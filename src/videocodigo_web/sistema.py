"""Consultas de servicios locales; ninguna consulta carga modelos."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import replace
from typing import Literal

import psutil
import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from videocodigo import config, estilo, guion, ingesta, proyecto, voz

from .archivos import archivo_seguro, carpeta_proyecto, carpeta_web, leer_json
from .seguridad import url_local

router = APIRouter()
_cache = {}
_cerrojo = threading.RLock()


def consultar(url, cabeceras=None):
    url_local(url)
    with requests.Session() as sesion:
        sesion.trust_env = False
        respuesta = sesion.get(url, headers=cabeceras, timeout=(1, 2), allow_redirects=False)
        if not 200 <= respuesta.status_code < 300:
            raise ValueError(f"El servicio respondió HTTP {respuesta.status_code}.")
        if len(respuesta.content) > 2_000_000:
            raise ValueError("La respuesta del servicio es demasiado grande.")
        return respuesta.json()


def estado_servicios(modelo=None, forzar=False):
    llm = config.ajustes_llm(modelo)
    v = config.ajustes_voz()
    clave = (str(config.RAIZ), llm.modelo, llm.proveedor, llm.url, v.voicestudio_url)
    with _cerrojo:
        anterior = _cache.get(clave)
        if anterior and not forzar and time.monotonic() - anterior[0] < 10:
            return anterior[1].copy()
        ollama = {"listo": False, "mensaje": "Elige un modelo de Ollama local.", "modelos": []}
        if llm.proveedor == "ollama":
            try:
                respuesta = consultar(url_local(llm.url) + "/api/tags")
                modelos = [m["name"] for m in respuesta.get("models", []) if isinstance(m, dict) and "name" in m]
                listo = llm.modelo in modelos or llm.modelo + ":latest" in modelos
                ollama = {"listo": listo, "modelos": modelos, "mensaje": "Ollama listo" if listo
                          else f"Ollama no tiene instalado {llm.modelo}."}
            except (requests.RequestException, ValueError, HTTPException, AttributeError):
                ollama["mensaje"] = "Ollama no responde o su dirección no es local. Abre Ollama y revisa su configuración."
        try:
            consultar(url_local(v.voicestudio_url) + "/health",
                      {"Authorization": f"Bearer {v.voicestudio_clave}"} if v.voicestudio_clave else {})
            estudio = {"listo": True, "mensaje": "VoiceStudio listo"}
        except (requests.RequestException, ValueError, HTTPException):
            estudio = {"listo": False, "mensaje": "VoiceStudio no responde o su dirección no es local. Abre VoiceStudio."}
        datos = {"ollama": ollama, "voicestudio": estudio, "ffmpeg": bool(shutil.which("ffmpeg"))}
        _cache[clave] = (time.monotonic(), datos)
        return datos.copy()


@router.get("/salud")
def salud(request: Request, forzar: bool = False):
    datos = estado_servicios(forzar=forzar)
    datos["trabajo"] = request.app.state.gestor.ocupado()
    return datos


@router.get("/ajustes")
def ajustes():
    m, v = config.ajustes_llm(), config.ajustes_voz()
    docker = os.environ.get("FILMCODE_DOCKER") == "1"
    return {"capacidades": {"modo": "docker" if docker else "nativo",
                            "prioridad_dinamica": os.name == "nt" and not docker,
                            "rutas_anfitrion": not docker},
            "modelo": {k: getattr(m, k) for k in
                       ("proveedor", "modelo", "url", "temperatura", "contexto", "max_tokens", "formato")},
            "voz": {k: getattr(v, k) for k in ("proveedor", "voicestudio_url", "voicestudio_voz",
                    "voicestudio_modelo", "voicestudio_idioma", "edge_voz", "edge_velocidad")},
            "claves": {"openai": bool(config.ajustes_llm("openai:local").clave),
                       "voicestudio": bool(v.voicestudio_clave)}}


@router.get("/esquema")
def esquema():
    return {"escenas": guion.ESCENAS, "acciones": guion.ACCIONES, "iconos": list(estilo.NOMBRES_ICONOS),
            "limites": {"texto": guion.MAX_TEXTO, "escenas": guion.MAX_ESCENAS, "lineas": estilo.MAX_LINEAS,
                        "archivos": ingesta.MAX_ARCHIVOS, "bytes": ingesta.MAX_BYTES},
            "calidades": proyecto.CALIDADES, "calidad_predeterminada": proyecto.CALIDAD_PREDETERMINADA}


@router.get("/voces")
def voces():
    v = config.ajustes_voz()
    try:
        datos = consultar(url_local(v.voicestudio_url) + "/v1/audio/voices",
                          {"Authorization": f"Bearer {v.voicestudio_clave}"} if v.voicestudio_clave else {})
        estudio = datos.get("voices", []) if isinstance(datos, dict) else datos
        if not isinstance(estudio, list):
            raise ValueError("Lista inválida")
    except (requests.RequestException, ValueError, HTTPException):
        estudio = {"error": "VoiceStudio no responde. Abre la app para consultar sus voces."}
    return {"edge": voz.VOCES_EDGE_ES, "voicestudio": estudio}


def comprobar_para_trabajo(nombre, opciones):
    from .guiones import errores_guion

    tipo = opciones.get("tipo")
    calidad = opciones.get("calidad", proyecto.CALIDAD_PREDETERMINADA)
    carpeta = carpeta_proyecto(nombre)
    archivo_guion = archivo_seguro(carpeta, "guion.json")
    existe = archivo_guion.is_file()
    if tipo in {"render", "continuar"} and existe:
        errores = errores_guion(leer_json(archivo_guion), carpeta)
        if errores:
            raise HTTPException(422, {"error": "Corrige el guion antes de renderizar.", "errores": errores})
    requiere_guion = tipo == "guion" or (tipo == "continuar" and not existe)
    if requiere_guion:
        m = config.ajustes_llm(opciones.get("modelo"))
        if m.proveedor != "ollama":
            raise HTTPException(400, "Esta interfaz utiliza exclusivamente modelos locales de Ollama.")
        url_local(m.url)
        estado = estado_servicios(opciones.get("modelo"), forzar=True)
        if not estado["ollama"]["listo"]:
            raise HTTPException(409, estado["ollama"]["mensaje"])
    if tipo in {"render", "continuar", "fotogramas"} and not shutil.which("ffmpeg"):
        raise HTTPException(409, "No se encuentra ffmpeg en este equipo.")
    if tipo in {"render", "continuar"} and (opciones.get("voz") or proyecto.CALIDADES.get(calidad, {}).get("voz")) == "voicestudio":
        url_local(config.ajustes_voz().voicestudio_url)
        estado = estado_servicios(opciones.get("modelo"))
        if not estado["voicestudio"]["listo"]:
            raise HTTPException(409, estado["voicestudio"]["mensaje"])
    if tipo == "render" and not existe:
        raise HTTPException(400, "El proyecto no tiene guion.json; genera el guion primero.")


class PruebaVoz(BaseModel):
    proveedor: Literal["edge", "voicestudio"]
    voz: str = Field(min_length=1, max_length=160)
    texto: str = Field(default="Hola. Esta es una prueba de voz para tu próximo video.", min_length=1, max_length=200)


@router.post("/voces/prueba")
def prueba_voz(datos: PruebaVoz, request: Request):
    gestor = request.app.state.gestor
    with gestor.bloqueo:
        if gestor.ocupado() or getattr(gestor, "prueba_voz_activa", False):
            raise HTTPException(409, "Espera a que termine el trabajo activo antes de probar una voz.")
        gestor.prueba_voz_activa = True
    try:
        return ejecutar_prueba(datos)
    finally:
        with gestor.bloqueo:
            gestor.prueba_voz_activa = False


def ejecutar_prueba(datos: PruebaVoz):
    cache = archivo_seguro(carpeta_web(), "pruebas_voz")
    if datos.proveedor == "voicestudio":
        url_local(config.ajustes_voz().voicestudio_url)
    elif datos.voz not in {v["id"] for v in voz.VOCES_EDGE_ES}:
        raise HTTPException(400, "Selecciona una voz Edge de la lista disponible.")
    ajustes = replace(config.ajustes_voz(datos.proveedor),
                      **{"edge_voz" if datos.proveedor == "edge" else "voicestudio_voz": datos.voz})
    huella = voz.crear_voz(datos.proveedor, cache, ajustes).huella(datos.texto.strip())
    metadatos = archivo_seguro(cache, f"{huella}.json")
    archivo_seguro(cache, f"{huella}.mp3")
    if metadatos.is_file():
        anterior = leer_json(metadatos)
        if not isinstance(anterior, dict):
            raise HTTPException(422, "La caché de esta voz contiene metadatos inválidos.")
        if anterior.get("audio"):
            archivo_seguro(cache, anterior["audio"])
    orden = [sys.executable, "-m", "videocodigo_web.prueba_voz", datos.proveedor, datos.voz, datos.texto]
    proceso = subprocess.Popen(orden, cwd=config.RAIZ, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                               env={**os.environ, "PYTHONIOENCODING": "utf-8", "NO_PROXY": "localhost,127.0.0.1,::1",
                                    "no_proxy": "localhost,127.0.0.1,::1"})
    try:
        salida, _ = proceso.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        try:
            hijos = psutil.Process(proceso.pid).children(recursive=True)
            for hijo in reversed(hijos):
                hijo.kill()
        except psutil.Error:
            pass
        proceso.kill()
        proceso.communicate()
        raise HTTPException(504, "La prueba de voz superó los tres minutos.")
    if proceso.returncode:
        raise HTTPException(502, "No se pudo sintetizar la prueba. Revisa el servicio de voz y su configuración.")
    try:
        nombre = json.loads(salida)["archivo"]
        archivo = archivo_seguro(cache, nombre)
        if not archivo.is_file() or archivo.suffix != ".mp3":
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise HTTPException(502, "La prueba no produjo un audio válido.")
    return FileResponse(archivo, media_type="audio/mpeg")
