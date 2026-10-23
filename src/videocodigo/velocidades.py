"""Límites comunes de los controles de ritmo del video."""

from __future__ import annotations

import math


def _validar(valor, minimo: float, maximo: float, nombre: str) -> float:
    if valor is None:
        return 1.0
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or not minimo <= valor <= maximo:
        raise ValueError(f"La velocidad de {nombre} debe estar entre {minimo:g} y {maximo:g}×.")
    return float(valor)


def validar_velocidades(voz: float | None, animaciones: float | None) -> tuple[float, float]:
    return _validar(voz, 0.75, 1.5, "voz"), _validar(animaciones, 0.5, 2, "animaciones")
