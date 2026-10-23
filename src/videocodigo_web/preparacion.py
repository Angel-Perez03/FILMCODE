"""Lista de preparación de FilmCode: consulta, sin instalar ni cargar modelos."""

from __future__ import annotations

import os
import shutil
import sys
from importlib import metadata

import requests
from fastapi import APIRouter, HTTPException
from videocodigo import config

from . import sistema

router = APIRouter()
MODELO = "gemma4:12b"


def version_paquete(nombre):
    try:
        return metadata.version(nombre)
    except metadata.PackageNotFoundError:
        return None


def requisito(identificador, nombre, estado, necesario_para, detalle, accion, **extras):
    return {"id": identificador, "nombre": nombre, "estado": estado,
            "necesario_para": necesario_para, "detalle": detalle, "accion": accion, **extras}


def estado_perfil(estudio_listo):
    """Compara el perfil configurado internamente; nunca devuelve IDs ni errores crudos."""
    if not estudio_listo:
        return "sin_confirmar", "Primero debe responder VoiceStudio."
    ajustes = config.ajustes_voz()
    try:
        datos = sistema.consultar(ajustes.voicestudio_url.rstrip("/") + "/v1/audio/voices",
                                  {"Authorization": f"Bearer {ajustes.voicestudio_clave}"}
                                  if ajustes.voicestudio_clave else {})
        voces = datos.get("voices") if isinstance(datos, dict) else datos
        if not isinstance(voces, list):
            return "sin_confirmar", "VoiceStudio no devolvió una lista de perfiles verificable."
        perfiles = [v for v in voces if isinstance(v, dict) and isinstance(v.get("id"), str)]
        if voces and len(perfiles) != len(voces):
            return "sin_confirmar", "La respuesta de perfiles no permite confirmar la selección."
        if any(v["id"] == ajustes.voicestudio_voz for v in perfiles):
            return "listo", "El perfil configurado existe en VoiceStudio; su calidad se revisa al escucharlo."
        return "pendiente", "No se encontró el perfil configurado entre las voces de VoiceStudio."
    except (requests.RequestException, ValueError, HTTPException, TypeError, AttributeError):
        return "sin_confirmar", "No se pudo consultar el perfil de voz."


@router.get("/preparacion")
def preparacion(forzar: bool = False):
    docker = os.environ.get("FILMCODE_DOCKER") == "1"
    modo = "docker" if docker else "nativo"
    try:
        servicios = sistema.estado_servicios(forzar=forzar)
    except (requests.RequestException, ValueError, HTTPException, TypeError, AttributeError):
        servicios = {}
    ollama = servicios.get("ollama", {})
    estudio = servicios.get("voicestudio", {})
    modelos = ollama.get("modelos", [])
    modelos = modelos if isinstance(modelos, list) else []
    estudio_listo = estudio.get("listo") is True
    ollama_listo = ollama.get("listo") is True or bool(modelos)
    gemma = MODELO in modelos
    manim = version_paquete("manim")
    pango, cairo = version_paquete("manimpango"), version_paquete("pycairo")
    ffmpeg = bool(shutil.which("ffmpeg"))
    ffprobe = bool(shutil.which("ffprobe"))
    perfil, detalle_perfil = estado_perfil(estudio_listo)
    python = ".".join(str(parte) for parte in sys.version_info[:3])
    requisitos = [
        requisito("python", "Python 3.12", "listo" if sys.version_info >= (3, 12) else "pendiente",
                  "Ejecutar FilmCode", f"Intérprete actual: Python {python}.",
                  "Incluido en la imagen de FilmCode." if docker else
                  "Usa Python 3.12 y un entorno .venv para las dependencias del proyecto.",
                  url="https://www.python.org/downloads/"),
        requisito("manim", "Manim", "listo" if manim else "pendiente", "Animar las escenas",
                  f"Versión instalada: {manim}." if manim else "No se encontró el paquete Manim.",
                  "Incluido en la imagen de FilmCode." if docker else
                  "Instala las dependencias del proyecto dentro de .venv.",
                  url="https://docs.manim.community/en/stable/installation/uv.html"),
        requisito("texto", "Pango, Cairo y fuentes", "sin_confirmar" if pango and cairo else "pendiente",
                  "Dibujar texto y código",
                  f"ManimPango {pango} y PyCairo {cairo}; no se ha probado un render." if pango and cairo else
                  "Faltan dependencias de texto; no se ha probado un render.",
                  "La imagen incluye fuentes libres con alias para las fuentes del proyecto." if docker else
                  "Comprueba Segoe UI, Consolas y Cambria Math, o configura equivalentes locales. "
                  "En Linux instala Cairo, Pango y sus cabeceras. LaTeX no hace falta para las escenas actuales.",
                  url="https://docs.manim.community/en/stable/installation/uv.html"),
        requisito("ffmpeg", "FFmpeg y ffprobe", "listo" if ffmpeg and ffprobe else "pendiente",
                  "Audio, video y miniaturas",
                  "Ambos ejecutables están disponibles." if ffmpeg and ffprobe else
                  "FFmpeg o ffprobe no están disponibles en PATH.",
                  "Incluidos en la imagen de FilmCode." if docker else
                  "Instala FFmpeg con ffprobe y añade sus ejecutables a PATH.",
                  url="https://ffmpeg.org/download.html"),
        requisito("ollama", "Ollama local", "listo" if ollama_listo else "pendiente", "Generar el guion",
                  "El servicio local respondió y tiene modelos." if ollama_listo else
                  "No se pudo confirmar Ollama con un modelo instalado.",
                  "Usa el asistente de Windows para instalar Ollama con tu confirmación; "
                  "si ya está instalado, ábrelo tú para comprobarlo.",
                  url="https://ollama.com/download"),
        requisito("gemma", "Gemma 4 12B", "listo" if gemma else "pendiente", "Generar el guion predeterminado",
                  "El modelo predeterminado está instalado en Ollama." if gemma else
                  "Falta el modelo local gemma4:12b. No se descargará automáticamente.",
                  "Si falta, usa el asistente de Windows y confirma la descarga, "
                  "o ejecuta tú el comando de Ollama.", comando="ollama pull gemma4:12b",
                  url="https://ollama.com/library/gemma4:12b", tamano="7,7–8,0 GB de descarga aproximada"),
        requisito("voicestudio", "VoiceStudio local", "listo" if estudio_listo else "pendiente",
                  "Narración local con tu voz", "El servicio respondió a /health." if estudio_listo else
                  "VoiceStudio no responde; no se ha intentado abrirlo.",
                  "El asistente de Windows permite descargar VoiceStudio con tu confirmación. "
                  "Prepara sus motores dentro de la aplicación y desactiva sus analíticas.",
                  url="https://github.com/debpalash/VoiceStudio/releases/latest"),
        requisito("cosyvoice", "CosyVoice 3", "sin_confirmar", "Sintetizar la narración local",
                  "Que VoiceStudio responda no confirma que su motor CosyVoice 3 esté disponible.",
                  "En VoiceStudio comprueba el motor CosyVoice y sus pesos "
                  "FunAudioLLM/Fun-CosyVoice3-0.5B-2512; FilmCode usa el identificador cosyvoice.",
                  url="https://github.com/debpalash/VoiceStudio/blob/main/docs/engines/cosyvoice.md",
                  tamano="Unos 5,4 GB de pesos, más el entorno y sus dependencias"),
        requisito("whisper", "Whisper con tiempos por palabra", "sin_confirmar",
                  "Sincronizar la voz con las escenas",
                  "FilmCode solicita transcripción local con tiempos por palabra; /health no la verifica.",
                  "En VoiceStudio prepara Faster-Whisper o un ASR local compatible con verbose_json "
                  "y tiempos por palabra. El alias whisper-1 usa el motor activo.",
                  url="https://voicestudio.sh/docs/api-reference/audio"),
        requisito("voz", "Tu perfil de voz", perfil, "Clonar tu voz en la narración", detalle_perfil,
                  "Crea una voz en VoiceStudio con audio limpio y su transcripción exacta; "
                  "selecciona ese perfil en FilmCode. Los perfiles personales no se distribuyen.",
                  url="https://voicestudio.sh/docs/voices"),
        requisito("edge", "Voz Edge", "opcional", "Narración alternativa por internet",
                  "Es una alternativa a la voz local; necesita conexión a internet.",
                  "Elige VoiceStudio para una narración totalmente local."),
    ]
    return {"modo": modo, "requisitos": requisitos,
            "capacidades": {"prioridad_dinamica": os.name == "nt" and not docker,
                            "rutas_anfitrion": not docker, "modo": modo},
            "notas": [
                "Esta comprobación no instala paquetes, descarga modelos ni genera audio o video.",
                "CosyVoice y Whisper quedan sin confirmar para evitar iniciar motores durante la comprobación.",
                "El tamaño de descarga no equivale a la RAM o VRAM necesaria; deja memoria y disco libres.",
                "Ollama y VoiceStudio se preparan por separado; la imagen de FilmCode no incluye sus modelos."
                if docker else "Node 22.12 o posterior solo hace falta para compilar la interfaz React.",
            ]}
