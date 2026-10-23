"""Fondos con profundidad: degradado oscuro, brillos difusos y una rejilla tenue de puntos.

Se generan una vez como PNG (con Pillow, que ya viene con Manim) y se reutilizan entre renders.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ANCHO, ALTO = 1920, 1080

# Paletas por ambiente: color base y brillos (color, x, y, radio, intensidad) en fracciones del cuadro
AMBIENTES = {
    "azul": {"base": (5, 8, 16), "brillos": [((38, 99, 200), 0.82, 0.18, 0.55, 0.55), ((20, 60, 140), 0.12, 0.92, 0.5, 0.35)]},
    "neutro": {"base": (6, 7, 10), "brillos": [((40, 70, 120), 0.5, -0.1, 0.7, 0.30)]},
    "cian": {"base": (4, 10, 14), "brillos": [((20, 140, 170), 0.15, 0.2, 0.55, 0.40), ((40, 80, 190), 0.9, 0.85, 0.5, 0.35)]},
    "violeta": {"base": (8, 6, 16), "brillos": [((110, 60, 200), 0.85, 0.25, 0.55, 0.40), ((40, 80, 190), 0.1, 0.85, 0.5, 0.30)]},
    "rojo": {"base": (12, 6, 8), "brillos": [((190, 50, 60), 0.85, 0.15, 0.5, 0.35), ((60, 40, 110), 0.1, 0.9, 0.5, 0.25)]},
    "verde": {"base": (5, 11, 9), "brillos": [((40, 160, 110), 0.15, 0.15, 0.55, 0.35), ((30, 90, 160), 0.85, 0.9, 0.5, 0.30)]},
}


def _carpeta() -> Path:
    destino = Path(os.environ.get("VIDEOCODIGO_FONDOS", Path(tempfile.gettempdir()) / "videocodigo_fondos"))
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def generar(ambiente: str = "azul", puntos: bool = True, ancho: int = ANCHO, alto: int = ALTO) -> Path:
    """Devuelve la ruta del PNG del fondo al tamaño pedido (lo crea si no existe)."""
    datos = AMBIENTES.get(ambiente, AMBIENTES["azul"])
    huella = hashlib.sha256(json.dumps([datos, puntos, ancho, alto, 2]).encode()).hexdigest()[:12]
    ruta = _carpeta() / f"fondo_{ambiente}_{ancho}x{alto}_{huella}.png"
    if ruta.exists():
        return ruta
    ANCHO_, ALTO_ = ancho, alto
    ys, xs = np.mgrid[0:ALTO_, 0:ANCHO_].astype(np.float32)
    xs, ys = xs / ANCHO_, ys / ALTO_
    imagen = np.zeros((ALTO_, ANCHO_, 3), np.float32) + np.array(datos["base"], np.float32)
    for color, cx, cy, radio, fuerza in datos["brillos"]:
        d2 = ((xs - cx) * 16 / 9) ** 2 + (ys - cy) ** 2
        imagen += np.exp(-d2 / (2 * (radio / 2.2) ** 2))[..., None] * np.array(color, np.float32) * fuerza
    vineta = 1 - 0.45 * np.clip(((xs - 0.5) ** 2 + (ys - 0.5) ** 2) * 2.2, 0, 1)
    imagen *= vineta[..., None]
    if puntos:
        paso = max(int(48 * ANCHO_ / ANCHO), 12)
        malla = ((np.arange(ANCHO_) % paso == 0)[None, :] & (np.arange(ALTO_) % paso == 0)[:, None]).astype(np.float32)
        imagen += malla[..., None] * 22
    ruido = np.random.default_rng(7).normal(0, 1.6, imagen.shape[:2]).astype(np.float32)
    imagen += ruido[..., None]
    Image.fromarray(np.clip(imagen, 0, 255).astype(np.uint8)).save(ruta)
    return ruta
