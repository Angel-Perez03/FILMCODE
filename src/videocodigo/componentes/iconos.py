"""Íconos vectoriales dibujados con primitivas de Manim (sin archivos externos).

`icono("contenedor")` devuelve un VGroup de 1 × 1 unidades centrado en el origen. `NOMBRES` es la
lista que se le ofrece al modelo para que elija el ícono adecuado a cada idea.
"""

from __future__ import annotations

import numpy as np
from manim import (
    DOWN, LEFT, PI, RIGHT, UP, Arc, Circle, Dot, Ellipse, Line, Polygon, Rectangle, RoundedRectangle,
    Square, Text, Union, VGroup, VMobject,
)

from .. import estilo as e


def _p(x: float, y: float) -> np.ndarray:
    return np.array([x, y, 0.0])


def _trazo(m, color: str, ancho: float = 3.5, relleno: float = 0.0):
    m.set_stroke(color, width=ancho)
    m.set_fill(color, opacity=relleno)
    return m


def _contenedor(c):
    caja = _trazo(RoundedRectangle(corner_radius=0.06, width=1.0, height=0.58), c, relleno=0.12)
    costillas = VGroup(*[_trazo(Line(_p(x, -0.2), _p(x, 0.2)), c, 2.5) for x in np.linspace(-0.32, 0.32, 5)])
    return VGroup(caja, costillas)


def _ballena(c):
    cuerpo = VMobject()
    cuerpo.set_points_smoothly([_p(-0.62, 0.02), _p(0.3, 0.02), _p(0.47, 0.08), _p(0.6, 0.22), _p(0.66, 0.2),
                                _p(0.56, 0.04), _p(0.45, -0.12), _p(0.2, -0.3), _p(-0.15, -0.34),
                                _p(-0.47, -0.22), _p(-0.62, 0.02)])
    _trazo(cuerpo, c, relleno=0.18)
    bloques = VGroup()
    for fila, (y, xs) in enumerate([(0.13, [-0.43, -0.27, -0.11, 0.05, 0.21]), (0.29, [-0.27, -0.11, 0.05]),
                                   (0.45, [-0.11])]):
        for x in xs:
            bloques.add(_trazo(Square(side_length=0.13).move_to(_p(x, y)), c, 2.5, 0.35))
    ojo = Dot(_p(-0.44, -0.08), radius=0.03, color=c)
    return VGroup(cuerpo, bloques, ojo)


def _nube(c):
    forma = Union(Circle(0.26).move_to(_p(-0.26, -0.02)), Circle(0.33).move_to(_p(0.04, 0.1)),
                  Circle(0.23).move_to(_p(0.32, -0.04)), Rectangle(width=0.62, height=0.3).move_to(_p(0.02, -0.12)))
    return VGroup(_trazo(forma, c, relleno=0.12))


def _flecha_abajo(c, x=0.0, y=0.0, alto=0.5):
    asta = _trazo(Line(_p(x, y + alto / 2), _p(x, y - alto / 2 + 0.08)), c)
    punta = _trazo(Polygon(_p(x - 0.12, y - alto / 2 + 0.12), _p(x + 0.12, y - alto / 2 + 0.12), _p(x, y - alto / 2 - 0.05)), c, relleno=1)
    return VGroup(asta, punta)


def _registro(c):
    return VGroup(_nube(c).shift(UP * 0.12), _flecha_abajo(c, 0, -0.18, 0.42))


def _descarga(c):
    bandeja = _trazo(VMobject().set_points_as_corners([_p(-0.42, -0.1), _p(-0.42, -0.38), _p(0.42, -0.38), _p(0.42, -0.1)]), c)
    return VGroup(_flecha_abajo(c, 0, 0.12, 0.62), bandeja)


def _servidor(c):
    grupo = VGroup()
    for y in (0.3, 0.0, -0.3):
        grupo.add(_trazo(RoundedRectangle(corner_radius=0.05, width=0.92, height=0.24).move_to(_p(0, y)), c, relleno=0.1))
        grupo.add(Dot(_p(-0.32, y), radius=0.035, color=e.VERDE), _trazo(Line(_p(0.05, y), _p(0.32, y)), c, 2.5))
    return grupo


def _llave(c):
    aro = _trazo(Circle(0.17).move_to(_p(-0.3, 0)), c)
    hueco = _trazo(Circle(0.05).move_to(_p(-0.3, 0)), c, 2.5)
    asta = _trazo(Line(_p(-0.13, 0), _p(0.45, 0)), c)
    dientes = VGroup(_trazo(Line(_p(0.3, 0), _p(0.3, -0.14)), c), _trazo(Line(_p(0.42, 0), _p(0.42, -0.18)), c))
    return VGroup(aro, hueco, asta, dientes)


def _candado(c):
    cuerpo = _trazo(RoundedRectangle(corner_radius=0.08, width=0.7, height=0.5).move_to(_p(0, -0.15)), c, relleno=0.15)
    arco = _trazo(Arc(radius=0.22, start_angle=0, angle=PI).move_to(_p(0, 0.22)), c)
    patas = VGroup(_trazo(Line(_p(-0.22, 0.1), _p(-0.22, 0.2)), c), _trazo(Line(_p(0.22, 0.1), _p(0.22, 0.2)), c))
    ojo = Dot(_p(0, -0.15), radius=0.05, color=c)
    return VGroup(cuerpo, arco, patas, ojo)


def _escudo(c):
    forma = VMobject().set_points_smoothly([_p(0, 0.45), _p(0.38, 0.32), _p(0.36, -0.05), _p(0, -0.45),
                                            _p(-0.36, -0.05), _p(-0.38, 0.32), _p(0, 0.45)])
    marca = VMobject().set_points_as_corners([_p(-0.15, 0), _p(-0.03, -0.13), _p(0.17, 0.12)])
    return VGroup(_trazo(forma, c, relleno=0.12), _trazo(marca, c, 4))


def _usuario(c, x=0.0, escala=1.0):
    cabeza = _trazo(Circle(0.16 * escala).move_to(_p(x, 0.18 * escala)), c, relleno=0.15)
    hombros = _trazo(Arc(radius=0.3 * escala, start_angle=0, angle=PI).move_to(_p(x, -0.2 * escala)), c)
    base = _trazo(Line(_p(x - 0.3 * escala, -0.27 * escala), _p(x + 0.3 * escala, -0.27 * escala)), c)
    return VGroup(cabeza, hombros, base)


def _grupo(c):
    return VGroup(_usuario(c, -0.3, 0.7).set_opacity(0.6), _usuario(c, 0.3, 0.7).set_opacity(0.6), _usuario(c, 0, 0.9))


def _ventana(c, ancho=1.0, alto=0.72):
    marco = _trazo(RoundedRectangle(corner_radius=0.07, width=ancho, height=alto), c, relleno=0.08)
    barra = _trazo(Line(_p(-ancho / 2, alto / 2 - 0.16), _p(ancho / 2, alto / 2 - 0.16)), c, 2.5)
    puntos = VGroup(*[Dot(_p(-ancho / 2 + 0.1 + 0.08 * k, alto / 2 - 0.08), radius=0.025, color=c) for k in range(3)])
    return VGroup(marco, barra, puntos)


def _terminal(c):
    prompt = _trazo(VMobject().set_points_as_corners([_p(-0.3, 0.02), _p(-0.15, -0.08), _p(-0.3, -0.18)]), c, 4)
    cursor = _trazo(Line(_p(-0.08, -0.2), _p(0.15, -0.2)), c, 4)
    return VGroup(_ventana(c), prompt, cursor)


def _navegador(c):
    return VGroup(_ventana(c), *[_trazo(Line(_p(-0.35, y), _p(x, y)), c, 2.5) for y, x in ((0.0, 0.3), (-0.12, 0.1), (-0.24, 0.2))])


def _engranaje(c):
    puntos = []
    for k in range(32):
        angulo = 2 * PI * k / 32
        radio = 0.45 if (k // 2) % 2 == 0 else 0.34
        puntos.append(_p(radio * np.cos(angulo), radio * np.sin(angulo)))
    return VGroup(_trazo(Polygon(*puntos), c, relleno=0.12), _trazo(Circle(0.13), c))


def _base_datos(c):
    tapa = _trazo(Ellipse(width=0.8, height=0.24).move_to(_p(0, 0.3)), c, relleno=0.15)
    lados = VGroup(_trazo(Line(_p(-0.4, 0.3), _p(-0.4, -0.3)), c), _trazo(Line(_p(0.4, 0.3), _p(0.4, -0.3)), c))
    aros = VGroup(*[_trazo(Arc(radius=0.4, start_angle=PI, angle=PI).stretch(0.3, 1).move_to(_p(0, y)), c)
                    for y in (-0.0, -0.33)])
    return VGroup(tapa, lados, aros)


def _telefono(c):
    return VGroup(_trazo(RoundedRectangle(corner_radius=0.1, width=0.52, height=0.95), c, relleno=0.08),
                  _trazo(Line(_p(-0.08, 0.38), _p(0.08, 0.38)), c, 3))


def _portatil(c):
    pantalla = _trazo(RoundedRectangle(corner_radius=0.05, width=0.86, height=0.55).move_to(_p(0, 0.1)), c, relleno=0.08)
    base = _trazo(Polygon(_p(-0.55, -0.24), _p(0.55, -0.24), _p(0.48, -0.32), _p(-0.48, -0.32)), c, relleno=0.3)
    return VGroup(pantalla, base)


def _linux(c):
    cuerpo = Ellipse(width=0.62, height=0.82).move_to(_p(0, -0.05)).set_fill("#1A1A1A", 1).set_stroke(c, 3)
    panza = Ellipse(width=0.4, height=0.55).move_to(_p(0, -0.13)).set_fill("#F2F2F2", 1).set_stroke(width=0)
    ojos = VGroup(*[Dot(_p(x, 0.2), radius=0.04, color="#F2F2F2") for x in (-0.09, 0.09)])
    pico = Polygon(_p(-0.08, 0.12), _p(0.08, 0.12), _p(0, 0.02)).set_fill(e.AMARILLO, 1).set_stroke(width=0)
    patas = VGroup(*[Ellipse(width=0.22, height=0.09).move_to(_p(x, -0.45)).set_fill(e.AMARILLO, 1).set_stroke(width=0)
                     for x in (-0.14, 0.14)])
    return VGroup(cuerpo, panza, ojos, pico, patas)


def _windows(c):
    return VGroup(*[Square(side_length=0.36).move_to(_p(x, y)).set_fill(c, 0.9).set_stroke(width=0)
                    for x in (-0.2, 0.2) for y in (0.2, -0.2)])


def _paquete(c):
    frente = _trazo(Polygon(_p(-0.4, 0.1), _p(0, -0.08), _p(0, -0.48), _p(-0.4, -0.3)), c, relleno=0.15)
    lado = _trazo(Polygon(_p(0, -0.08), _p(0.4, 0.1), _p(0.4, -0.3), _p(0, -0.48)), c, relleno=0.3)
    tapa = _trazo(Polygon(_p(-0.4, 0.1), _p(0, 0.28), _p(0.4, 0.1), _p(0, -0.08)), c, relleno=0.05)
    return VGroup(frente, lado, tapa)


def _check(c):
    marca = VMobject().set_points_as_corners([_p(-0.2, 0), _p(-0.05, -0.15), _p(0.22, 0.14)])
    return VGroup(_trazo(Circle(0.42), e.VERDE if c == e.AZUL else c, relleno=0.15), _trazo(marca, e.VERDE if c == e.AZUL else c, 5))


def _alerta(c):
    color = e.AMARILLO if c == e.AZUL else c
    triangulo = _trazo(Polygon(_p(0, 0.42), _p(0.46, -0.36), _p(-0.46, -0.36)), color, relleno=0.12)
    signo = VGroup(_trazo(Line(_p(0, 0.15), _p(0, -0.12)), color, 5), Dot(_p(0, -0.24), radius=0.04, color=color))
    return VGroup(triangulo, signo)


def _codigo(c):
    izq = _trazo(VMobject().set_points_as_corners([_p(-0.2, 0.25), _p(-0.42, 0), _p(-0.2, -0.25)]), c, 4)
    der = _trazo(VMobject().set_points_as_corners([_p(0.2, 0.25), _p(0.42, 0), _p(0.2, -0.25)]), c, 4)
    barra = _trazo(Line(_p(0.08, 0.3), _p(-0.08, -0.3)), c, 4)
    return VGroup(izq, der, barra)


def _api(c):
    enchufe = _trazo(RoundedRectangle(corner_radius=0.06, width=0.4, height=0.34).move_to(_p(-0.12, 0)), c, relleno=0.15)
    patas = VGroup(*[_trazo(Line(_p(-0.32, y), _p(-0.45, y)), c) for y in (0.08, -0.08)])
    cable = _trazo(VMobject().set_points_smoothly([_p(0.08, 0), _p(0.25, 0.05), _p(0.35, -0.15), _p(0.48, -0.1)]), c)
    return VGroup(enchufe, patas, cable)


def _chip_ia(c):
    cuerpo = _trazo(RoundedRectangle(corner_radius=0.06, width=0.6, height=0.6), c, relleno=0.12)
    pines = VGroup()
    for k in np.linspace(-0.18, 0.18, 3):
        pines.add(_trazo(Line(_p(k, 0.3), _p(k, 0.42)), c, 2.5), _trazo(Line(_p(k, -0.3), _p(k, -0.42)), c, 2.5),
                  _trazo(Line(_p(0.3, k), _p(0.42, k)), c, 2.5), _trazo(Line(_p(-0.3, k), _p(-0.42, k)), c, 2.5))
    letras = Text("IA", font=e.FUENTE, font_size=26, color=c, weight="BOLD")
    return VGroup(cuerpo, pines, letras)


def _cohete(c):
    cuerpo = VMobject().set_points_smoothly([_p(0, 0.48), _p(0.16, 0.2), _p(0.16, -0.2), _p(-0.16, -0.2),
                                             _p(-0.16, 0.2), _p(0, 0.48)])
    alas = VGroup(_trazo(Polygon(_p(0.16, -0.05), _p(0.32, -0.28), _p(0.16, -0.2)), c, relleno=0.3),
                  _trazo(Polygon(_p(-0.16, -0.05), _p(-0.32, -0.28), _p(-0.16, -0.2)), c, relleno=0.3))
    fuego = Polygon(_p(-0.08, -0.22), _p(0.08, -0.22), _p(0, -0.45)).set_fill(e.AMARILLO, 0.9).set_stroke(width=0)
    return VGroup(_trazo(cuerpo, c, relleno=0.12), alas, fuego, _trazo(Circle(0.06).move_to(_p(0, 0.15)), c, 2.5))


def _carpeta(c):
    return VGroup(_trazo(Polygon(_p(-0.45, 0.25), _p(-0.15, 0.25), _p(-0.05, 0.15), _p(0.45, 0.15), _p(0.45, -0.32),
                                 _p(-0.45, -0.32)), c, relleno=0.15))


def _archivo(c):
    hoja = _trazo(Polygon(_p(-0.3, 0.42), _p(0.14, 0.42), _p(0.3, 0.26), _p(0.3, -0.42), _p(-0.3, -0.42)), c, relleno=0.08)
    lineas = VGroup(*[_trazo(Line(_p(-0.18, y), _p(0.18, y)), c, 2.5) for y in (0.1, -0.05, -0.2)])
    return VGroup(hoja, lineas)


def _reloj(c):
    return VGroup(_trazo(Circle(0.42), c, relleno=0.1), _trazo(Line(_p(0, 0), _p(0, 0.27)), c, 4),
                  _trazo(Line(_p(0, 0), _p(0.18, -0.1)), c, 4))


def _rayo(c):
    return VGroup(_trazo(Polygon(_p(0.08, 0.48), _p(-0.25, -0.02), _p(-0.02, -0.02), _p(-0.1, -0.48),
                                 _p(0.25, 0.06), _p(0.02, 0.06)), e.AMARILLO if c == e.AZUL else c, relleno=0.5))


def _capas(c):
    grupo = VGroup()
    for k, y in enumerate((-0.25, 0, 0.25)):
        grupo.add(_trazo(Polygon(_p(-0.45, y), _p(0, y + 0.16), _p(0.45, y), _p(0, y - 0.16)), c, relleno=0.1 + 0.1 * k))
    return grupo


def _red(c):
    puntos = [_p(-0.35, -0.25), _p(0.35, -0.25), _p(0, 0.32)]
    lineas = VGroup(*[_trazo(Line(a, b), c, 2.5) for a, b in ((puntos[0], puntos[1]), (puntos[1], puntos[2]), (puntos[2], puntos[0]))])
    return VGroup(lineas, *[_trazo(Circle(0.11).move_to(p), c, relleno=0.6) for p in puntos])


def _reinicio(c):
    arco = _trazo(Arc(radius=0.36, start_angle=PI / 3, angle=1.6 * PI), c, 4)
    punta = _trazo(Polygon(_p(0.12, 0.42), _p(0.3, 0.26), _p(0.06, 0.2)), c, relleno=1)
    return VGroup(arco, punta)


def _pantalla(c):
    return VGroup(_trazo(RoundedRectangle(corner_radius=0.05, width=0.95, height=0.6).move_to(_p(0, 0.1)), c, relleno=0.08),
                  _trazo(Line(_p(0, -0.2), _p(0, -0.35)), c), _trazo(Line(_p(-0.22, -0.36), _p(0.22, -0.36)), c))


def _imagen(c):
    grupo = VGroup()
    for k in range(3):
        grupo.add(_trazo(RoundedRectangle(corner_radius=0.05, width=0.8, height=0.22).move_to(_p(0, -0.26 + 0.26 * k)),
                         c, relleno=0.1 + 0.12 * k))
    return grupo


ICONOS = {
    "contenedor": _contenedor, "docker": _ballena, "nube": _nube, "registro": _registro, "descarga": _descarga,
    "servidor": _servidor, "llave": _llave, "candado": _candado, "escudo": _escudo, "usuario": _usuario,
    "grupo": _grupo, "terminal": _terminal, "navegador": _navegador, "engranaje": _engranaje,
    "base_datos": _base_datos, "telefono": _telefono, "portatil": _portatil, "linux": _linux,
    "windows": _windows, "paquete": _paquete, "check": _check, "alerta": _alerta, "codigo": _codigo, "api": _api,
    "chip_ia": _chip_ia, "cohete": _cohete, "carpeta": _carpeta, "archivo": _archivo, "reloj": _reloj,
    "rayo": _rayo, "capas": _capas, "red": _red, "reinicio": _reinicio, "pantalla": _pantalla, "imagen": _imagen,
}
NOMBRES = sorted(ICONOS)
assert set(NOMBRES) == set(e.NOMBRES_ICONOS), "estilo.NOMBRES_ICONOS no coincide con los íconos dibujados"


def icono(nombre: str, color: str = e.AZUL, tamano: float = 1.0) -> VGroup:
    if nombre not in ICONOS:
        raise KeyError(f"Ícono {nombre!r} desconocido. Disponibles: {', '.join(NOMBRES)}")
    figura = ICONOS[nombre](color)
    if tamano != 1.0:
        figura.scale(tamano)
    return figura
