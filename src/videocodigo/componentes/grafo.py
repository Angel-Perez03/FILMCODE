"""Grafo con pesos, valores junto a cada nodo, nodos cerrados, caminos y pulsos que viajan por aristas."""

from __future__ import annotations

from collections import deque

import numpy as np
from manim import (
    BOLD, DOWN, LEFT, ORIGIN, RIGHT, UP, AnimationGroup, Arrow, Circle, Create, Dot, FadeIn, FadeOut,
    GrowFromCenter, Indicate, LaggedStart, Line, MoveAlongPath, Succession, Transform, VGroup,
)

from .. import estilo as e
from .textos import texto


def disposicion_por_capas(nodos: list[str], aristas: list[tuple], inicio: str | None = None,
                          ancho: float = 10.0, alto: float = 5.0) -> dict[str, tuple[float, float]]:
    """Ubica los nodos por capas de BFS desde `inicio`, de izquierda a derecha (como el video de referencia)."""
    vecinos = {n: [] for n in nodos}
    for a in aristas:
        vecinos[a[0]].append(a[1])
        vecinos[a[1]].append(a[0])
    capa, pendientes = {}, list(nodos)
    while pendientes:
        raiz = inicio if inicio in pendientes else pendientes[0]
        base = max(capa.values(), default=-1) + 1
        cola = deque([(raiz, base)])
        capa[raiz] = base
        while cola:
            n, c = cola.popleft()
            for v in vecinos[n]:
                if v not in capa:
                    capa[v] = c + 1
                    cola.append((v, c + 1))
        pendientes = [n for n in nodos if n not in capa]
    capas: dict[int, list[str]] = {}
    for n in nodos:
        capas.setdefault(capa[n], []).append(n)
    total = max(capas) or 1
    posiciones = {}
    for c, grupo in capas.items():
        x = -ancho / 2 + ancho * c / total if total else 0.0
        for k, n in enumerate(grupo):
            y = 0.0 if len(grupo) == 1 else alto / 2 - alto * k / (len(grupo) - 1)
            posiciones[n] = (x, y)
    return posiciones


class Grafo(VGroup):
    """`aristas` = [("A", "B", 4), ...]; el peso es opcional. Si no das posiciones, se ubican por capas."""

    def __init__(self, nodos: list[str] | dict[str, tuple[float, float]], aristas: list[tuple],
                 dirigido: bool = False, radio: float = 0.42, inicio: str | None = None,
                 ancho: float = 10.0, alto: float = 5.0, tam_nodo: float = e.TAM_NODO, tam_peso: float = 30):
        super().__init__()
        if isinstance(nodos, dict):
            posiciones = nodos
        else:
            posiciones = disposicion_por_capas(list(nodos), aristas, inicio, ancho, alto)
        self.dirigido, self.radio, self.tam_nodo = dirigido, radio, tam_nodo
        self.circulos, self.letras, self.valores = {}, {}, {}
        for n, (x, y) in posiciones.items():
            punto = np.array([x, y, 0.0])
            circulo = Circle(radius=radio, color=e.TEXTO, stroke_width=3).set_fill(e.FONDO, opacity=1).move_to(punto)
            letra = texto(str(n), tam_nodo, e.TEXTO, peso=BOLD).move_to(punto)
            if letra.width > radio * 1.5:
                letra.scale_to_fit_width(radio * 1.5)
            self.circulos[n], self.letras[n] = circulo, letra
        pares = {(a[0], a[1]) for a in aristas}
        self.lineas, self.pesos = {}, {}
        for a in aristas:
            u, v = a[0], a[1]
            if u not in self.circulos or v not in self.circulos:
                raise ValueError(f"La arista {u}–{v} usa un nodo que no existe.")
            linea = self._linea(u, v, doble=dirigido and (v, u) in pares)
            self.lineas[(u, v)] = linea
            if len(a) > 2 and a[2] is not None:
                self.pesos[(u, v)] = self._etiqueta_peso(linea, a[2], tam_peso)
        self.add(*self.lineas.values(), *self.pesos.values())
        for n in self.circulos:
            self.add(self.circulos[n], self.letras[n])

    # Geometría (todo se mide sobre la posición actual, por si el grafo se movió o se escaló)
    @property
    def _centro(self) -> np.ndarray:
        return np.mean([c.get_center() for c in self.circulos.values()], axis=0)

    def _factor(self) -> float:
        circulo = next(iter(self.circulos.values()))
        return circulo.width / (2 * self.radio)

    def _linea(self, u: str, v: str, doble: bool):
        pu, pv = self.circulos[u].get_center(), self.circulos[v].get_center()
        d = (pv - pu) / np.linalg.norm(pv - pu)
        corrimiento = np.array([-d[1], d[0], 0]) * 0.13 if doble else ORIGIN
        ini, fin = pu + d * self.radio + corrimiento, pv - d * self.radio + corrimiento
        if self.dirigido:
            return Arrow(ini, fin, buff=0, stroke_width=3, color=e.GRIS_ARISTA, tip_length=0.22,
                         max_tip_length_to_length_ratio=0.5, max_stroke_width_to_length_ratio=12)
        return Line(ini, fin, stroke_width=3, color=e.GRIS_ARISTA)

    def _etiqueta_peso(self, linea, peso, tamano: float):
        ini, fin = linea.get_start(), linea.get_end()
        medio = (ini + fin) / 2
        d = (fin - ini) / max(np.linalg.norm(fin - ini), 1e-6)
        normal = np.array([-d[1], d[0], 0])
        if np.dot(normal, medio - self._centro) < 0:
            normal = -normal
        etiqueta = texto(e.numero(peso), tamano, e.TEXTO, peso=BOLD)
        return etiqueta.move_to(medio + normal * 0.32)

    def _lado(self, n: str) -> np.ndarray:
        rel = self.circulos[n].get_center() - self._centro
        if abs(rel[0]) > abs(rel[1]) * 1.6:
            return RIGHT if rel[0] > 0 else LEFT
        return UP if rel[1] >= 0 else DOWN

    def _arista(self, u: str, v: str):
        if (u, v) in self.lineas:
            return self.lineas[(u, v)]
        if not self.dirigido and (v, u) in self.lineas:
            return self.lineas[(v, u)]
        raise KeyError(f"No hay arista {u}–{v}.")

    # Animaciones
    def aparecer(self) -> AnimationGroup:
        nodos = [GrowFromCenter(VGroup(self.circulos[n], self.letras[n])) for n in self.circulos]
        aristas = [Create(l) for l in self.lineas.values()]
        pesos = [FadeIn(p) for p in self.pesos.values()]
        return AnimationGroup(LaggedStart(*nodos, lag_ratio=0.08), LaggedStart(*aristas, *pesos, lag_ratio=0.04),
                              lag_ratio=0.5)

    def valor(self, n: str, contenido, color: str = e.TEXTO) -> AnimationGroup:
        """Pone o cambia el número junto al nodo (p. ej. la distancia)."""
        f = self._factor()
        nuevo = texto(e.valor_corto(contenido) if not isinstance(contenido, str) else contenido,
                      self.tam_nodo * f, color, peso=BOLD)
        nuevo.next_to(self.circulos[n], self._lado(n), buff=0.16 * f)
        viejo = self.valores.get(n)
        if viejo is None:
            self.valores[n] = nuevo
            self.add(nuevo)
            return AnimationGroup(FadeIn(nuevo, scale=0.7))
        return AnimationGroup(Transform(viejo, nuevo))

    def valores_iniciales(self, contenido="∞", color: str = e.TEXTO) -> AnimationGroup:
        return AnimationGroup(*[self.valor(n, contenido, color) for n in self.circulos], lag_ratio=0.05)

    def cerrar(self, n: str, color: str = e.AZUL) -> AnimationGroup:
        """Rellena el nodo (ya visitado o definitivo) y pinta su valor del mismo color."""
        anims = [self.circulos[n].animate.set_fill(color, opacity=1).set_stroke(color),
                 self.letras[n].animate.set_color(e.FONDO)]
        if n in self.valores:
            anims.append(self.valores[n].animate.set_color(color))
        return AnimationGroup(*anims)

    def marcar(self, n: str, color: str = e.AZUL) -> AnimationGroup:
        """Solo el borde: el nodo que se está mirando ahora."""
        return AnimationGroup(self.circulos[n].animate.set_stroke(color, width=5), Indicate(self.letras[n], color=color))

    def abrir(self, n: str) -> AnimationGroup:
        anims = [self.circulos[n].animate.set_fill(e.FONDO, opacity=1).set_stroke(e.TEXTO, width=3),
                 self.letras[n].animate.set_color(e.TEXTO)]
        if n in self.valores:
            anims.append(self.valores[n].animate.set_color(e.TEXTO))
        return AnimationGroup(*anims)

    def resaltar_arista(self, u: str, v: str, color: str = e.AZUL, grosor: float = 5) -> AnimationGroup:
        return AnimationGroup(self._arista(u, v).animate.set_stroke(color, width=grosor))

    def atenuar_arista(self, u: str, v: str) -> AnimationGroup:
        return AnimationGroup(self._arista(u, v).animate.set_stroke(e.GRIS_ARISTA, width=3))

    def camino(self, nodos: list[str], color: str = e.ROJO) -> Succession:
        pasos = [self.resaltar_arista(a, b, color, 6) for a, b in zip(nodos, nodos[1:])]
        return Succession(*pasos)

    def pulso(self, u: str, v: str, color: str = e.ROJO) -> Succession:
        """Un punto que viaja de u a v (flujo, recorrido, el 'surfista' de PageRank)."""
        linea = self._arista(u, v)
        ini, fin = (linea.get_start(), linea.get_end()) if (u, v) in self.lineas else (linea.get_end(), linea.get_start())
        punto = Dot(ini, radius=0.1, color=color)
        return Succession(FadeIn(punto, run_time=0.15), MoveAlongPath(punto, Line(ini, fin)), FadeOut(punto, run_time=0.15))

    def cambiar_peso(self, u: str, v: str, peso, color: str = e.ROJO) -> AnimationGroup:
        clave = (u, v) if (u, v) in self.pesos else (v, u)
        viejo = self.pesos[clave]
        nuevo = texto(e.numero(peso), 30 * self._factor(), color, peso=BOLD)
        return AnimationGroup(Transform(viejo, nuevo.move_to(viejo)))

    def nodo(self, n: str) -> VGroup:
        return VGroup(self.circulos[n], self.letras[n])
