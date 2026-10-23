"""Tabla de texto (requisitos, comparaciones, versiones) con filas que se pueden resaltar."""

from __future__ import annotations

import numpy as np
from manim import DOWN, LEFT, SEMIBOLD, UP, AnimationGroup, FadeIn, LaggedStart, Line, Rectangle, VGroup

from .. import estilo as e
from .textos import texto


def _celda(contenido: str, tamano: float, color: str, ancho_max: float, peso=None) -> VGroup:
    """Texto que se parte en varias líneas si no cabe en `ancho_max`."""
    kw = {"peso": peso} if peso else {}
    palabras, lineas, actual = str(contenido).split(), [], ""
    for palabra in palabras:
        prueba = f"{actual} {palabra}".strip()
        if actual and texto(prueba, tamano, color, **kw).width > ancho_max:
            lineas.append(actual)
            actual = palabra
        else:
            actual = prueba
    lineas.append(actual)
    return VGroup(*[texto(l or " ", tamano, color, **kw) for l in lineas]).arrange(DOWN, buff=0.08, aligned_edge=LEFT)


class Tabla(VGroup):
    """`aparecer()`, `resaltar(i)` (fila i, desde 0) y `normal()`."""

    def __init__(self, encabezados: list[str], filas: list[list[str]], tamano: float = 28,
                 ancho_columna: float = 5.2, ancho_max: float = e.ANCHO_UTIL):
        super().__init__()
        columnas = len(encabezados)
        filas = [list(map(str, f)) + [""] * (columnas - len(f)) for f in filas]
        cabeza = [_celda(t, tamano * 0.85, e.GRIS, ancho_columna, SEMIBOLD) for t in encabezados]
        cuerpo = [[_celda(t, tamano, e.TEXTO_SUAVE, ancho_columna) for t in fila] for fila in filas]
        anchos = [max([cabeza[c].width] + [f[c].width for f in cuerpo]) + 0.6 for c in range(columnas)]
        altos = [max(c.height for c in cabeza) + 0.35] + [max(c.height for c in f) + 0.4 for f in cuerpo]
        total = sum(anchos)
        y = 0.0
        self.fondos, self.celdas = [], []
        for r, fila in enumerate([cabeza] + cuerpo):
            x = 0.0
            for c, celda in enumerate(fila):
                celda.move_to(np.array([x + 0.3, y - altos[r] / 2, 0]), aligned_edge=LEFT)
                x += anchos[c]
            if r:
                fondo = Rectangle(width=total, height=altos[r], stroke_width=0).set_fill(e.AZUL_OSCURO, opacity=0)
                fondo.move_to(np.array([total / 2, y - altos[r] / 2, 0]))
                self.fondos.append(fondo)
                self.add(fondo)
            self.celdas.append(VGroup(*fila))
            y -= altos[r]
            color = e.GRIS if r == 0 else e.GRIS_OSCURO
            self.add(Line(np.array([0, y, 0]), np.array([total, y, 0]), color=color, stroke_width=2 if r == 0 else 1))
        self.add(*self.celdas)
        if self.width > ancho_max:
            self.scale_to_fit_width(ancho_max)
        self.move_to(np.zeros(3))

    def aparecer(self) -> LaggedStart:
        return LaggedStart(*[FadeIn(f, shift=UP * 0.1) for f in self.celdas], lag_ratio=0.15)

    def resaltar(self, *indices: int) -> AnimationGroup:
        anims = []
        for i, fondo in enumerate(self.fondos):
            activo = i in indices
            anims.append(fondo.animate.set_fill(opacity=0.95 if activo else 0))
            anims.append(self.celdas[i + 1].animate.set_opacity(1 if activo else 0.45))
        return AnimationGroup(*anims)

    def normal(self) -> AnimationGroup:
        return AnimationGroup(*[f.animate.set_fill(opacity=0) for f in self.fondos],
                              *[c.animate.set_opacity(1) for c in self.celdas[1:]])
