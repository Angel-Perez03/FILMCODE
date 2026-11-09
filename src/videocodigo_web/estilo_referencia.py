"""Traduce una paleta de referencia a colores legibles para la escena."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

PALETA_ENV = "FILMCODE_PALETA_REFERENCIA"
FONDO_PREDETERMINADO = "predeterminado"
_CLAVES = {"fondo", "texto", "acento", "secundario"}
_HEX = re.compile(r"#[0-9a-fA-F]{6}")


def normalizar_fondo(valor: str | None) -> str:
    if valor is None or valor == FONDO_PREDETERMINADO:
        return FONDO_PREDETERMINADO
    if not isinstance(valor, str) or not _HEX.fullmatch(valor):
        raise ValueError("Elige el fondo original o un color válido en formato #RRGGBB.")
    return valor.upper()


def paleta_con_fondo(paleta: dict[str, str] | None, fondo: str | None) -> dict[str, str] | None:
    """Un fondo explícito gana; conserva los otros colores de la referencia."""
    fondo = normalizar_fondo(fondo)
    if fondo == FONDO_PREDETERMINADO:
        return paleta
    if paleta is not None:
        return {**paleta, "fondo": fondo}
    tinta = "#161616" if contraste("#161616", fondo) >= contraste("#F7F7F7", fondo) else "#F7F7F7"
    return {"fondo": fondo, "texto": tinta, "acento": "#4EA8F5", "secundario": tinta}


def leer_paleta(valor: str | None) -> dict[str, str] | None:
    """Acepta solo los cuatro colores CSS transportados al proceso de Manim."""
    if valor is None:
        return None
    try:
        datos = json.loads(valor) if len(valor) <= 256 else None
    except ValueError:
        datos = None
    if not isinstance(datos, dict) or datos.keys() != _CLAVES or not all(
        isinstance(color, str) and _HEX.fullmatch(color) for color in datos.values()
    ):
        raise ValueError("Paleta de referencia inválida: se esperan fondo, texto, acento y secundario en #RRGGBB.")
    return {nombre: color.upper() for nombre, color in datos.items()}


def _rgb(color: str) -> tuple[int, ...]:
    return tuple(bytes.fromhex(color[1:]))


def _mezclar(a: str, b: str, peso: float) -> str:
    return "#" + "".join(f"{round(x + (y - x) * peso):02X}" for x, y in zip(_rgb(a), _rgb(b)))


def _luminancia(color: str) -> float:
    def lineal(canal: int) -> float:
        nivel = canal / 255
        return nivel / 12.92 if nivel <= 0.04045 else ((nivel + 0.055) / 1.055) ** 2.4

    return sum(lineal(c) * p for c, p in zip(_rgb(color), (0.2126, 0.7152, 0.0722)))


def contraste(a: str, b: str) -> float:
    oscuro, claro = sorted((_luminancia(a), _luminancia(b)))
    return (claro + 0.05) / (oscuro + 0.05)


def _contrastar(color: str, fondos: tuple[str, ...], minimo: float, extremo: str) -> str:
    """Busca el ajuste más pequeño hacia un extremo de contraste conocido."""
    def legible(candidato: str) -> bool:
        return all(contraste(candidato, fondo) >= minimo for fondo in fondos)

    if legible(color):
        return color
    bajo, alto = 0.0, 1.0
    for _ in range(12):
        punto = (bajo + alto) / 2
        if legible(_mezclar(color, extremo, punto)):
            alto = punto
        else:
            bajo = punto
    return _mezclar(color, extremo, alto)


@dataclass(frozen=True)
class EstiloReferencia:
    colores: dict[str, str]
    sintaxis: dict[str, str]
    panel: str
    tarjeta: str


def construir_estilo(paleta: dict[str, str]) -> EstiloReferencia:
    """Conserva el fondo y solo desplaza texto y acentos cuando falta contraste."""
    fondo = paleta["fondo"]
    negro, blanco = "#000000", "#FFFFFF"
    tinta = negro if contraste(negro, fondo) >= contraste(blanco, fondo) else blanco
    neutro = blanco if tinta == negro else negro

    def superficie(color: str, peso: float) -> str:
        return _contrastar(_mezclar(fondo, color, peso), (tinta,), 4.5, neutro)

    panel = superficie(tinta, 0.06)
    tarjeta = superficie(paleta["secundario"], 0.12)
    barra = superficie(paleta["acento"], 0.18)
    fondos = fondo, panel, tarjeta, barra

    def frente(color: str, minimo: float = 4.5) -> str:
        return _contrastar(color, fondos, minimo, tinta)

    texto = frente(paleta["texto"])
    acento = frente(paleta["acento"])
    secundario = frente(paleta["secundario"])
    suave = frente(_mezclar(texto, fondo, 0.16))
    gris = frente(_mezclar(texto, fondo, 0.32))
    borde = frente(_mezclar(texto, fondo, 0.58), 3)
    verde = frente("#7BC47F")
    return EstiloReferencia(
        colores={"FONDO": fondo, "TEXTO": texto, "TEXTO_SUAVE": suave, "GRIS": gris,
                 "GRIS_OSCURO": borde, "GRIS_ARISTA": gris, "AZUL": acento,
                 "AZUL_OSCURO": barra, "AZUL_LINEA": secundario,
                 "ROJO": frente("#F0646A"), "AMARILLO": frente("#F5C542"), "VERDE": verde},
        sintaxis={"palabra_clave": secundario, "funcion": texto, "nombre": suave,
                  "cadena": verde, "numero": acento, "comentario": gris,
                  "operador": gris, "builtin": acento},
        panel=panel,
        tarjeta=tarjeta,
    )
