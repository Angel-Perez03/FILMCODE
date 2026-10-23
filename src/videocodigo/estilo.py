"""Paleta, tipografías y formatos del estilo de los videos (fondo negro, Segoe UI, Consolas)."""

from __future__ import annotations

import math
from collections.abc import Iterable

# Colores
FONDO = "#000000"
TEXTO = "#FFFFFF"
TEXTO_SUAVE = "#D0D3D9"   # títulos grandes
GRIS = "#8B8F98"          # notas, antetítulos, etiquetas
GRIS_OSCURO = "#3A3D44"   # líneas tenues y cajas de relleno
GRIS_ARISTA = "#9A9DA4"   # aristas de grafos y flechas
AZUL = "#4EA8F5"          # lo que ya quedó definido o lo que está activo
AZUL_OSCURO = "#12304A"   # barra de la línea de código activa
AZUL_LINEA = "#2F5E8C"    # subrayado de las tarjetas de sección
ROJO = "#F0646A"          # alertas, camino final, tachados
AMARILLO = "#F5C542"
VERDE = "#7BC47F"

# Sintaxis apagada, como en el video de referencia
SINTAXIS = {
    "palabra_clave": "#D7B96E",
    "funcion": "#ECECEC",
    "nombre": "#C9CDD4",
    "cadena": "#A8C98A",
    "numero": "#8CC4F0",
    "comentario": "#6A6F78",
    "operador": "#A0A4AC",
    "builtin": "#8CC4F0",
}

# Tipografías (vienen con Windows)
FUENTE = "Segoe UI"
FUENTE_CODIGO = "Consolas"
FUENTE_MATE = "Cambria Math"

# Tamaños (font_size de Manim)
TAM_TITULO = 80
TAM_ANTETITULO = 26
TAM_FRASE = 44
TAM_TEXTO = 34
TAM_NOTA = 28
TAM_CODIGO = 22
TAM_ESTADO = 22
TAM_NODO = 30

# El cuadro mide 14,22 × 8 unidades; esto es lo que se deja libre en los bordes
MARGEN = 0.6
ANCHO_UTIL = 14.22 - 2 * MARGEN
ALTO_UTIL = 8.0 - 2 * MARGEN

INFINITO = "∞"
LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
MAX_LINEAS = 24  # líneas de código que caben legibles en una pantalla

# Íconos disponibles (se dibujan en componentes/iconos.py; aquí solo los nombres, para validar sin cargar Manim)
NOMBRES_ICONOS = (
    "alerta", "api", "archivo", "base_datos", "candado", "capas", "carpeta", "check", "chip_ia", "codigo", "cohete",
    "contenedor", "descarga", "docker", "engranaje", "escudo", "grupo", "imagen", "linux", "llave", "navegador",
    "nube", "paquete", "pantalla", "portatil", "rayo", "red", "registro", "reinicio", "reloj", "servidor",
    "telefono", "terminal", "usuario", "windows",
)


def numero(valor, decimales: int = 2) -> str:
    """Formatea un número al estilo del video: coma decimal y ∞ para infinito."""
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, float):
        if math.isinf(valor):
            return INFINITO if valor > 0 else "-" + INFINITO
        if math.isnan(valor):
            return "NaN"
        if valor.is_integer() and abs(valor) < 1e9:
            return str(int(valor))
        return f"{valor:.{decimales}f}".replace(".", ",")
    return str(valor)


def valor_corto(valor, decimales: int = 2, max_largo: int = 48) -> str:
    """Convierte un valor de la traza (JSON) en un texto corto para la tabla de estado."""
    if valor is None:
        return "-"
    if isinstance(valor, (int, float, bool)):
        return numero(valor, decimales)
    if isinstance(valor, str):
        texto = valor
    elif isinstance(valor, list):
        if valor and all(isinstance(v, list) and len(v) <= 3 for v in valor):
            texto = "[" + ", ".join("(" + ",".join(valor_corto(x, decimales) for x in v) + ")" for v in valor) + "]"
        else:
            texto = "[" + ", ".join(valor_corto(v, decimales) for v in valor) + "]"
    elif isinstance(valor, dict):
        texto = "{" + ", ".join(f"{k}: {valor_corto(v, decimales)}" for k, v in valor.items()) + "}"
    else:
        texto = str(valor)
    return texto if len(texto) <= max_largo else texto[: max_largo - 1] + "…"


def columnas(valores: Iterable, ancho: int = 4, decimales: int = 2) -> str:
    """Une valores en columnas de ancho fijo para que alineen en Consolas."""
    return "".join(valor_corto(v, decimales).ljust(ancho) for v in valores).rstrip()


def letra(indice: int) -> str:
    """0 → A, 1 → B… (después de la Z usa números)."""
    return LETRAS[indice] if 0 <= indice < len(LETRAS) else str(indice)
