"""Cola y pila de cajitas: meter, sacar, tachar y resaltar elementos."""

from __future__ import annotations

import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UP, AnimationGroup, Create, FadeIn, FadeOut, RoundedRectangle, VGroup,
)

from .. import estilo as e
from .textos import mono, nota, tachar


class FilaCajas(VGroup):
    """Elementos en cajitas con una etiqueta ('cola', 'pila'). `vertical=True` apila hacia arriba."""

    def __init__(self, etiqueta: str = "cola", items: list[str] = (), vertical: bool = False,
                 tamano: float = 24, separacion: float = 0.18):
        super().__init__()
        self.vertical, self.tamano, self.sep = vertical, tamano, separacion
        self.etiqueta = nota(etiqueta, tamano * 1.3)
        self.add(self.etiqueta)
        self.cajas: list[VGroup] = []
        for item in items:
            caja = self._caja(item)
            self.cajas.append(caja)
            self.add(caja)
        self._ordenar(self.cajas)

    def _caja(self, contenido: str) -> VGroup:
        letras = mono(str(contenido), tamano=self.tamano)
        marco = RoundedRectangle(corner_radius=0.08, width=letras.width + 0.36, height=letras.height + 0.36,
                                 stroke_color=e.GRIS, stroke_width=2.5)
        marco.move_to(letras)
        return VGroup(marco, letras)

    def _posiciones(self, cajas: list[VGroup]) -> list[np.ndarray]:
        posiciones = []
        if self.vertical:
            y = self.etiqueta.get_top()[1] + 0.25
            for caja in cajas:
                posiciones.append(np.array([self.etiqueta.get_center()[0], y + caja.height / 2, 0]))
                y += caja.height + self.sep
        else:
            x = self.etiqueta.get_right()[0] + 0.3
            for caja in cajas:
                posiciones.append(np.array([x + caja.width / 2, self.etiqueta.get_center()[1], 0]))
                x += caja.width + self.sep
        return posiciones

    def _ordenar(self, cajas: list[VGroup]) -> None:
        for caja, punto in zip(cajas, self._posiciones(cajas)):
            caja.move_to(punto)

    def _reacomodo(self, cajas: list[VGroup]) -> list:
        return [c.animate.move_to(p) for c, p in zip(cajas, self._posiciones(cajas))
                if np.linalg.norm(c.get_center() - p) > 1e-3]

    def meter(self, contenido: str) -> AnimationGroup:
        caja = self._caja(contenido)
        caja.move_to(self._posiciones(self.cajas + [caja])[-1])
        self.cajas.append(caja)
        self.add(caja)
        return AnimationGroup(FadeIn(caja, shift=(DOWN if self.vertical else LEFT) * 0.3))

    def sacar(self, indice: int = 0) -> AnimationGroup:
        """Saca el elemento `indice` (0 = el primero de la cola; -1 = el tope de la pila)."""
        caja = self.cajas.pop(indice)
        self.remove(caja)
        return AnimationGroup(FadeOut(caja, shift=(RIGHT if self.vertical else UP) * 0.4), *self._reacomodo(self.cajas))

    def tachar(self, indice: int) -> AnimationGroup:
        """Tacha una entrada vieja (sigue en la cola, pero ya no sirve)."""
        caja = self.cajas[indice]
        linea = tachar(caja)
        caja.add(linea)
        return AnimationGroup(Create(linea), caja[1].animate.set_opacity(0.5))

    def resaltar(self, indice: int, color: str = e.AZUL) -> AnimationGroup:
        return AnimationGroup(self.cajas[indice][0].animate.set_stroke(color, width=4))

    def normal(self) -> AnimationGroup:
        return AnimationGroup(*[c[0].animate.set_stroke(e.GRIS, width=2.5) for c in self.cajas])

    def reemplazar(self, items: list[str]) -> AnimationGroup:
        """Pone exactamente estos elementos (útil cuando la traza trae la lista completa)."""
        salen = [FadeOut(c) for c in self.cajas]
        for c in self.cajas:
            self.remove(c)
        self.cajas = [self._caja(i) for i in items]
        self._ordenar(self.cajas)
        self.add(*self.cajas)
        entran = [FadeIn(c, shift=UP * 0.1) for c in self.cajas]
        return AnimationGroup(AnimationGroup(*salen), AnimationGroup(*entran), lag_ratio=0.4)


def Cola(items: list[str] = (), etiqueta: str = "cola", **kw) -> FilaCajas:
    return FilaCajas(etiqueta, items, vertical=False, **kw)


def Pila(items: list[str] = (), etiqueta: str = "pila", **kw) -> FilaCajas:
    return FilaCajas(etiqueta, items, vertical=True, **kw)
