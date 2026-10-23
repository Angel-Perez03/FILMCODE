"""Piezas con más movimiento: tarjetas con ícono, pila de capas, piezas que se instalan, lista con
marcas de verificación y frases que aparecen palabra por palabra."""

from __future__ import annotations

import html
import re

import numpy as np
from manim import (
    DOWN, LEFT, ORIGIN, RIGHT, SEMIBOLD, UP, AnimationGroup, Circle, FadeIn, FadeOut, LaggedStart, MarkupText,
    RoundedRectangle, Transform, VGroup,
)

from .. import estilo as e
from .iconos import icono
from .textos import texto

FONDO_TARJETA = "#0F1724"
BORDE_TARJETA = "#2B3A52"


class Tarjeta(VGroup):
    """Tarjeta oscura con ícono arriba, título y detalle (por ejemplo 'Docker Hub' / 'registro de imágenes')."""

    def __init__(self, titulo: str, nombre_icono: str | None = None, detalle: str | None = None,
                 ancho: float = 2.7, alto: float | None = None, color: str = e.AZUL):
        super().__init__()
        partes = []
        if nombre_icono:
            partes.append(icono(nombre_icono, color, 0.75))
        titulo_m = texto(titulo, 26, e.TEXTO)
        if titulo_m.width > ancho - 0.35:
            titulo_m.scale_to_fit_width(ancho - 0.35)
        partes.append(titulo_m)
        if detalle:
            detalle_m = texto(detalle, 18, e.GRIS, fuente=e.FUENTE_CODIGO)
            if detalle_m.width > ancho - 0.35:
                detalle_m.scale_to_fit_width(ancho - 0.35)
            partes.append(detalle_m)
        contenido = VGroup(*partes).arrange(DOWN, buff=0.18)
        alto = alto or contenido.height + 0.6
        self.marco = RoundedRectangle(corner_radius=0.2, width=ancho, height=alto, stroke_color=BORDE_TARJETA,
                                      stroke_width=2).set_fill(FONDO_TARJETA, opacity=0.92)
        self.add(self.marco, contenido.move_to(self.marco))
        self.contenido = contenido

    def encender(self, color: str = e.AZUL) -> AnimationGroup:
        return AnimationGroup(self.marco.animate.set_stroke(color, width=4), self.contenido.animate.scale(1.06))

    def apagar(self) -> AnimationGroup:
        return AnimationGroup(self.marco.animate.set_stroke(BORDE_TARJETA, width=2), self.contenido.animate.scale(1 / 1.06))


class Capas(VGroup):
    """Pila de capas de abajo hacia arriba (hardware → sistema → … → aplicación)."""

    def __init__(self, capas: list[dict], ancho: float = 8.5, alto: float = 0.82, separacion: float = 0.16):
        super().__init__()
        self.capas = []
        for k, capa in enumerate(capas):
            fuerza = 0.18 + 0.5 * k / max(len(capas) - 1, 1)
            barra = RoundedRectangle(corner_radius=0.16, width=ancho, height=alto, stroke_color=e.AZUL,
                                     stroke_width=1.5).set_fill(e.AZUL, opacity=fuerza * 0.55)
            fila = [texto(capa["titulo"], 28, e.TEXTO)]
            if capa.get("icono"):
                fila.insert(0, icono(capa["icono"], e.TEXTO, 0.55))
            izquierda = VGroup(*fila).arrange(RIGHT, buff=0.3)
            izquierda.move_to(barra).align_to(barra, LEFT).shift(RIGHT * 0.35)
            grupo = VGroup(barra, izquierda)
            if capa.get("detalle"):
                grupo.add(texto(capa["detalle"], 20, e.TEXTO_SUAVE, cursiva=True).move_to(barra).align_to(barra, RIGHT)
                          .shift(LEFT * 0.35))
            grupo.move_to(np.array([0, k * (alto + separacion), 0]))
            self.capas.append(grupo)
            self.add(grupo)
        self.move_to(ORIGIN)

    def construir(self) -> LaggedStart:
        return LaggedStart(*[FadeIn(c, shift=DOWN * 0.35) for c in self.capas], lag_ratio=0.35)

    def mostrar(self, i: int) -> FadeIn:
        return FadeIn(self.capas[i], shift=DOWN * 0.35)

    def resaltar(self, i: int) -> AnimationGroup:
        anims = []
        for k, capa in enumerate(self.capas):
            anims.append(capa[0].animate.set_stroke(e.AZUL if k != i else e.TEXTO, width=1.5 if k != i else 4))
            anims.append(capa.animate.set_opacity(1 if k == i else 0.45))
        return AnimationGroup(*anims)

    def normal(self) -> AnimationGroup:
        return AnimationGroup(*[c.animate.set_opacity(1) for c in self.capas],
                              *[c[0].animate.set_stroke(e.AZUL, width=1.5) for c in self.capas])


class Piezas(VGroup):
    """Tarjetas en fila o en rejilla que aparecen una a una y pueden 'instalarse' en un destino."""

    def __init__(self, items: list[dict], columnas: int = 5, ancho_tarjeta: float = 2.4):
        super().__init__()
        self.tarjetas = [Tarjeta(i["titulo"], i.get("icono"), i.get("detalle"), ancho=ancho_tarjeta) for i in items]
        alto = max(t.height for t in self.tarjetas)
        for k, t in enumerate(self.tarjetas):
            fila, col = divmod(k, columnas)
            en_fila = min(columnas, len(self.tarjetas) - fila * columnas)
            x = (col - (en_fila - 1) / 2) * (ancho_tarjeta + 0.3)
            t.move_to(np.array([x, -fila * (alto + 0.3), 0]))
            self.add(t)
        self.move_to(ORIGIN)

    def mostrar(self, i: int) -> FadeIn:
        return FadeIn(self.tarjetas[i], scale=0.8, shift=UP * 0.2)

    def instalar(self, destino) -> AnimationGroup:
        """Todas las tarjetas viajan hacia `destino` y se encogen (se 'instalan')."""
        punto = destino.get_center()
        return AnimationGroup(*[t.animate.scale(0.15).move_to(punto).set_opacity(0) for t in self.tarjetas],
                              lag_ratio=0.08)


class ListaCheck(VGroup):
    """Lista con un círculo por ítem que se convierte en ✓ al narrarlo."""

    def __init__(self, items: list[str], tamano: float = 36, ancho: float = e.ANCHO_UTIL - 1):
        super().__init__()
        self.circulos, self.textos, self.filas = [], [], []
        for item in items:
            circulo = Circle(radius=0.17, color=e.GRIS, stroke_width=3)
            letras = texto(item, tamano, e.GRIS)
            if letras.width > ancho - 0.8:
                letras.scale_to_fit_width(ancho - 0.8)
            fila = VGroup(circulo, letras).arrange(RIGHT, buff=0.35)
            self.circulos.append(circulo)
            self.textos.append(letras)
            self.filas.append(fila)
            self.add(fila)
        self.arrange(DOWN, buff=0.32, aligned_edge=LEFT)

    def mostrar(self, i: int) -> FadeIn:
        return FadeIn(self.filas[i], shift=RIGHT * 0.2)

    def marcar(self, i: int) -> AnimationGroup:
        marca = icono("check", e.VERDE, 0.42).move_to(self.circulos[i])
        return AnimationGroup(Transform(self.circulos[i], marca), self.textos[i].animate.set_color(e.TEXTO))


class FraseCinetica(VGroup):
    """Frase centrada que aparece palabra por palabra; lo que va entre *asteriscos* sale en azul."""

    def __init__(self, contenido: str, tamano: float = e.TAM_FRASE, ancho: float = e.ANCHO_UTIL,
                 color: str = e.TEXTO, color_enfasis: str = e.AZUL):
        super().__init__()
        palabras: list[tuple[str, bool]] = []
        for k, trozo in enumerate(re.split(r"\*([^*]+)\*", contenido)):
            for j, p in enumerate(trozo.split()):
                # Puntuación pegada al énfasis anterior ("*necesita*, en") va con la palabra previa, sin espacio
                if j == 0 and palabras and not trozo[:1].isspace() and re.match(r"^[,.;:!?…)»]", p):
                    previa, enfasis = palabras[-1]
                    palabras[-1] = (previa + p, enfasis)
                    continue
                palabras.append((p, bool(k % 2)))
        self.texto_plano = " ".join(p for p, _ in palabras)
        lineas, actual = [], []
        for palabra in palabras:
            prueba = " ".join(p for p, _ in actual + [palabra])
            if actual and texto(prueba, tamano).width > ancho:
                lineas.append(actual)
                actual = [palabra]
            else:
                actual.append(palabra)
        if actual:
            lineas.append(actual)
        self.palabras: list[VGroup] = []
        for linea in lineas:
            marcado = " ".join(f'<span foreground="{color_enfasis if enf else color}">{html.escape(p, quote=False)}</span>'
                               for p, enf in linea)
            m = MarkupText(f'<span font_features="liga=0,clig=0">{marcado}</span>', font=e.FUENTE, font_size=tamano,
                           weight=SEMIBOLD)
            esperados = sum(len(p.replace(" ", "")) for p, _ in linea)
            if len(m) == esperados:
                k = 0
                for p, _ in linea:
                    n = len(p.replace(" ", ""))
                    self.palabras.append(VGroup(*m[k:k + n]))
                    k += n
            else:
                self.palabras.append(VGroup(*m))
            self.add(m)
        self.arrange(DOWN, buff=0.25)

    def revelar(self) -> LaggedStart:
        return LaggedStart(*[FadeIn(p, shift=UP * 0.12) for p in self.palabras], lag_ratio=0.6)
