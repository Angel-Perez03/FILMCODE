"""Lecturas breves y rutas confinadas a los archivos públicos del proyecto."""

from __future__ import annotations

import copy
import json
import re
import threading
import time
import uuid
from pathlib import Path, PureWindowsPath

from fastapi import HTTPException
from videocodigo import config, proyecto

_estados: dict[str, tuple[float, dict]] = {}
_cerrojo = threading.RLock()
MAX_JSON = 8_000_000


def es_enlace(ruta: Path) -> bool:
    return ruta.is_symlink() or ruta.is_junction()


def relativa_segura(texto: str) -> Path:
    if not isinstance(texto, str) or not texto or len(texto) > 1000:
        raise HTTPException(400, "Ruta de archivo inválida.")
    win = PureWindowsPath(texto)
    partes = texto.replace("\\", "/").split("/")
    if win.drive or win.root or any(
        not p or p in {".", ".."} or p.startswith(".") or p.endswith((" ", "."))
        or re.search(r'[<>:"|?*\x00-\x1f]', p)
        or PureWindowsPath(p).is_reserved() for p in partes
    ):
        raise HTTPException(400, "La ruta debe ser relativa, sin archivos ocultos ni partes especiales.")
    return Path(*partes)


def archivo_seguro(base: Path, relativa: str | Path) -> Path:
    relativa = relativa_segura(str(relativa))
    base = Path(base).absolute()
    if es_enlace(base):
        raise HTTPException(400, "No se permiten enlaces simbólicos ni uniones de carpetas.")
    actual = base
    for parte in relativa.parts:
        actual = actual / parte
        if es_enlace(actual):
            raise HTTPException(400, "No se permiten enlaces simbólicos ni uniones de carpetas.")
    resuelta = actual.resolve()
    if not resuelta.is_relative_to(base.resolve()):
        raise HTTPException(400, "El archivo está fuera de la carpeta permitida.")
    return resuelta


def carpeta_proyecto(nombre: str) -> Path:
    if not isinstance(nombre, str) or nombre != proyecto.nombre_valido(nombre):
        raise HTTPException(400, "Nombre de proyecto inválido.")
    base = Path(proyecto.VIDEOS)
    carpeta = archivo_seguro(base, nombre)
    manifiesto = archivo_seguro(carpeta, "proyecto.json")
    if not manifiesto.is_file():
        raise HTTPException(404, "El proyecto no existe.")
    proyecto.ruta(nombre)
    return carpeta


def carpeta_web() -> Path:
    carpeta = Path(config.RAIZ) / ".web"
    if es_enlace(carpeta):
        raise HTTPException(400, "La carpeta de trabajo no puede ser un enlace.")
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def leer_json(archivo: Path, defecto=None):
    archivo = Path(archivo)
    for intento in range(2):
        try:
            if archivo.stat().st_size > MAX_JSON:
                raise HTTPException(413, "El archivo JSON supera el límite de lectura.")
            return json.loads(archivo.read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            return copy.deepcopy(defecto)
        except (PermissionError, json.JSONDecodeError):
            if intento == 0:
                time.sleep(0.2)
    raise HTTPException(503, "El archivo se está actualizando; vuelve a intentarlo.")


def leer_estado(nombre: str) -> dict:
    archivo = archivo_seguro(carpeta_proyecto(nombre), "estado.json")
    clave = str(archivo)
    with _cerrojo:
        ahora = time.monotonic()
        anterior = _estados.get(clave)
        if anterior and ahora - anterior[0] < 1:
            return copy.deepcopy(anterior[1])
        estado = leer_json(archivo, {})
        if not isinstance(estado, dict):
            raise HTTPException(422, "El estado del proyecto debe ser un objeto JSON.")
        _estados[clave] = (time.monotonic(), estado)
        return copy.deepcopy(estado)


def invalidar_estado(nombre: str) -> None:
    clave = str((Path(proyecto.VIDEOS) / nombre / "estado.json").resolve())
    with _cerrojo:
        _estados.pop(clave, None)


def escribir_json(archivo: Path, datos) -> None:
    archivo.parent.mkdir(parents=True, exist_ok=True)
    temporal = archivo.with_name(f".{archivo.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        for intento in range(3):
            try:
                temporal.replace(archivo)
                break
            except PermissionError:
                if intento == 2:
                    raise
                time.sleep(0.2)
    finally:
        temporal.unlink(missing_ok=True)
