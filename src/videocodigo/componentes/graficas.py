"""Gráficas sencillas: una curva (error contra vueltas) y barras que cambian de altura."""

from __future__ import annotations

import math

import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UP, AnimationGroup, Create, DashedLine, FadeIn, Line, Rectangle, Transform, VGroup,
    VMobject,
)

from .. import estilo as e
from .textos import nota, texto


class GraficaLinea(VGroup):
    """Ejes mínimos con etiquetas en cursiva, una curva azul y una línea de referencia punteada roja."""

    def __init__(self, ys: list[float], xs: list[float] | None = None, ancho: float = 5.0, alto: float = 3.0,
                 etiqueta_x: str = "", etiqueta_y: str = "", referencia: float | None = None,
                 etiqueta_referencia: str = "", logaritmica: bool = False):
        super().__init__()
        xs = xs or list(range(len(ys)))
        if len(xs) != len(ys) or len(ys) < 2:
            raise ValueError("La gráfica necesita al menos dos puntos y tantos x como y.")
        transformar = (lambda v: math.log10(max(v, 1e-12))) if logaritmica else float
        yt = [transformar(y) for y in ys]
        ref = transformar(referencia) if referencia is not None else None
        bajo = min(yt + ([ref] if ref is not None else []))
        alto_v = max(yt + ([ref] if ref is not None else []))
        rango_y = (alto_v - bajo) or 1.0
        rango_x = (max(xs) - min(xs)) or 1.0

        def punto(x, y):
            return np.array([(x - min(xs)) / rango_x * ancho, (y - bajo) / rango_y * alto, 0])

        self.eje_x = Line(punto(min(xs), bajo), punto(min(xs), bajo) + RIGHT * ancho, color=e.GRIS, stroke_width=2)
        self.eje_y = Line(punto(min(xs), bajo), punto(min(xs), bajo) + UP * alto, color=e.GRIS, stroke_width=2)
        self.curva = VMobject(color=e.AZUL, stroke_width=4)
        self.curva.set_points_smoothly([punto(x, y) for x, y in zip(xs, yt)])
        self.add(self.eje_x, self.eje_y)
        if etiqueta_y:
            self.add(nota(etiqueta_y, 24).next_to(self.eje_y, UP, buff=0.12))
        if etiqueta_x:
            self.add(nota(etiqueta_x, 24).next_to(self.eje_x.get_end(), UP + LEFT * 0.2, buff=0.12))
        if ref is not None:
            self.referencia = DashedLine(punto(min(xs), ref), punto(max(xs), ref), color=e.ROJO, stroke_width=2)
            self.add(self.referencia)
            if etiqueta_referencia:
                self.add(nota(etiqueta_referencia, 22, e.ROJO).next_to(self.referencia.get_end(), UP + LEFT * 0.4, buff=0.08))
        self.add(self.curva)

    def dibujar(self) -> Create:
        return Create(self.curva)


class Barras(VGroup):
    """Barras verticales (puntajes, frecuencias). `actualizar(valores)` cambia sus alturas."""

    def __init__(self, valores: list[float], etiquetas: list[str] | None = None, ancho_barra: float = 0.45,
                 alto_max: float = 2.5, separacion: float = 0.35, maximo: float | None = None, color: str = e.AZUL):
        super().__init__()
        self.alto_max, self.color, self.ancho_barra = alto_max, color, ancho_barra
        self.maximo = maximo or max(max(valores), 1e-9)
        self.base_y = 0.0
        self.barras = [self._barra(v, i * (ancho_barra + separacion)) for i, v in enumerate(valores)]
        self.add(*self.barras)
        if etiquetas:
            for barra, etiqueta in zip(self.barras, etiquetas):
                self.add(texto(etiqueta, 22, e.GRIS).next_to(barra, DOWN, buff=0.12))

    def _barra(self, valor: float, x: float) -> Rectangle:
        alto = max(valor / self.maximo * self.alto_max, 0.02)
        barra = Rectangle(width=self.ancho_barra, height=alto, stroke_width=0).set_fill(self.color, opacity=0.9)
        return barra.move_to(np.array([x, self.base_y + alto / 2, 0]))

    def actualizar(self, valores: list[float]) -> AnimationGroup:
        anims = []
        for barra, valor in zip(self.barras, valores):
            base = barra.get_bottom()
            alto = max(valor / self.maximo * self.alto_max * (barra.width / self.ancho_barra), 0.02)
            nueva = barra.copy().stretch_to_fit_height(alto).move_to(base + UP * alto / 2)
            anims.append(Transform(barra, nueva))
        return AnimationGroup(*anims)
