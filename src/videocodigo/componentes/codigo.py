"""Panel de código con números de línea, sintaxis apagada y barra azul sobre la línea activa."""

from __future__ import annotations

import html
from pathlib import Path

import numpy as np
from manim import (
    LEFT, RIGHT, UR, AnimationGroup, FadeIn, LaggedStart, Rectangle, Transform, VectorizedPoint, VGroup,
)
from pygments import lex
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename
from pygments.token import Comment, Keyword, Name, Number, Operator, Punctuation, String
from pygments.util import ClassNotFound

from .. import estilo as e
from .textos import medidas_mono, mono, nota

MAX_LINEAS = e.MAX_LINEAS


def _color(token) -> str:
    s = e.SINTAXIS
    if token in Comment:
        return s["comentario"]
    if token in Keyword:
        return s["palabra_clave"]
    if token in String:
        return s["cadena"]
    if token in Number:
        return s["numero"]
    if token in Name.Builtin:
        return s["builtin"]
    if token in Name.Function or token in Name.Class:
        return s["funcion"]
    if token in Operator or token in Punctuation:
        return s["operador"]
    return s["nombre"]


def _lexer(lenguaje: str | None, archivo: str | None):
    try:
        if lenguaje:
            return get_lexer_by_name(lenguaje, stripnl=False, ensurenl=False)
        if archivo:
            return get_lexer_for_filename(archivo, stripnl=False, ensurenl=False)
    except ClassNotFound:
        pass
    return get_lexer_by_name("text", stripnl=False, ensurenl=False)


def lineas_coloreadas(codigo: str, lenguaje: str | None = None, archivo: str | None = None) -> list[str]:
    """Devuelve una línea de Pango markup por cada línea de código."""
    lineas = [""]
    for token, valor in lex(codigo.expandtabs(4), _lexer(lenguaje, archivo)):
        color = _color(token)
        for i, pedazo in enumerate(valor.split("\n")):
            if i:
                lineas.append("")
            if pedazo:
                lineas[-1] += f'<span foreground="{color}">{html.escape(pedazo, quote=False)}</span>'
    if len(lineas) > 1 and lineas[-1] == "" and codigo.endswith("\n"):
        lineas.pop()
    return lineas


class PanelCodigo(VGroup):
    """Código listo para recorrer línea a línea.

    `resaltar(n)` mueve la barra a la línea n (numeración real del archivo) y atenúa el resto.
    """

    def __init__(self, codigo: str, lenguaje: str | None = None, primera_linea: int = 1,
                 tamano: float = e.TAM_CODIGO, interlineado: float = 1.75, atenuado: float = 0.55,
                 archivo: str | None = None, titulo: str | None = None):
        super().__init__()
        texto_lineas = codigo.expandtabs(4).rstrip("\n").split("\n")
        if len(texto_lineas) > MAX_LINEAS:
            raise ValueError(f"El fragmento tiene {len(texto_lineas)} líneas; parte en trozos de {MAX_LINEAS} o menos.")
        self.primera, self.atenuado = primera_linea, atenuado
        ancho_letra, alto = medidas_mono(tamano)
        self.paso, self.alto_letra = alto * interlineado, alto
        marcadas = lineas_coloreadas("\n".join(texto_lineas), lenguaje, archivo)
        digitos = len(str(primera_linea + len(texto_lineas) - 1))
        x_codigo = (digitos + 1.5) * ancho_letra
        largo = max((len(l) for l in texto_lineas), default=1)
        self.ancho_codigo = largo * ancho_letra

        self.lineas, self.numeros, self.anclas = [], [], []
        for i, marcada in enumerate(marcadas):
            punto = np.array([x_codigo, -i * self.paso, 0])
            self.lineas.append(mono(marcada, punto, tamano, markup=True))
            numero = str(primera_linea + i).rjust(digitos)
            self.numeros.append(mono(numero, np.array([0, -i * self.paso, 0]), tamano, color="#5A5E66"))
            self.anclas.append(VectorizedPoint(punto))

        izquierda, derecha = -0.15, x_codigo + self.ancho_codigo + 0.3
        self.barra = Rectangle(width=derecha - izquierda, height=self.paso * 0.95, stroke_width=0)
        self.barra.set_fill(e.AZUL_OSCURO, opacity=0)
        self.barra.move_to(np.array([(izquierda + derecha) / 2, -alto / 2, 0]))
        # Regla invisible: escala con el grupo y da el interlineado y el alto de letra actuales
        self._regla = [VectorizedPoint(np.zeros(3)), VectorizedPoint(np.array([0, -self.paso, 0])),
                       VectorizedPoint(np.array([0, -alto, 0]))]
        self.add(self.barra, *self.numeros, *self.lineas, *self.anclas, *self._regla)
        if titulo:
            self.titulo = nota(titulo, 24)
            self.titulo.next_to(VGroup(*self.numeros, *self.lineas), np.array([0, 1, 0]), buff=0.35, aligned_edge=LEFT)
            self.add(self.titulo)
        for linea in self.lineas:
            linea.set_opacity(atenuado)
        self.move_to(np.zeros(3))

    @classmethod
    def desde_archivo(cls, ruta: str | Path, desde: int = 1, hasta: int | None = None, **kw) -> PanelCodigo:
        lineas = Path(ruta).read_text(encoding="utf-8").splitlines()
        hasta = hasta or len(lineas)
        kw.setdefault("archivo", str(ruta))
        return cls("\n".join(lineas[desde - 1:hasta]), primera_linea=desde, **kw)

    @property
    def ultima(self) -> int:
        return self.primera + len(self.lineas) - 1

    def _indice(self, n: int) -> int:
        if not self.primera <= n <= self.ultima:
            raise ValueError(f"La línea {n} no está en el panel ({self.primera}–{self.ultima}).")
        return n - self.primera

    def linea(self, n: int) -> VGroup:
        return self.lineas[self._indice(n)]

    def mostrar(self) -> LaggedStart:
        filas = [VGroup(num, lin) for num, lin in zip(self.numeros, self.lineas)]
        return LaggedStart(*[FadeIn(f, shift=RIGHT * 0.15) for f in filas], lag_ratio=0.04)

    def _medidas(self) -> tuple[float, float]:
        y0, y1, y2 = (p.get_center()[1] for p in self._regla)
        return y0 - y1, y0 - y2

    def _barra_para(self, a: int, b: int) -> Rectangle:
        paso, alto = self._medidas()
        arriba = self.anclas[a].get_center()[1] + (paso - alto) / 2
        abajo = self.anclas[b].get_center()[1] - alto - (paso - alto) / 2
        nueva = self.barra.copy().set_fill(e.AZUL_OSCURO, opacity=0.95)
        nueva.stretch_to_fit_height(arriba - abajo)
        nueva.move_to(np.array([self.barra.get_center()[0], (arriba + abajo) / 2, 0]))
        return nueva

    def resaltar(self, desde: int, hasta: int | None = None) -> AnimationGroup:
        a, b = self._indice(desde), self._indice(hasta or desde)
        a, b = min(a, b), max(a, b)
        anims = [Transform(self.barra, self._barra_para(a, b))]
        for i, linea in enumerate(self.lineas):
            anims.append(linea.animate.set_opacity(1.0 if a <= i <= b else self.atenuado))
        return AnimationGroup(*anims)

    def quitar_resaltado(self) -> AnimationGroup:
        anims = [self.barra.animate.set_fill(opacity=0)]
        anims += [linea.animate.set_opacity(self.atenuado) for linea in self.lineas]
        return AnimationGroup(*anims)

    def encender(self) -> AnimationGroup:
        """Todas las líneas a opacidad completa (para mostrar el código entero)."""
        return AnimationGroup(*[linea.animate.set_opacity(1.0) for linea in self.lineas])

    def ajustar(self, ancho: float, alto: float) -> PanelCodigo:
        """Escala el panel para que quepa en un área, sin agrandarlo."""
        factor = min(1.0, ancho / max(self.width, 1e-6), alto / max(self.height, 1e-6))
        if factor < 1.0:
            self.scale(factor)
        return self

    def esquina_derecha(self) -> np.ndarray:
        return VGroup(*self.lineas).get_corner(UR)
