"""Textos del estilo: tarjetas de sección, personajes, notas, sellos y texto monoespaciado alineado."""

from __future__ import annotations

import html
from functools import lru_cache

import numpy as np
from manim import (
    BOLD, DOWN, ITALIC, LEFT, NORMAL, ORIGIN, PI, SEMIBOLD, UL, UP, UR,
    AnimationGroup, Create, FadeIn, FadeOut, Line, MarkupText, Rectangle, Text, VGroup, VMobject,
)

from .. import estilo as e


@lru_cache(maxsize=64)
def _texto_corto(contenido: str, tamano: float, color: str, cursiva: bool, peso: str, fuente: str) -> Text:
    """Plantilla privada: nunca se entrega al objeto que la animará."""
    return Text(contenido, font=fuente, font_size=tamano, color=color,
                slant=ITALIC if cursiva else NORMAL, weight=peso)


def texto(contenido: str, tamano: float = e.TAM_TEXTO, color: str = e.TEXTO,
          cursiva: bool = False, peso: str = NORMAL, fuente: str = e.FUENTE) -> Text:
    # Las etiquetas y los prefijos usados al medir líneas se repiten. Cada
    # llamada recibe su copia para que moverla, colorearla o animarla sea local.
    if len(contenido) <= 80:
        return _texto_corto(contenido, tamano, color, cursiva, peso, fuente).copy()
    return Text(contenido, font=fuente, font_size=tamano, color=color,
                slant=ITALIC if cursiva else NORMAL, weight=peso)


def mono(contenido: str, punto=ORIGIN, tamano: float = e.TAM_CODIGO, color: str = e.TEXTO,
         markup: bool = False) -> VMobject:
    """Texto en Consolas cuya esquina superior izquierda de una 'M' invisible cae en `punto`.

    Así todas las líneas comparten línea base y la sangría se conserva, aunque la línea
    empiece con espacios o no tenga letras altas.
    """
    cuerpo = contenido if markup else html.escape(contenido, quote=False)
    if markup:
        t = MarkupText("M" + cuerpo, font=e.FUENTE_CODIGO, font_size=tamano)
    else:
        t = MarkupText(f'<span foreground="{color}">M{cuerpo}</span>', font=e.FUENTE_CODIGO, font_size=tamano)
    ancla = t[0]
    t.shift(np.array(punto) - ancla.get_corner(UL))
    t.remove(ancla)
    return t


def medidas_mono(tamano: float = e.TAM_CODIGO) -> tuple[float, float]:
    """(ancho de un carácter, alto de mayúscula) de Consolas al tamaño dado."""
    return _medidas_mono(e.FUENTE_CODIGO, tamano)


@lru_cache(maxsize=32)
def _medidas_mono(fuente: str, tamano: float) -> tuple[float, float]:
    muestra = Text("M" * 20, font=fuente, font_size=tamano)
    return muestra.width / 20, Text("M", font=fuente, font_size=tamano).height


class TarjetaSeccion(VGroup):
    """'EL CÓDIGO' pequeño en gris, título grande y una línea azul debajo."""

    def __init__(self, titulo: str, antetitulo: str = "", tamano: float = e.TAM_TITULO):
        super().__init__()
        self.titulo = texto(titulo, tamano, e.TEXTO_SUAVE, peso=SEMIBOLD)
        if self.titulo.width > e.ANCHO_UTIL:
            self.titulo.scale_to_fit_width(e.ANCHO_UTIL)
        partes = [self.titulo]
        if antetitulo:
            self.antetitulo = texto(antetitulo.upper(), e.TAM_ANTETITULO, e.GRIS)
            partes.insert(0, self.antetitulo)
        self.linea = Line(LEFT, LEFT + 2 * np.array([1, 0, 0]), color=e.AZUL_LINEA, stroke_width=5)
        self.linea.set_width(min(self.titulo.width * 0.32, 4.0))
        partes.append(self.linea)
        self.add(*partes)
        self.arrange(DOWN, buff=0.32)

    def entrar(self) -> AnimationGroup:
        return AnimationGroup(FadeIn(VGroup(*self[:-1]), shift=UP * 0.15), Create(self.linea), lag_ratio=0.3)

    def salir(self) -> FadeOut:
        return FadeOut(self, shift=UP * 0.15)


class Personaje(VGroup):
    """Nombre en azul y lugar o detalle en cursiva gris, pensado para la esquina superior izquierda."""

    def __init__(self, nombre: str, detalle: str = ""):
        super().__init__()
        self.nombre = texto(nombre, 40, e.AZUL, peso=SEMIBOLD)
        self.add(self.nombre)
        if detalle:
            self.detalle = texto(detalle, e.TAM_NOTA, e.GRIS, cursiva=True)
            self.add(self.detalle)
        self.arrange(DOWN, buff=0.12, aligned_edge=LEFT)

    def esquina(self) -> Personaje:
        return self.to_corner(UL, buff=e.MARGEN)


def nota(contenido: str, tamano: float = e.TAM_NOTA, color: str = e.GRIS) -> Text:
    """Comentario en cursiva gris, como 'distancia desde A' o '(a veces escondidas con letra blanca)'."""
    return texto(contenido, tamano, color, cursiva=True)


def frase(contenido: str, tamano: float = e.TAM_FRASE, color: str = e.TEXTO, ancho: float = e.ANCHO_UTIL) -> VGroup:
    """Frase centrada que se parte en varias líneas si no cabe a lo ancho."""
    palabras, lineas, actual = contenido.split(), [], ""
    for palabra in palabras:
        prueba = f"{actual} {palabra}".strip()
        if actual and texto(prueba, tamano, color).width > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = prueba
    if actual:
        lineas.append(actual)
    return VGroup(*[texto(l, tamano, color) for l in lineas]).arrange(DOWN, buff=0.25)


def cifra(contenido: str, color: str = e.AZUL, tamano: float = 72) -> Text:
    """Número protagonista ('1956', '13', '85 %')."""
    return texto(contenido, tamano, color, peso=BOLD)


def formula(contenido: str, tamano: float = 36, color: str = e.TEXTO) -> Text:
    """Fórmula escrita con Cambria Math (no hace falta LaTeX)."""
    return Text(contenido, font=e.FUENTE_MATE, font_size=tamano, color=color)


class Sello(VGroup):
    """Sello rojo inclinado ('NEGATIVO', 'O(n²)', 'ERROR')."""

    def __init__(self, contenido: str, color: str = e.ROJO, tamano: float = 34):
        super().__init__()
        letras = texto(contenido.upper(), tamano, color, peso=BOLD)
        marco = Rectangle(width=letras.width + 0.45, height=letras.height + 0.35, color=color, stroke_width=4)
        self.add(marco, letras)
        self.rotate(PI / 20)

    def entrar(self) -> FadeIn:
        return FadeIn(self, scale=1.6)


def tachar(objetivo: VMobject, color: str = e.ROJO, grosor: float = 4) -> Line:
    """Línea diagonal sobre un objeto; anímala con Create(...)."""
    return Line(objetivo.get_corner(DOWN + LEFT), objetivo.get_corner(UR), color=color, stroke_width=grosor)


class ListaPuntos(VGroup):
    """Lista de ideas cortas que aparecen una a una (`mostrar(i)`)."""

    def __init__(self, items: list[str], tamano: float = e.TAM_TEXTO, color: str = e.TEXTO):
        super().__init__()
        for item in items:
            punto = texto("•", tamano, e.AZUL)
            linea = VGroup(punto, texto(item, tamano, color)).arrange(np.array([1, 0, 0]), buff=0.25)
            self.add(linea)
        self.arrange(DOWN, buff=0.35, aligned_edge=LEFT)
        for linea in self:
            if linea.width > e.ANCHO_UTIL:
                linea.scale_to_fit_width(e.ANCHO_UTIL)

    def mostrar(self, i: int) -> FadeIn:
        return FadeIn(self[i], shift=np.array([0.2, 0, 0]))
