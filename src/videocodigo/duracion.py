"""Duración aproximada del video y presupuesto de narración para el guion."""

from __future__ import annotations

import math

from .guion import MAX_TEXTO

# Misma referencia que usa la interfaz. La voz real y las pausas pueden variar.
CARACTERES_POR_SEGUNDO = 14.8
FRACCION_NARRACION = 0.82


def validar_minutos(valor: float | None) -> float | None:
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or not 1 <= valor <= 120:
        raise ValueError("La duración debe ser de 1 a 120 minutos, o quedar vacía.")
    return float(valor)


def estimar_segundos(caracteres: int) -> float:
    """Incluye un margen para pausas y transiciones; no cambia la velocidad de la voz."""
    return round(caracteres / CARACTERES_POR_SEGUNDO / FRACCION_NARRACION, 1)


def _caracteres(respuesta) -> int:
    if isinstance(respuesta, dict):
        total = 0
        for clave, valor in respuesta.items():
            if clave in {"texto", "intro", "cierre", "resultado", "reto", "despedida", "texto_salida", "gancho", "narracion"}:
                if isinstance(valor, str):
                    total += len(valor)
                elif isinstance(valor, list):
                    total += sum(len(t) for t in valor if isinstance(t, str))
            elif isinstance(valor, (dict, list)):
                total += _caracteres(valor)
        return total
    if isinstance(respuesta, list):
        return sum(_caracteres(valor) for valor in respuesta)
    return 0


class PresupuestoNarracion:
    def __init__(self, minutos: float | None):
        self.minutos = validar_minutos(minutos)
        self.restantes = 1
        self.usados = 0

    def repartir(self, solicitudes: int) -> None:
        self.restantes = max(1, solicitudes)

    def instruccion(self, narrada: bool) -> str:
        if self.minutos is None:
            return ""
        contexto = (f"\n\nDURACIÓN OBJETIVO DEL VIDEO COMPLETO: aproximadamente {self.minutos:g} minutos. "
                    "Es la duración del video final, no el tiempo de generación. "
                    "Planifica la explicación para esa duración a un ritmo natural. "
                    "Prioriza lo esencial, evita repeticiones y conserva la precisión de comandos y conceptos. "
                    "No cambies la velocidad de la voz ni añadas silencios para rellenar.")
        if narrada:
            presupuesto = self.minutos * 60 * CARACTERES_POR_SEGUNDO * FRACCION_NARRACION
            parte = max(40, round(max(0, presupuesto - self.usados) / self.restantes))
            contexto += (f" Para esta respuesta destina aproximadamente {parte} caracteres en total a TODOS sus "
                         "campos narrados juntos, incluyendo introducciones y explicaciones. "
                         "Los títulos, el código y las etiquetas de pantalla no cuentan en ese presupuesto. "
                         f"Cada campo narrado individual tiene un máximo de {MAX_TEXTO} caracteres. "
                         "Distribuye entre los bloques permitidos por el esquema. Respeta siempre sus límites "
                         "y cantidades obligatorias, aunque no se pueda alcanzar la duración objetivo; "
                         "no inventes contenido ni añadas relleno. Usa frases concisas y claras.")
        return contexto

    def registrar(self, respuesta: dict) -> None:
        self.usados += _caracteres(respuesta)
        self.restantes = max(1, self.restantes - 1)
