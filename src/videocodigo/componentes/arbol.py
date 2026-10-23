"""Árboles (binarios o n-arios): búsqueda, recursión, montículos. Se ubican solos por niveles."""

from __future__ import annotations

import numpy as np
from manim import (
    BOLD, AnimationGroup, Circle, Create, GrowFromCenter, LaggedStart, Line, Succession, VGroup,
)

from .. import estilo as e
from .textos import texto


class Arbol(VGroup):
    """`raiz` = (valor, [hijos]) o (valor, izquierdo, derecho); un hijo None deja el hueco.

    Los nodos se nombran por su ruta: "r", "r0", "r01"… También `nodo(valor)` si el valor es único.
    """

    def __init__(self, raiz, radio: float = 0.36, sep_x: float = 0.95, sep_y: float = 1.25, tamano: float = 26):
        super().__init__()
        self.radio = radio
        self.circulos, self.letras, self.lineas, self.padre = {}, {}, {}, {}
        self._por_valor: dict[str, list[str]] = {}
        posiciones, cursor = {}, [0]

        def hijos_de(nodo):
            if len(nodo) == 2 and isinstance(nodo[1], (list, tuple)) and not _es_nodo(nodo[1]):
                return list(nodo[1])
            return list(nodo[1:])

        def ubicar(nodo, ruta: str, nivel: int) -> float | None:
            if nodo is None:
                cursor[0] += 1
                return None
            if not isinstance(nodo, (list, tuple)):
                nodo = (nodo, [])
            hijos = hijos_de(nodo)
            xs = [ubicar(h, f"{ruta}{i}", nivel + 1) for i, h in enumerate(hijos)]
            xs = [x for x in xs if x is not None]
            if xs:
                x = (min(xs) + max(xs)) / 2
            else:
                x = cursor[0]
                cursor[0] += 1
            posiciones[ruta] = (x, nivel, str(nodo[0]))
            for i, h in enumerate(hijos):
                if h is not None:
                    self.padre[f"{ruta}{i}"] = ruta
            return x

        ubicar(raiz, "r", 0)
        ancho = max(p[0] for p in posiciones.values()) or 1
        for ruta, (x, nivel, valor) in posiciones.items():
            punto = np.array([(x - ancho / 2) * sep_x, -nivel * sep_y, 0])
            self.circulos[ruta] = Circle(radius=radio, color=e.TEXTO, stroke_width=3).set_fill(e.FONDO, 1).move_to(punto)
            letra = texto(valor, tamano, e.TEXTO, peso=BOLD).move_to(punto)
            if letra.width > radio * 1.6:
                letra.scale_to_fit_width(radio * 1.6)
            self.letras[ruta] = letra
            self._por_valor.setdefault(valor, []).append(ruta)
        for hijo, padre in self.padre.items():
            a, b = self.circulos[padre].get_center(), self.circulos[hijo].get_center()
            d = (b - a) / np.linalg.norm(b - a)
            self.lineas[hijo] = Line(a + d * radio, b - d * radio, color=e.GRIS_ARISTA, stroke_width=3)
        self.add(*self.lineas.values())
        for ruta in self.circulos:
            self.add(self.circulos[ruta], self.letras[ruta])
        self.move_to(np.zeros(3))

    def _ruta(self, clave: str) -> str:
        if clave in self.circulos:
            return clave
        rutas = self._por_valor.get(str(clave), [])
        if len(rutas) != 1:
            raise KeyError(f"No hay un único nodo con valor {clave!r}; usa su ruta ('r', 'r0'…).")
        return rutas[0]

    def nodo(self, clave: str) -> VGroup:
        r = self._ruta(clave)
        return VGroup(self.circulos[r], self.letras[r])

    def aparecer(self) -> AnimationGroup:
        orden = sorted(self.circulos, key=len)
        return AnimationGroup(LaggedStart(*[GrowFromCenter(VGroup(self.circulos[r], self.letras[r])) for r in orden],
                                          lag_ratio=0.1),
                              LaggedStart(*[Create(self.lineas[r]) for r in orden if r in self.lineas], lag_ratio=0.1),
                              lag_ratio=0.4)

    def resaltar(self, clave: str, color: str = e.AZUL) -> AnimationGroup:
        r = self._ruta(clave)
        return AnimationGroup(self.circulos[r].animate.set_fill(color, 1).set_stroke(color),
                              self.letras[r].animate.set_color(e.FONDO))

    def normal(self) -> AnimationGroup:
        return AnimationGroup(*[c.animate.set_fill(e.FONDO, 1).set_stroke(e.TEXTO) for c in self.circulos.values()],
                              *[l.animate.set_color(e.TEXTO) for l in self.letras.values()])

    def camino(self, claves: list[str], color: str = e.ROJO) -> Succession:
        """Resalta nodo por nodo, por ejemplo la búsqueda de un valor desde la raíz."""
        pasos = []
        for clave in claves:
            r = self._ruta(clave)
            anims = [self.circulos[r].animate.set_stroke(color, width=5)]
            if r in self.lineas:
                anims.append(self.lineas[r].animate.set_stroke(color, width=5))
            pasos.append(AnimationGroup(*anims))
        return Succession(*pasos)


def _es_nodo(valor) -> bool:
    return isinstance(valor, (list, tuple)) and len(valor) >= 1 and not isinstance(valor[0], (list, tuple))
