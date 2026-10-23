"""Arreglos y matrices: celdas con valores, índices, punteros, comparaciones e intercambios."""

from __future__ import annotations

import numpy as np
from manim import (
    DOWN, PI, UP, AnimationGroup, Arrow, FadeIn, Indicate, Square, Transform, VGroup,
)

from .. import estilo as e
from .textos import mono, texto


def _contenido(valor, tamano: float, color: str = e.TEXTO) -> VGroup:
    letras = texto(e.valor_corto(valor, max_largo=6), tamano, color, fuente=e.FUENTE_CODIGO)
    return letras


class Arreglo(VGroup):
    """Fila de celdas. `intercambiar(i, j)`, `poner(i, v)`, `puntero('i', 2)`, `resaltar(i)`."""

    def __init__(self, valores: list, lado: float = 0.95, indices: bool = True, tamano: float = 30,
                 etiqueta: str | None = None):
        super().__init__()
        self.lado, self.tamano = lado, tamano
        self.celdas = VGroup(*[Square(side_length=lado, color=e.GRIS, stroke_width=2.5) for _ in valores])
        self.celdas.arrange(np.array([1, 0, 0]), buff=0)
        self.valores = [_contenido(v, tamano).move_to(c) for v, c in zip(valores, self.celdas)]
        self.add(self.celdas, *self.valores)
        if indices:
            self.indices = VGroup(*[texto(str(i), tamano * 0.6, e.GRIS, fuente=e.FUENTE_CODIGO)
                                    .next_to(c, DOWN, buff=0.12) for i, c in enumerate(self.celdas)])
            self.add(self.indices)
        if etiqueta:
            self.etiqueta = texto(etiqueta, tamano * 0.9, e.GRIS, cursiva=True).next_to(self.celdas, np.array([-1, 0, 0]), buff=0.3)
            self.add(self.etiqueta)
        self.punteros: dict[str, VGroup] = {}

    def _factor(self) -> float:
        return self.celdas[0].width / self.lado

    def poner(self, i: int, valor, color: str = e.AZUL) -> AnimationGroup:
        nuevo = _contenido(valor, self.tamano * self._factor(), color).move_to(self.celdas[i])
        return AnimationGroup(Transform(self.valores[i], nuevo))

    def intercambiar(self, i: int, j: int) -> AnimationGroup:
        vi, vj = self.valores[i], self.valores[j]
        self.valores[i], self.valores[j] = vj, vi
        return AnimationGroup(vi.animate(path_arc=PI / 1.6).move_to(self.celdas[j]),
                              vj.animate(path_arc=PI / 1.6).move_to(self.celdas[i]))

    def resaltar(self, *indices: int, color: str = e.AZUL) -> AnimationGroup:
        return AnimationGroup(*[self.celdas[i].animate.set_fill(color, opacity=0.25).set_stroke(color, width=4)
                                for i in indices])

    def comparar(self, i: int, j: int, color: str = e.AMARILLO) -> AnimationGroup:
        return AnimationGroup(Indicate(self.valores[i], color=color), Indicate(self.valores[j], color=color))

    def normal(self, *indices: int) -> AnimationGroup:
        objetivo = indices or range(len(self.celdas))
        return AnimationGroup(*[self.celdas[i].animate.set_fill(opacity=0).set_stroke(e.GRIS, width=2.5)
                                for i in objetivo])

    def marcar_listo(self, *indices: int, color: str = e.AZUL) -> AnimationGroup:
        """Celdas que ya quedaron en su lugar definitivo."""
        return AnimationGroup(*[v.animate.set_color(color) for k, v in enumerate(self.valores) if k in indices])

    def puntero(self, nombre: str, i: int, color: str = e.ROJO) -> AnimationGroup:
        """Flecha con nombre bajo la celda i; si ya existe, se mueve."""
        celda = self.celdas[i]
        base = celda.get_bottom() + DOWN * (0.55 * self._factor())
        if nombre not in self.punteros:
            flecha = Arrow(base + DOWN * 0.5, base, buff=0, color=color, stroke_width=4, tip_length=0.18)
            letrero = mono(nombre, tamano=22 * self._factor(), color=color)
            letrero.next_to(flecha, DOWN, buff=0.08)
            grupo = VGroup(flecha, letrero)
            self.punteros[nombre] = grupo
            self.add(grupo)
            return AnimationGroup(FadeIn(grupo, shift=UP * 0.2))
        grupo = self.punteros[nombre]
        return AnimationGroup(grupo.animate.shift(np.array([celda.get_center()[0] - grupo[0].get_center()[0], 0, 0])))


class Matriz(VGroup):
    """Cuadrícula (programación dinámica, tableros). `poner(f, c, v)`, `resaltar(f, c)`."""

    def __init__(self, filas: int, columnas: int, valores: list[list] | None = None, lado: float = 0.75,
                 tamano: float = 24, encabezados_filas: list[str] | None = None,
                 encabezados_columnas: list[str] | None = None):
        super().__init__()
        self.lado, self.tamano = lado, tamano
        self.celdas = [[Square(side_length=lado, color=e.GRIS_OSCURO, stroke_width=2) for _ in range(columnas)]
                       for _ in range(filas)]
        rejilla = VGroup(*[VGroup(*fila).arrange(np.array([1, 0, 0]), buff=0) for fila in self.celdas])
        rejilla.arrange(DOWN, buff=0)
        self.add(rejilla)
        self.valores: dict[tuple[int, int], VGroup] = {}
        for f in range(filas):
            for c in range(columnas):
                if valores and valores[f][c] is not None:
                    v = _contenido(valores[f][c], tamano).move_to(self.celdas[f][c])
                    self.valores[(f, c)] = v
                    self.add(v)
        if encabezados_filas:
            for f, t in enumerate(encabezados_filas):
                self.add(texto(t, tamano * 0.8, e.GRIS, fuente=e.FUENTE_CODIGO).next_to(self.celdas[f][0], np.array([-1, 0, 0]), buff=0.15))
        if encabezados_columnas:
            for c, t in enumerate(encabezados_columnas):
                self.add(texto(t, tamano * 0.8, e.GRIS, fuente=e.FUENTE_CODIGO).next_to(self.celdas[0][c], UP, buff=0.12))

    def poner(self, f: int, c: int, valor, color: str = e.AZUL) -> AnimationGroup:
        factor = self.celdas[0][0].width / self.lado
        nuevo = _contenido(valor, self.tamano * factor, color).move_to(self.celdas[f][c])
        if (f, c) in self.valores:
            return AnimationGroup(Transform(self.valores[(f, c)], nuevo))
        self.valores[(f, c)] = nuevo
        self.add(nuevo)
        return AnimationGroup(FadeIn(nuevo, scale=0.6))

    def resaltar(self, f: int, c: int, color: str = e.AZUL) -> AnimationGroup:
        return AnimationGroup(self.celdas[f][c].animate.set_fill(color, opacity=0.25).set_stroke(color, width=3))

    def normal(self) -> AnimationGroup:
        return AnimationGroup(*[celda.animate.set_fill(opacity=0).set_stroke(e.GRIS_OSCURO, width=2)
                                for fila in self.celdas for celda in fila])
