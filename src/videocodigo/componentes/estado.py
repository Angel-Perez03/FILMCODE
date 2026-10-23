"""Tabla 'estado del programa': una fila por variable, con los valores que va tomando."""

from __future__ import annotations

import numpy as np
from manim import DOWN, LEFT, AnimationGroup, FadeIn, FadeOut, Transform, VectorizedPoint, VGroup

from .. import estilo as e
from .textos import medidas_mono, mono, nota


class TablaEstado(VGroup):
    """`actualizar({"dist": "0 4 2 ∞"})` cambia valores; lo que cambió queda en azul hasta el siguiente paso."""

    def __init__(self, filas: list[str] | dict[str, str], titulo: str = "estado del programa",
                 tamano: float = e.TAM_ESTADO, interlineado: float = 2.0, reserva: int = 0):
        """`reserva` = caracteres del valor más largo que se va a mostrar, para medir bien el ancho."""
        super().__init__()
        iniciales = dict(filas) if isinstance(filas, dict) else {f: "" for f in filas}
        self.tamano = tamano
        ancho_letra, alto = medidas_mono(tamano)
        self._alto_original = alto
        paso = alto * interlineado
        x_valor = (max(len(f) for f in iniciales) + 3) * ancho_letra
        self.encabezado = nota(titulo, tamano * 1.4)
        self.encabezado.move_to(np.array([0, paso * 0.9, 0]), aligned_edge=LEFT)
        self.add(self.encabezado)
        self.etiquetas, self.valores, self._anclas = {}, {}, {}
        for i, (fila, valor) in enumerate(iniciales.items()):
            y = -i * paso
            self.etiquetas[fila] = mono(fila, np.array([0, y, 0]), tamano, e.TEXTO_SUAVE)
            self._anclas[fila] = VectorizedPoint(np.array([x_valor, y, 0]))
            self.valores[fila] = mono(valor, np.array([x_valor, y, 0]), tamano) if valor else VGroup()
            self.add(self.etiquetas[fila], self._anclas[fila], self.valores[fila])
        self._regla = [VectorizedPoint(np.zeros(3)), VectorizedPoint(np.array([0, -alto, 0]))]
        self.add(*self._regla)
        if reserva:
            self.add(VectorizedPoint(np.array([x_valor + reserva * ancho_letra, 0, 0])))
        self._azules: set[str] = set()

    def _tamano_actual(self) -> float:
        alto = self._regla[0].get_center()[1] - self._regla[1].get_center()[1]
        return self.tamano * alto / self._alto_original

    def actualizar(self, cambios: dict[str, str], resaltar: bool = True) -> AnimationGroup:
        anims = []
        for fila, valor in cambios.items():
            if fila not in self.valores:
                raise KeyError(f"La tabla no tiene la fila {fila!r}. Filas: {list(self.valores)}")
            viejo = self.valores[fila]
            color = e.AZUL if resaltar else e.TEXTO
            if not valor:
                if len(viejo):
                    anims.append(FadeOut(viejo))
                    self.remove(viejo)
                    self.valores[fila] = VGroup()
                    self.add(self.valores[fila])
                continue
            nuevo = mono(valor, self._anclas[fila].get_center(), self._tamano_actual(), color)
            if len(viejo):
                anims.append(Transform(viejo, nuevo))
            else:
                self.remove(viejo)
                self.valores[fila] = nuevo
                self.add(nuevo)
                anims.append(FadeIn(nuevo, shift=DOWN * 0.08))
        for fila in self._azules - set(cambios):
            if len(self.valores[fila]):
                anims.append(self.valores[fila].animate.set_color(e.TEXTO))
        self._azules = {f for f, v in cambios.items() if v} if resaltar else set()
        return AnimationGroup(*anims) if anims else AnimationGroup(*[])

    def valor(self, fila: str) -> VGroup:
        return self.valores[fila]
