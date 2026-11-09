"""Formatos de salida de la web sin cambiar los perfiles de render de Manim."""

from __future__ import annotations

from typing import Literal

from videocodigo import proyecto

Orientacion = Literal["horizontal", "vertical"]
ORIENTACIONES = ("horizontal", "vertical")
SUFIJO_VERTICAL = "-vertical"


def calidad_base(calidad: str) -> str:
    """Valida un identificador público y devuelve el perfil original de Manim."""
    if not isinstance(calidad, str):
        raise ValueError("Calidad desconocida.")
    base = calidad.removesuffix(SUFIJO_VERTICAL)
    if base not in proyecto.CALIDADES:
        raise ValueError("Calidad desconocida.")
    return base


def calidad_salida(calidad: str, orientacion: Orientacion) -> str:
    base = calidad_base(calidad)
    if orientacion not in ORIENTACIONES:
        raise ValueError("Elige una orientación horizontal o vertical.")
    return base + SUFIJO_VERTICAL if orientacion == "vertical" else base


def orientacion_salida(calidad: str) -> Orientacion:
    calidad_base(calidad)
    return "vertical" if calidad.endswith(SUFIJO_VERTICAL) else "horizontal"


def calidades_salida() -> tuple[str, ...]:
    return (*proyecto.CALIDADES, *(base + SUFIJO_VERTICAL for base in proyecto.CALIDADES))


def dimensiones_salida(calidad: str) -> tuple[int, int]:
    perfil = proyecto.CALIDADES[calidad_base(calidad)]
    alto = perfil["resolucion"]
    ancho = perfil.get("ancho", proyecto.RESOLUCIONES[alto]["ancho"])
    return (alto, ancho) if orientacion_salida(calidad) == "vertical" else (ancho, alto)


def filtro_vertical(calidad: str) -> str | None:
    """Adapta el lienzo al móvil conservando el encuadre y el texto de Manim."""
    if orientacion_salida(calidad) == "horizontal":
        return None
    ancho, alto = dimensiones_salida(calidad)
    return (
        f"scale=w={ancho}:h={alto}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
        f"pad=w={ancho}:h={alto}:x=(ow-iw)/2:y=(oh-ih)/2:color=0x080C16,setsar=1"
    )
