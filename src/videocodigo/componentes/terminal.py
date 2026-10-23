"""Ventana de terminal: escribe comandos, muestra su salida y subraya fragmentos mientras se explican."""

from __future__ import annotations

import numpy as np
from manim import (
    DOWN, LEFT, UP, AnimationGroup, Circle, Create, FadeIn, FadeOut, Line, RoundedRectangle, ShowIncreasingSubsets,
    VectorizedPoint,
    Succession, VGroup,
)

from .. import estilo as e
from .textos import medidas_mono, mono, nota, texto

PROMPTS = {"bash": ("$", e.VERDE), "powershell": ("PS>", e.AZUL), "cmd": (">", e.AZUL)}


def partir(texto: str, ancho: int) -> list[tuple[int, str]]:
    """Parte un comando largo en filas de `ancho` caracteres, de preferencia en un espacio.

    Devuelve (posición en el texto original, contenido de la fila).
    """
    filas, inicio = [], 0
    while inicio < len(texto):
        fin = min(inicio + ancho, len(texto))
        if fin < len(texto):
            corte = texto.rfind(" ", inicio + 1, fin)
            if corte > inicio + ancho // 3:
                fin = corte + 1
        filas.append((inicio, texto[inicio:fin]))
        inicio = fin
    return filas or [(0, "")]


class Terminal(VGroup):
    """`escribir(cmd)`, `salida([...])`, `subrayar(fragmento, nota)`, `quitar_subrayados()`, `limpiar()`."""

    def __init__(self, titulo: str = "Ventana de terminal", shell: str = "bash", ancho: float = 12.4,
                 alto: float = 5.2, tamano: float = 22):
        super().__init__()
        self.shell, self.tamano = shell, tamano
        self.ancho_letra, self.alto_letra = medidas_mono(tamano)
        self.paso = self.alto_letra * 1.95
        self.marco = RoundedRectangle(corner_radius=0.18, width=ancho, height=alto, stroke_color="#2A2E36",
                                      stroke_width=2).set_fill("#0D1117", opacity=1)
        arriba = self.marco.get_top()[1]
        izquierda = self.marco.get_left()[0]
        botones = VGroup(*[Circle(radius=0.07, stroke_width=0).set_fill(c, 0.85)
                           for c in (e.ROJO, e.AMARILLO, e.VERDE)]).arrange(np.array([1, 0, 0]), buff=0.12)
        botones.move_to(np.array([izquierda + 0.45, arriba - 0.3, 0]))
        self.titulo = nota(titulo, 22).move_to(np.array([self.marco.get_center()[0], arriba - 0.3, 0]))
        separador = Line(np.array([izquierda, arriba - 0.58, 0]), np.array([izquierda + ancho, arriba - 0.58, 0]),
                         color="#2A2E36", stroke_width=2)
        # Ancla y regla invisibles: viajan con la ventana si se mueve o se escala
        self._paso_original = self.paso
        self._ancla = VectorizedPoint(np.array([izquierda + 0.35, arriba - 0.8, 0.0]))
        self._regla = VectorizedPoint(np.array([izquierda + 0.35, arriba - 0.8 - self.paso, 0.0]))
        self.add(self.marco, botones, self.titulo, separador, self._ancla, self._regla)
        self.max_filas = max(int((alto - 1.05) / self.paso), 3)
        self.max_columnas = max(int((ancho - 0.7) / self.ancho_letra), 20)
        self.filas: list[VGroup] = []
        self.comandos: list[dict] = []
        self._marcas: list = []
        self._pintados: list = []

    # Posiciones
    def _factor(self) -> float:
        return (self._ancla.get_center()[1] - self._regla.get_center()[1]) / self._paso_original

    def _punto(self, fila: int, columna: int = 0) -> np.ndarray:
        f = self._factor()
        return self._ancla.get_center() + np.array([columna * self.ancho_letra * f, -fila * self.paso * f, 0])

    def _mono(self, contenido: str, punto: np.ndarray, color: str):
        return mono(contenido, punto, self.tamano * self._factor(), color)

    def _espacio(self, necesarias: int) -> list:
        """Si no caben `necesarias` filas más, sube el contenido como una terminal real."""
        sobra = len(self.filas) + necesarias - self.max_filas
        if sobra <= 0:
            return []
        salen, quedan = self.filas[:sobra], self.filas[sobra:]
        self.filas = quedan
        for grupo in salen:
            self.remove(grupo)
        desplazamiento = UP * self.paso * self._factor() * sobra
        anims = [FadeOut(g, shift=desplazamiento) for g in salen]
        anims += [g.animate.shift(desplazamiento) for g in quedan]
        for cmd in self.comandos:
            cmd["fila0"] -= sobra
        return [AnimationGroup(*anims)]

    # Animaciones
    def escribir(self, comando: str, prompt: str | None = None, color: str = e.TEXTO):
        simbolo, color_prompt = (prompt, e.GRIS) if prompt is not None else PROMPTS.get(self.shell, PROMPTS["bash"])
        sangria = len(simbolo) + 1
        trozos = partir(comando, self.max_columnas - sangria)
        previas = self._espacio(len(trozos))
        fila0 = len(self.filas)
        marca = self._mono(simbolo, self._punto(fila0), color_prompt)
        textos = []
        for k, (_, contenido) in enumerate(trozos):
            textos.append(self._mono(contenido, self._punto(fila0 + k, sangria), color))
        for k, t in enumerate(textos):
            grupo = VGroup(marca, t) if k == 0 else VGroup(t)
            self.filas.append(grupo)
            self.add(grupo)
        self.comandos.append({"texto": comando, "trozos": trozos, "textos": textos, "fila0": fila0})
        tecleo = [ShowIncreasingSubsets(t, run_time=max(len(c), 1) * 0.03) for t, (_, c) in zip(textos, trozos) if len(t)]
        escribir = AnimationGroup(FadeIn(marca, run_time=0.15), Succession(*tecleo) if tecleo else FadeIn(marca),
                                  lag_ratio=1.0)
        return Succession(*previas, escribir) if previas else escribir

    def salida(self, lineas: list[str], color: str = "#A9AEB7"):
        lineas = [l if len(l) <= self.max_columnas else l[: self.max_columnas - 1] + "…" for l in lineas]
        previas = self._espacio(len(lineas))
        inicio = len(self.filas)
        nuevas = []
        for k, contenido in enumerate(lineas):
            grupo = VGroup(self._mono(contenido, self._punto(inicio + k), color))
            self.filas.append(grupo)
            self.add(grupo)
            nuevas.append(grupo)
        aparecer = AnimationGroup(*[FadeIn(g, shift=UP * 0.05) for g in nuevas], lag_ratio=0.15)
        return Succession(*previas, aparecer) if previas else aparecer

    def subrayar(self, fragmento: str, texto_nota: str | None = None, color: str = e.AZUL, comando: int = -1,
                 ocurrencia: int = 0) -> AnimationGroup:
        """Subraya `fragmento` dentro del comando (el último, por defecto) y abre una tarjeta con la explicación
        justo debajo. `self.foco` queda con lo subrayado y la tarjeta, para que la cámara se acerque."""
        cmd = self.comandos[comando]
        inicio = -1
        for _ in range(ocurrencia + 1):
            inicio = cmd["texto"].find(fragmento, inicio + 1)
        if inicio < 0:
            raise ValueError(f"{fragmento!r} no aparece en el comando {cmd['texto']!r}.")
        fin = inicio + len(fragmento)
        anims, subrayadas = [], VGroup()
        for (pos, contenido), mob in zip(cmd["trozos"], cmd["textos"]):
            a, b = max(inicio, pos), min(fin, pos + len(contenido))
            if a >= b:
                continue
            desde = len(contenido[: a - pos].replace(" ", ""))
            cuantos = len(contenido[a - pos: b - pos].replace(" ", ""))
            letras = VGroup(*mob[desde: desde + cuantos])
            if not len(letras):
                continue
            base = letras.get_bottom()[1] - 0.07
            linea = Line(np.array([letras.get_left()[0], base, 0]), np.array([letras.get_right()[0], base, 0]),
                         color=color, stroke_width=4)
            self._marcas.append(linea)
            self._pintados.append(letras)
            self.add(linea)
            subrayadas.add(letras, linea)
            anims += [Create(linea), letras.animate.set_color(color)]
        self.foco = VGroup(subrayadas)
        if texto_nota and len(subrayadas):
            tarjeta = self._tarjeta(texto_nota, color, subrayadas)
            self._marcas.append(tarjeta)
            self.add(tarjeta)
            self.foco.add(tarjeta)
            anims.append(FadeIn(tarjeta, shift=UP * 0.12, scale=0.95))
        return AnimationGroup(*anims)

    def _tarjeta(self, contenido: str, color: str, ancla: VGroup) -> VGroup:
        """Tarjeta flotante (como el tooltip de un editor) debajo del fragmento, sin salirse de la ventana."""
        letras = texto(contenido, 26 * self._factor(), e.TEXTO)
        limite = self.marco.width * 0.62
        if letras.width > limite:
            letras.scale_to_fit_width(limite)
        caja = RoundedRectangle(corner_radius=0.12, width=letras.width + 0.45, height=letras.height + 0.36,
                                stroke_color=color, stroke_width=2).set_fill("#111A2B", opacity=0.97)
        tarjeta = VGroup(caja, letras.move_to(caja))
        tarjeta.next_to(ancla, DOWN, buff=0.2).align_to(ancla, LEFT)
        derecha, izquierda = self.marco.get_right()[0] - 0.2, self.marco.get_left()[0] + 0.2
        if tarjeta.get_right()[0] > derecha:
            tarjeta.shift(np.array([derecha - tarjeta.get_right()[0], 0, 0]))
        if tarjeta.get_left()[0] < izquierda:
            tarjeta.shift(np.array([izquierda - tarjeta.get_left()[0], 0, 0]))
        if tarjeta.get_bottom()[1] < self.marco.get_bottom()[1] + 0.1:
            tarjeta.next_to(ancla, UP, buff=0.2)
        tarjeta.set_z_index(5)
        return tarjeta

    def insignia(self, real: bool) -> AnimationGroup:
        """Etiqueta en la barra de título: si la salida es real (de este equipo) o un ejemplo."""
        anims = []
        if getattr(self, "_insignia", None) is not None:
            anims.append(FadeOut(self._insignia))
            self.remove(self._insignia)
        contenido = "● salida real de este equipo" if real else "salida de ejemplo"
        self._insignia = texto(contenido, 20 * self._factor(), e.VERDE if real else e.GRIS, cursiva=not real)
        self._insignia.move_to(self.titulo).align_to(self.marco, np.array([1, 0, 0])).shift(np.array([-0.35, 0, 0]))
        self.add(self._insignia)
        anims.append(FadeIn(self._insignia))
        return AnimationGroup(*anims)

    def quitar_subrayados(self) -> AnimationGroup:
        anims = [FadeOut(m) for m in self._marcas] + [l.animate.set_color(e.TEXTO) for l in self._pintados]
        for m in self._marcas:
            self.remove(m)
        self._marcas, self._pintados = [], []
        return AnimationGroup(*anims)

    def limpiar(self) -> AnimationGroup:
        extra = [self._insignia] if getattr(self, "_insignia", None) is not None else []
        anims = [FadeOut(g) for g in self.filas + self._marcas + extra]
        for g in self.filas + self._marcas + extra:
            self.remove(g)
        self.filas, self.comandos, self._marcas, self._pintados, self._insignia = [], [], [], [], None
        return AnimationGroup(*anims)
