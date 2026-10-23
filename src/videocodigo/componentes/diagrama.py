"""Diagramas de cajas y flechas (arquitectura, flujo de datos) y lista de archivos de un proyecto."""

from __future__ import annotations

from collections import deque

import numpy as np
from manim import (
    DOWN, LEFT, AnimationGroup, Arrow, Create, Dot, FadeIn, FadeOut, Indicate, LaggedStart, Line, MoveAlongPath,
    RoundedRectangle, Succession, Transform, VGroup,
)

from .. import estilo as e
from .textos import mono, texto


def _borde(centro: np.ndarray, ancho: float, alto: float, direccion: np.ndarray) -> np.ndarray:
    """Punto donde una recta desde el centro de un rectángulo cruza su borde."""
    dx, dy = abs(direccion[0]) or 1e-9, abs(direccion[1]) or 1e-9
    t = min(ancho / 2 / dx, alto / 2 / dy)
    return centro + direccion * t


def disposicion_flujo(nombres: list[str], flechas: list[tuple], ancho: float = 11.0, alto: float = 5.0) -> dict:
    """Columnas según el orden del flujo (BFS desde las cajas sin flechas de entrada)."""
    entrantes = {n: 0 for n in nombres}
    salidas = {n: [] for n in nombres}
    for f in flechas:
        salidas[f[0]].append(f[1])
        entrantes[f[1]] += 1
    columna = {}
    cola = deque([(n, 0) for n in nombres if entrantes[n] == 0] or [(nombres[0], 0)])
    while cola:
        n, c = cola.popleft()
        if n in columna:
            continue
        columna[n] = c
        cola.extend((v, c + 1) for v in salidas[n] if v not in columna)
    for n in nombres:
        columna.setdefault(n, max(columna.values(), default=-1) + 1)
    grupos: dict[int, list[str]] = {}
    for n in nombres:
        grupos.setdefault(columna[n], []).append(n)
    total = max(grupos) or 1
    posiciones = {}
    for c, grupo in grupos.items():
        x = -ancho / 2 + ancho * c / total if total else 0.0
        for k, n in enumerate(grupo):
            y = 0.0 if len(grupo) == 1 else alto / 2 - alto * k / (len(grupo) - 1)
            posiciones[n] = (x, y)
    return posiciones


class Diagrama(VGroup):
    """`cajas` = {"api": "API REST"}, {"api": ("API REST", "rutas.py")} o {"api": {"titulo", "icono", "detalle"}};
    `flechas` = [("api", "db", "consulta")]."""

    def __init__(self, cajas: dict, flechas: list[tuple] = (), posiciones: dict | None = None,
                 ancho_caja: float = 2.8, alto_caja: float = 1.1, ancho: float = 11.0, alto: float = 5.0):
        super().__init__()
        from .movimiento import Tarjeta

        posiciones = posiciones or disposicion_flujo(list(cajas), list(flechas), ancho, alto)
        self.cajas, self.flechas, self.rotulos = {}, {}, {}
        for nombre, contenido in cajas.items():
            x, y = posiciones[nombre]
            if isinstance(contenido, dict):
                caja = Tarjeta(contenido.get("titulo", nombre), contenido.get("icono"), contenido.get("detalle"),
                               ancho=ancho_caja)
                self.cajas[nombre] = caja.move_to(np.array([x, y, 0]))
                continue
            titulo, detalle = (contenido, None) if isinstance(contenido, str) else (contenido[0], contenido[1])
            marco = RoundedRectangle(corner_radius=0.14, width=ancho_caja, height=alto_caja,
                                     stroke_color=e.GRIS, stroke_width=2.5).set_fill(e.FONDO, opacity=1)
            partes = [texto(titulo, 28, e.TEXTO)]
            if detalle:
                partes.append(texto(detalle, 18, e.GRIS, fuente=e.FUENTE_CODIGO))
            letras = VGroup(*partes).arrange(DOWN, buff=0.1)
            if letras.width > ancho_caja - 0.3:
                letras.scale_to_fit_width(ancho_caja - 0.3)
            caja = VGroup(marco, letras.move_to(marco)).move_to(np.array([x, y, 0]))
            self.cajas[nombre] = caja
        for f in flechas:
            u, v = f[0], f[1]
            cu, cv = self.cajas[u][0], self.cajas[v][0]
            d = cv.get_center() - cu.get_center()
            d = d / max(np.linalg.norm(d), 1e-6)
            ini = _borde(cu.get_center(), cu.width, cu.height, d) + d * 0.08
            fin = _borde(cv.get_center(), cv.width, cv.height, -d) - d * 0.08
            flecha = Arrow(ini, fin, buff=0, color=e.GRIS_ARISTA, stroke_width=3, tip_length=0.2,
                           max_tip_length_to_length_ratio=0.4)
            self.flechas[(u, v)] = flecha
            if len(f) > 2 and f[2]:
                normal = np.array([-d[1], d[0], 0])
                self.rotulos[(u, v)] = texto(f[2], 22, e.GRIS, cursiva=True).move_to((ini + fin) / 2 + normal * 0.3)
        self.add(*self.flechas.values(), *self.rotulos.values(), *self.cajas.values())

    def aparecer(self) -> AnimationGroup:
        return AnimationGroup(LaggedStart(*[FadeIn(c, shift=DOWN * 0.15) for c in self.cajas.values()], lag_ratio=0.12),
                              LaggedStart(*[Create(f) for f in self.flechas.values()],
                                          *[FadeIn(r) for r in self.rotulos.values()], lag_ratio=0.1),
                              lag_ratio=0.6)

    def resaltar(self, nombre: str, color: str = e.AZUL) -> AnimationGroup:
        caja = self.cajas[nombre]
        anims = [caja[0].animate.set_stroke(color, width=4)]
        if len(caja) > 1:
            anims.append(Indicate(caja[1], color=None, scale_factor=1.08))
        return AnimationGroup(*anims)

    def normal(self) -> AnimationGroup:
        return self.enfocar(None)

    def enfocar(self, nombre: str | None, color: str = e.AZUL) -> AnimationGroup:
        """Resalta una caja y devuelve las demás a su borde normal, en una sola animación.

        Se anima la caja completa (no solo el marco): Manim pasa al frente lo que anima dentro de un grupo,
        y un marco con relleno tapaba el ícono y el texto.
        """
        anims = []
        for clave, caja in self.cajas.items():
            objetivo = caja.copy()
            if clave == nombre:
                objetivo[0].set_stroke(color, width=4)
            else:
                objetivo[0].set_stroke(self._borde(caja), width=2.5)
            anims.append(Transform(caja, objetivo))
        return AnimationGroup(*anims)

    @staticmethod
    def _borde(caja) -> str:
        from .movimiento import BORDE_TARJETA

        return BORDE_TARJETA if caja[0].get_fill_opacity() < 1 else e.GRIS

    def flujo(self, origen: str, destino: str, color: str = e.AZUL, viajero: str | None = None) -> Succession:
        """Algo viaja por la flecha (un punto, o el ícono `viajero`): un dato, una petición, una imagen."""
        flecha = self.flechas.get((origen, destino))
        if flecha is None:
            flecha = self.flechas[(destino, origen)]
            ini, fin = flecha.get_end(), flecha.get_start()
        else:
            ini, fin = flecha.get_start(), flecha.get_end()
        if viajero:
            from .iconos import icono

            punto = icono(viajero, color, 0.55).move_to(ini)
        else:
            punto = Dot(ini, radius=0.1, color=color)
        return Succession(FadeIn(punto, run_time=0.15, scale=0.6), MoveAlongPath(punto, Line(ini, fin)),
                          FadeOut(punto, run_time=0.2, scale=0.6))


class ListaArchivos(VGroup):
    """Árbol de archivos de un proyecto, con sangría por carpeta. `resaltar('src/motor.py')`."""

    def __init__(self, rutas: list[str], tamano: float = 22, max_lineas: int = 18):
        super().__init__()
        filas, vistas = [], set()
        for ruta in sorted(rutas):
            partes = ruta.replace("\\", "/").split("/")
            for nivel in range(len(partes) - 1):
                carpeta = "/".join(partes[: nivel + 1])
                if carpeta not in vistas:
                    vistas.add(carpeta)
                    filas.append((nivel, partes[nivel] + "/", carpeta, True))
            filas.append((len(partes) - 1, partes[-1], ruta.replace("\\", "/"), False))
        if len(filas) > max_lineas:
            filas = filas[: max_lineas - 1] + [(0, f"… y {len(filas) - max_lineas + 1} más", "", False)]
        self.lineas: dict[str, VGroup] = {}
        ancho, _ = 0.0, 0.0
        for i, (nivel, nombre, clave, es_carpeta) in enumerate(filas):
            color = e.GRIS if es_carpeta else e.TEXTO_SUAVE
            linea = mono("  " * nivel + nombre, np.array([0, -i * tamano / 40, 0]), tamano, color)
            self.add(linea)
            if clave:
                self.lineas[clave] = linea

    def resaltar(self, ruta: str, color: str = e.AZUL) -> AnimationGroup:
        ruta = ruta.replace("\\", "/")
        anims = [l.animate.set_opacity(1 if k == ruta else 0.35) for k, l in self.lineas.items()]
        if ruta in self.lineas:
            anims.append(self.lineas[ruta].animate.set_color(color))
        return AnimationGroup(*anims)

    def normal(self) -> AnimationGroup:
        return AnimationGroup(*[l.animate.set_opacity(1) for l in self.lineas.values()])
