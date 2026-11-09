"""Entrada de Manim que aplica el estilo de referencia solo en su proceso."""

from __future__ import annotations

import os

from videocodigo import estilo
from videocodigo_web.estilo_referencia import PALETA_ENV, EstiloReferencia, construir_estilo, leer_paleta


def _adaptar_componentes(tema: EstiloReferencia) -> None:
    from videocodigo import componentes
    from videocodigo.componentes import codigo, movimiento, terminal

    # Estas superficies tienen un color fijo en el motor original.
    class TerminalReferencia(terminal.Terminal):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.marco.set_fill(tema.panel, opacity=1).set_stroke(tema.colores["GRIS_OSCURO"])

        def salida(self, lineas, color=None):
            return super().salida(lineas, color=color or tema.colores["GRIS"])

        def _tarjeta(self, contenido, color, ancla):
            tarjeta = super()._tarjeta(contenido, color, ancla)
            tarjeta[0].set_fill(tema.tarjeta, opacity=1)
            return tarjeta

    class PanelCodigoReferencia(codigo.PanelCodigo):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # La barra marca la línea activa sin atenuar el texto de la referencia.
            self.atenuado = 1.0
            for linea in self.lineas:
                linea.set_opacity(1)
            for numero in self.numeros:
                numero.set_color(tema.colores["GRIS"])

    terminal.Terminal = componentes.Terminal = TerminalReferencia
    codigo.PanelCodigo = componentes.PanelCodigo = PanelCodigoReferencia
    movimiento.FONDO_TARJETA = tema.tarjeta
    movimiento.BORDE_TARJETA = tema.colores["GRIS_OSCURO"]


_paleta = leer_paleta(os.environ.get(PALETA_ENV))
if _paleta is not None:
    _tema = construir_estilo(_paleta)
    # Se aplica antes de importar las piezas que capturan colores como valores predeterminados.
    for _nombre, _color in _tema.colores.items():
        setattr(estilo, _nombre, _color)
    estilo.SINTAXIS = _tema.sintaxis
    os.environ["VIDEOCODIGO_AMBIENTE"] = "plano"
    _adaptar_componentes(_tema)

from videocodigo import motor  # noqa: E402 — debe importar la paleta ya aplicada.


class VideoGuion(motor.VideoGuion):
    """Escena local para que el cargador de Manim la descubra en este archivo."""
