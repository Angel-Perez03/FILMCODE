"""Medios existentes, capítulos y archivos de revisión de cada proyecto."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from videocodigo import guion, ingesta, proyecto, voz

from .archivos import (archivo_seguro, carpeta_proyecto, carpeta_web, es_enlace,
                       leer_estado, leer_json)
from .fuentes import admitido
from .proyectos import videos_disponibles
from .seguridad import sanitizar

router = APIRouter()
_miniaturas = threading.Lock()


def calidad_valida(calidad: str) -> str:
    if calidad not in proyecto.CALIDADES:
        raise HTTPException(400, "Calidad desconocida.")
    return calidad


def existente(nombre: str, relativa: str) -> Path:
    archivo = archivo_seguro(carpeta_proyecto(nombre), relativa)
    if not archivo.is_file():
        raise HTTPException(404, "El archivo todavía no está disponible.")
    return archivo


@router.get("/proyectos/{nombre}/video/{calidad}")
def video(nombre: str, calidad: str, descargar: bool = False):
    archivo = existente(nombre, f"salida/{calidad_valida(calidad)}.mp4")
    return FileResponse(archivo, media_type="video/mp4", filename=f"{nombre}-{calidad}.mp4",
                        content_disposition_type="attachment" if descargar else "inline")


def srt_a_vtt(texto: str) -> str:
    texto = texto.lstrip("\ufeff").replace("\r\n", "\n")
    texto = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", texto)
    return "WEBVTT\n\n" + texto.strip() + "\n"


@router.get("/proyectos/{nombre}/subtitulos/{calidad}.vtt")
def subtitulos(nombre: str, calidad: str):
    archivo = existente(nombre, f"salida/{calidad_valida(calidad)}.srt")
    if archivo.stat().st_size > 4_000_000:
        raise HTTPException(413, "El archivo de subtítulos supera el límite de lectura.")
    return Response(sanitizar(srt_a_vtt(archivo.read_text(encoding="utf-8-sig"))), media_type="text/vtt")


def capitulos_de(documento: dict, narrado: dict) -> list[dict]:
    escenas = documento.get("escenas", [])
    if not isinstance(escenas, list):
        return []
    textos = []
    for escena in escenas:
        try:
            textos.append([voz.extraer_marcas(t)[0] for t in guion.textos({"escenas": [escena]})])
        except (ValueError, TypeError, AttributeError, KeyError):
            textos.append([])
    actual = 0
    capitulos = []
    encontrados = set()
    for bloque in narrado.get("bloques", []):
        if not isinstance(bloque, dict):
            continue
        for indice in range(actual, len(escenas)):
            if bloque.get("texto") not in textos[indice]:
                continue
            actual = indice
            if indice not in encontrados:
                escena = escenas[indice]
                capitulos.append({"escena": indice + 1, "tipo": escena.get("tipo", ""),
                                  "titulo": escena.get("titulo") or escena.get("pantalla") or f"Escena {indice + 1}",
                                  "inicio": bloque.get("inicio", 0)})
                encontrados.add(indice)
            break
    return capitulos


@router.get("/proyectos/{nombre}/narrado/{calidad}")
def narrado(nombre: str, calidad: str):
    archivo = existente(nombre, f"salida/narrado_{calidad_valida(calidad)}.json")
    datos = leer_json(archivo, {})
    if not isinstance(datos, dict):
        raise HTTPException(422, "La narración debe ser un objeto JSON.")
    documento = leer_json(archivo_seguro(carpeta_proyecto(nombre), "guion.json"), {})
    return {**datos, "capitulos": capitulos_de(documento if isinstance(documento, dict) else {}, datos)}


@router.get("/proyectos/{nombre}/hojas/{calidad}")
def hojas(nombre: str, calidad: str):
    carpeta = archivo_seguro(carpeta_proyecto(nombre), f"salida/hojas_{calidad_valida(calidad)}")
    if not carpeta.is_dir():
        return []
    return [ruta.name for ruta in sorted(carpeta.glob("hoja_*.jpg"))
            if ruta.is_file() and not es_enlace(ruta) and re.fullmatch(r"hoja_\d+\.jpg", ruta.name)]


@router.get("/proyectos/{nombre}/hojas/{calidad}/{archivo}")
def hoja(nombre: str, calidad: str, archivo: str):
    if not re.fullmatch(r"hoja_\d+\.jpg", archivo):
        raise HTTPException(400, "Nombre de hoja inválido.")
    ruta = existente(nombre, f"salida/hojas_{calidad_valida(calidad)}/{archivo}")
    return FileResponse(ruta, media_type="image/jpeg")


def generar_miniatura(nombre: str) -> Path:
    carpeta = carpeta_proyecto(nombre)
    disponibles = videos_disponibles(carpeta, leer_estado(nombre))
    if not disponibles:
        raise HTTPException(404, "El proyecto todavía no tiene video.")
    ultimo = max(disponibles, key=lambda v: v.get("fecha") or "")
    entrada = archivo_seguro(carpeta, f"salida/{ultimo['calidad']}.mp4")
    salida = archivo_seguro(carpeta, "salida/miniatura.jpg")
    with _miniaturas:
        if salida.is_file() and salida.stat().st_mtime >= entrada.stat().st_mtime:
            return salida
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise HTTPException(503, "No se encontró ffmpeg para generar la miniatura.")
        duracion = ultimo.get("duracion")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if not isinstance(duracion, (int, float)) or duracion <= 0:
            ffprobe = shutil.which("ffprobe")
            if not ffprobe:
                raise HTTPException(503, "No se encontró ffprobe para leer la duración.")
            try:
                resultado = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(entrada)], capture_output=True,
                    text=True, timeout=15, creationflags=flags, check=True)
                duracion = float(resultado.stdout.strip())
            except (subprocess.SubprocessError, ValueError, OSError) as exc:
                raise HTTPException(503, "No fue posible leer la duración del video.") from exc
        temporal = archivo_seguro(carpeta_web(), f"miniatura-{uuid.uuid4().hex}.jpg")
        try:
            subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-ss", str(max(0, duracion * 0.1)), "-i", str(entrada), "-frames:v", "1",
                "-vf", "scale=480:-2", str(temporal)], capture_output=True, timeout=20,
                creationflags=flags, check=True)
            temporal.replace(salida)
        except (subprocess.SubprocessError, OSError) as exc:
            raise HTTPException(503, "No fue posible generar la miniatura del video.") from exc
        finally:
            temporal.unlink(missing_ok=True)
    return salida


@router.get("/proyectos/{nombre}/miniatura")
def miniatura(nombre: str):
    return FileResponse(generar_miniatura(nombre), media_type="image/jpeg")


@router.get("/proyectos/{nombre}/capturas")
def capturas(nombre: str):
    return leer_json(archivo_seguro(carpeta_proyecto(nombre), "capturas.json"), [])


@router.get("/proyectos/{nombre}/llm")
def registro_llm(nombre: str):
    archivo = archivo_seguro(carpeta_proyecto(nombre), "llm/registro.jsonl")
    if not archivo.is_file():
        return []
    if archivo.stat().st_size > 8_000_000:
        raise HTTPException(413, "El registro del modelo supera el límite de lectura.")
    registros = []
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        try:
            dato = json.loads(linea)
            if isinstance(dato, dict):
                registros.append(dato)
        except json.JSONDecodeError:
            continue
    return registros


@router.get("/proyectos/{nombre}/log/{calidad}")
def log(nombre: str, calidad: str, lineas: int = Query(200, ge=1, le=1000)):
    archivo = archivo_seguro(carpeta_proyecto(nombre), f"salida/render_{calidad_valida(calidad)}.log")
    if not archivo.is_file():
        return {"lineas": []}
    with archivo.open("rb") as flujo:
        tamanio = archivo.stat().st_size
        flujo.seek(max(0, tamanio - 1_000_000))
        texto = flujo.read(1_000_000).decode("utf-8", errors="replace")
    contenido = texto.splitlines()
    if tamanio > 1_000_000:
        contenido = contenido[1:]
    return {"lineas": contenido[-lineas:]}


@router.get("/proyectos/{nombre}/codigo")
def codigo(nombre: str):
    base = archivo_seguro(carpeta_proyecto(nombre), "codigo")
    if not base.is_dir():
        return []
    salida = []
    entradas = 0
    for carpeta, directorios, archivos in os.walk(base, followlinks=False):
        directorios[:] = [d for d in directorios if not d.startswith(".") and d not in ingesta.IGNORAR
                          and not es_enlace(Path(carpeta) / d)]
        entradas += len(directorios) + len(archivos)
        if entradas > 20_000:
            raise HTTPException(413, "El árbol de código supera el límite de lectura.")
        for nombre_archivo in archivos:
            archivo = Path(carpeta) / nombre_archivo
            if nombre_archivo.startswith(".") or not admitido(archivo) or es_enlace(archivo):
                continue
            if archivo.stat().st_size > ingesta.MAX_BYTES:
                continue
            salida.append({"ruta": archivo.relative_to(base).as_posix(), "bytes": archivo.stat().st_size,
                           "lenguaje": ingesta.lenguaje_de(archivo) or "markdown"})
            if len(salida) > ingesta.MAX_ARCHIVOS:
                raise HTTPException(413, "El árbol de código supera 400 archivos.")
    return sorted(salida, key=lambda item: item["ruta"])


@router.get("/proyectos/{nombre}/codigo/archivo")
def codigo_archivo(nombre: str, ruta: str):
    base = archivo_seguro(carpeta_proyecto(nombre), "codigo")
    archivo = archivo_seguro(base, ruta)
    if not archivo.is_file():
        raise HTTPException(404, "El archivo de código no existe.")
    if not admitido(archivo):
        raise HTTPException(400, "El tipo de archivo no está admitido.")
    if archivo.stat().st_size > ingesta.MAX_BYTES:
        raise HTTPException(413, "El archivo pesa más de 400 KB.")
    return {"ruta": archivo.relative_to(base).as_posix(), "contenido": archivo.read_text(encoding="utf-8", errors="replace"),
            "lenguaje": ingesta.lenguaje_de(archivo) or "markdown"}
