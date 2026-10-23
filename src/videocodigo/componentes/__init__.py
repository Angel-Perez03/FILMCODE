"""Piezas visuales reutilizables. Cada método devuelve una animación lista para `self.play(...)`."""

from .arbol import Arbol
from .arreglo import Arreglo, Matriz
from .codigo import PanelCodigo
from .diagrama import Diagrama, ListaArchivos
from .estado import TablaEstado
from .estructuras import Cola, FilaCajas, Pila
from .graficas import Barras, GraficaLinea
from .tabla import Tabla
from .terminal import Terminal
from .grafo import Grafo
from .textos import (
    ListaPuntos, Personaje, Sello, TarjetaSeccion, cifra, formula, frase, mono, nota, tachar, texto,
)

__all__ = [
    "Arbol", "Arreglo", "Barras", "Cola", "Diagrama", "FilaCajas", "GraficaLinea", "Grafo", "ListaArchivos",
    "ListaPuntos", "Matriz", "PanelCodigo", "Personaje", "Pila", "Sello", "Tabla", "TablaEstado", "TarjetaSeccion",
    "Terminal",
    "cifra", "formula", "frase", "mono", "nota", "tachar", "texto",
]
