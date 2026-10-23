"""Configuración: rutas del repo y ajustes leídos del .env o de variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(os.environ.get("VIDEOCODIGO_RAIZ", Path(__file__).resolve().parents[2]))
VIDEOS = RAIZ / "videos"

PROVEEDORES_VOZ = ("voicestudio", "edge", "silencio")


def cargar_entorno() -> None:
    """Carga el .env del repo sin pisar variables que ya existan en el entorno."""
    load_dotenv(RAIZ / ".env", override=False)


def _flotante(nombre: str, defecto: float) -> float:
    try:
        return float(os.environ.get(nombre, defecto))
    except ValueError:
        return defecto


@dataclass(frozen=True)
class AjustesVoz:
    proveedor: str = "edge"
    voicestudio_url: str = "http://localhost:3900"
    voicestudio_voz: str = "alloy"
    voicestudio_modelo: str = "cosyvoice"
    voicestudio_idioma: str = "es"
    voicestudio_estilo: str = ""  # instrucción de tono para CosyVoice (vacío = copia la referencia tal cual)
    voicestudio_clave: str = ""
    edge_voz: str = "es-CO-GonzaloNeural"
    edge_velocidad: str = "+0%"
    palabras_por_minuto: int = 150


def ajustes_voz(proveedor: str | None = None) -> AjustesVoz:
    cargar_entorno()
    elegido = (proveedor or os.environ.get("VIDEOCODIGO_VOZ") or "edge").lower()
    if elegido not in PROVEEDORES_VOZ:
        raise ValueError(f"Proveedor de voz desconocido: {elegido!r}. Usa uno de {PROVEEDORES_VOZ}.")
    return AjustesVoz(
        proveedor=elegido,
        voicestudio_url=os.environ.get("VOICESTUDIO_URL", "http://localhost:3900").strip(),
        voicestudio_voz=os.environ.get("VOICESTUDIO_VOZ", "alloy").strip(),
        voicestudio_modelo=os.environ.get("VOICESTUDIO_MODELO", "cosyvoice").strip(),
        voicestudio_idioma=os.environ.get("VOICESTUDIO_IDIOMA", "es").strip(),
        voicestudio_estilo=os.environ.get("VOICESTUDIO_ESTILO", "").strip(),
        voicestudio_clave=os.environ.get("OMNIVOICE_API_KEY", "").strip(),
        edge_voz=os.environ.get("EDGE_VOZ", "es-CO-GonzaloNeural").strip(),
        edge_velocidad=os.environ.get("EDGE_VELOCIDAD", "+0%").strip(),
    )


@dataclass(frozen=True)
class AjustesLLM:
    proveedor: str = "ollama"
    modelo: str = "gemma4:12b"
    url: str = "http://localhost:11434"
    clave: str = ""
    temperatura: float = 0.4
    contexto: int = 8192  # con 6 GB de VRAM, 32K de contexto saca el modelo de la GPU y lo vuelve 20 veces más lento
    max_tokens: int = 2048
    formato: str = "libre"  # libre (rápido, se valida después) | json | esquema (gramática exacta, lenta en Gemma)


def ajustes_llm(modelo: str | None = None) -> AjustesLLM:
    """`modelo` acepta 'proveedor:nombre': ollama:gemma4:12b o openai:<modelo> (LM Studio, vLLM, OpenRouter…)."""
    cargar_entorno()
    texto = modelo or os.environ.get("VIDEOCODIGO_MODELO") or "ollama:gemma4:12b"
    proveedor, _, nombre = texto.partition(":")
    if proveedor not in ("ollama", "openai"):
        proveedor, nombre = "ollama", texto
    urls = {
        "ollama": os.environ.get("OLLAMA_URL", "http://localhost:11434"),
        "openai": os.environ.get("OPENAI_BASE_URL", "http://localhost:1234/v1"),
    }
    claves = {"ollama": "", "openai": os.environ.get("OPENAI_API_KEY", "")}
    return AjustesLLM(
        proveedor=proveedor,
        modelo=nombre,
        url=urls[proveedor].rstrip("/"),
        clave=claves[proveedor].strip(),
        temperatura=_flotante("VIDEOCODIGO_TEMPERATURA", 0.4),
        contexto=int(_flotante("VIDEOCODIGO_CONTEXTO", 8192)),
        max_tokens=int(_flotante("VIDEOCODIGO_MAX_TOKENS", 2048)),
        formato=os.environ.get("VIDEOCODIGO_FORMATO", "libre").strip().lower(),
    )
