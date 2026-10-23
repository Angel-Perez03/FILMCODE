"""Capa de servicio: cada video es una carpeta en videos/<nombre>/ con su manifiesto (proyecto.json) y su
estado (estado.json). Todas las funciones reciben y devuelven datos simples, listas para una API o un frontend.

Flujo completo: crear → generar_guion → renderizar (o todo junto con hacer_video).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from . import guion as g
from . import ingesta
from .config import RAIZ, VIDEOS, ajustes_llm
from .duracion import estimar_segundos, validar_minutos
from .llm import ClienteLLM, ErrorLLM
from .velocidades import validar_velocidades

Progreso = Callable[[str, float], None]
CALIDAD_PREDETERMINADA = "720p30"
RESOLUCIONES = {480: {"bandera": "-ql", "ancho": 854},
                720: {"bandera": "-qm", "ancho": 1280},
                1080: {"bandera": "-qh", "ancho": 1920}}
CALIDADES = {
    f"{alto}p{fps}": {"banderas": [datos["bandera"], "--fps", str(fps)], "voz": "voicestudio",
                     "carpeta": f"{alto}p{fps}", "resolucion": alto, "ancho": datos["ancho"], "fps": fps}
    for alto, datos in RESOLUCIONES.items() for fps in (30, 60)
}
# Los identificadores anteriores siguen abriendo los videos y las cachés ya creados.
# La interfaz ofrece resolución/FPS; estos nombres dejan de representar etapas del proyecto.
CALIDADES.update({
    "silencio": {"banderas": ["-ql"], "voz": "silencio", "carpeta": "480p15", "resolucion": 480, "fps": 15},
    "borrador": {"banderas": ["-ql"], "voz": "edge", "carpeta": "480p15", "resolucion": 480, "fps": 15},
    "alta": {"banderas": ["-qh", "--fps", "30"], "voz": "edge", "carpeta": "1080p30", "resolucion": 1080, "fps": 30},
    "final": {"banderas": ["-qh", "--fps", "30"], "voz": "voicestudio", "carpeta": "1080p30", "resolucion": 1080, "fps": 30},
    "final60": {"banderas": ["-qm", "--fps", "60"], "voz": "voicestudio", "carpeta": "720p60", "resolucion": 720, "fps": 60},
})
ESCENA = Path(__file__).with_name("escena_guion.py")


class ErrorProyecto(RuntimeError):
    """Algo impide seguir con el proyecto (fuente inválida, falta el guion, falló el render…)."""


def _ahora() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def nombre_valido(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpio = re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower()).strip("-")
    return limpio[:60] or "video"


def ruta(nombre: str) -> Path:
    if nombre != nombre_valido(nombre):
        raise ErrorProyecto(f"Nombre de proyecto inválido: {nombre!r}")
    carpeta = VIDEOS / nombre
    if not (carpeta / "proyecto.json").is_file():
        raise ErrorProyecto(f"No existe el proyecto {nombre!r} en {VIDEOS}")
    return carpeta


def _leer(archivo: Path) -> dict:
    return json.loads(archivo.read_text(encoding="utf-8"))


def _escribir(archivo: Path, datos: dict) -> None:
    temporal = archivo.with_suffix(".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    temporal.replace(archivo)


def actualizar_estado(nombre: str, **campos) -> dict:
    archivo = ruta(nombre) / "estado.json"
    estado = _leer(archivo)
    estado.update({k: v for k, v in campos.items() if k != "salidas"}, actualizado=_ahora())
    if "salidas" in campos:
        estado.setdefault("salidas", {}).update(campos["salidas"])
    if "etapa" in campos:
        estado.setdefault("historial", []).append({"etapa": campos["etapa"], "fecha": _ahora()})
    _escribir(archivo, estado)
    return estado


# Crear
def crear(fuente: str | Path, nombre: str | None = None, titulo: str | None = None) -> dict:
    """Copia la fuente (archivo o carpeta) a videos/<nombre>/codigo y deja el proyecto listo."""
    origen = Path(fuente).expanduser().resolve()
    if not origen.exists():
        raise ErrorProyecto(f"No existe la fuente: {origen}")
    if origen.is_file() and origen.stat().st_size > ingesta.MAX_BYTES:
        raise ErrorProyecto(f"El archivo pesa más de {ingesta.MAX_BYTES // 1000} KB.")
    base = nombre_valido(nombre or origen.stem)
    candidato, k = base, 2
    while (VIDEOS / candidato).exists():
        candidato, k = f"{base}-{k}", k + 1
    carpeta = VIDEOS / candidato
    destino = carpeta / "codigo"
    destino.mkdir(parents=True)
    if origen.is_dir():
        for archivo in ingesta.archivos(origen):
            copia = destino / origen.name / archivo.relative_to(origen)
            copia.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archivo, copia)
        copia_rel = f"codigo/{origen.name}"
    else:
        shutil.copy2(origen, destino / origen.name)
        copia_rel = f"codigo/{origen.name}"
    tipo = ingesta.tipo_fuente(origen)
    manifiesto = {"nombre": candidato, "titulo": titulo or origen.stem, "creado": _ahora(), "version": 1,
                  "fuente": {"tipo": tipo, "original": str(origen), "copia": copia_rel}}
    _escribir(carpeta / "proyecto.json", manifiesto)
    _escribir(carpeta / "estado.json", {"etapa": "creado", "mensaje": "proyecto creado", "progreso": 0,
                                        "actualizado": _ahora(), "salidas": {}, "historial": [
                                            {"etapa": "creado", "fecha": _ahora()}]})
    return manifiesto


def leer(nombre: str) -> dict:
    carpeta = ruta(nombre)
    datos = {"manifiesto": _leer(carpeta / "proyecto.json"), "estado": _leer(carpeta / "estado.json")}
    datos["tiene_guion"] = (carpeta / "guion.json").is_file()
    return datos


def listar() -> list[dict]:
    if not VIDEOS.exists():
        return []
    salida = []
    for carpeta in sorted(VIDEOS.iterdir()):
        if (carpeta / "proyecto.json").is_file() and (carpeta / "estado.json").is_file():
            estado = _leer(carpeta / "estado.json")
            salida.append({"nombre": carpeta.name, "etapa": estado.get("etapa"), "actualizado": estado.get("actualizado")})
    return salida


# Guion
def generar_guion(nombre: str, modelo: str | None = None, capturar: bool = True,
                  progreso: Progreso | None = None, duracion_objetivo_minutos: float | None = None) -> dict:
    """El modelo local escribe el guion; se valida y se guarda en guion.json."""
    from .director import Director
    from .director_codigo import DirectorCodigo

    carpeta = ruta(nombre)
    preferencias = _leer(carpeta / "preferencias.json") if (carpeta / "preferencias.json").is_file() else {}
    if not isinstance(preferencias, dict):
        raise ErrorProyecto("Las preferencias del proyecto deben ser un objeto JSON.")
    try:
        objetivo = validar_minutos(duracion_objetivo_minutos if duracion_objetivo_minutos is not None
                                  else preferencias.get("duracion_objetivo_minutos"))
    except ValueError as error:
        raise ErrorProyecto(str(error)) from error
    if duracion_objetivo_minutos is not None:
        _escribir(carpeta / "preferencias.json", {**preferencias, "duracion_objetivo_minutos": objetivo})
    manifiesto = _leer(carpeta / "proyecto.json")
    cliente = ClienteLLM(ajustes_llm(modelo), cache=carpeta / "llm" / "cache", registro=carpeta / "llm" / "registro.jsonl")
    listo, mensaje = cliente.disponible()
    if not listo:
        raise ErrorProyecto(mensaje)

    def avisar(texto: str, fraccion: float) -> None:
        if fraccion >= 0:
            actualizar_estado(nombre, mensaje=texto, progreso=round(fraccion * 100))
        if progreso:
            progreso(texto, fraccion)

    actualizar_estado(nombre, etapa="escribiendo guion", mensaje=f"modelo {cliente.nombre}", progreso=0)
    inicio = time.time()
    try:
        if manifiesto["fuente"]["tipo"] == "documento":
            guion = Director(carpeta, cliente, avisar, capturar, objetivo).documento(carpeta / manifiesto["fuente"]["copia"])
        else:
            guion = DirectorCodigo(carpeta, cliente, avisar, capturar, objetivo).codigo(carpeta / "codigo")
    except ErrorLLM as error:
        actualizar_estado(nombre, etapa="error", mensaje=str(error)[:300])
        raise ErrorProyecto(f"{error}\nLo que ya respondió el modelo quedó en caché: "
                            f"retoma con «continuar {nombre}».") from error
    errores = g.validar(guion, carpeta)
    if errores:
        g.guardar(guion, carpeta / "guion_con_errores.json")
        actualizar_estado(nombre, etapa="error", mensaje="el guion no pasó la validación")
        raise ErrorProyecto("El guion generado tiene errores:\n- " + "\n- ".join(errores[:15]))
    caracteres = sum(len(t) for t in g.textos(guion))
    duracion = {"duracion_objetivo_minutos": objetivo, "duracion_estimada_segundos": estimar_segundos(caracteres)}
    guion["duracion"] = duracion
    if (carpeta / "guion.json").is_file():
        versiones = carpeta / "guion_versiones"
        versiones.mkdir(exist_ok=True)
        shutil.copy2(carpeta / "guion.json", versiones / f"guion_{datetime.now():%Y%m%d_%H%M%S_%f}.json")
    g.guardar(guion, carpeta / "guion.json")
    resumen = {"escenas": len(guion["escenas"]), "caracteres": caracteres, **duracion,
               "modelo": cliente.nombre, "segundos": round(time.time() - inicio)}
    actualizar_estado(nombre, etapa="guion", mensaje="guion listo", progreso=100, guion=resumen)
    return resumen


# Render
def proveedor_voz(calidad: str, voz: str | None = None) -> str:
    """La voz elegida manda; si no se eligió, la que trae la calidad."""
    from .config import PROVEEDORES_VOZ

    elegida = voz or CALIDADES[calidad]["voz"]
    if elegida not in PROVEEDORES_VOZ:
        raise ErrorProyecto(f"Voz desconocida {elegida!r}. Usa: {', '.join(PROVEEDORES_VOZ)}")
    return elegida


def presintetizar(nombre: str, calidad: str = CALIDAD_PREDETERMINADA, progreso: Progreso | None = None,
                  voz: str | None = None, velocidad_voz: float = 1.0) -> dict:
    """Prepara la voz y su alineación en caché, agrupando TTS y ASR para evitar alternar modelos."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from .voz import crear_voz, extraer_marcas

    carpeta = ruta(nombre)
    proveedor = proveedor_voz(calidad, voz)
    voz = crear_voz(proveedor, carpeta / "cache_voz", velocidad=velocidad_voz)
    textos = sorted({extraer_marcas(t)[0] for t in g.textos(g.cargar(carpeta / "guion.json")) if t.strip()})
    pendientes = [t for t in textos if not voz.en_cache(t)] if proveedor != "silencio" else []
    cacheados = len(textos) - len(pendientes) if proveedor != "silencio" else 0
    fallos = []
    audios_preparados = set(textos) - set(pendientes) if proveedor != "silencio" else set()
    subfase = "audio" if proveedor == "voicestudio" and pendientes else "sincronizacion"

    def contadores(completados: int) -> dict:
        return {"textos": len(textos), "cacheados": cacheados,
                "generados": completados - len(fallos), "pendientes": len(pendientes) - completados,
                "fallidas": len(fallos), "omitidas": len(textos) if proveedor == "silencio" else 0,
                **({"subfase": "completo" if completados == len(pendientes) else subfase,
                    "audios_preparados": len(audios_preparados)}
                   if proveedor == "voicestudio" else {})}

    def avisar(completados: int) -> None:
        if proveedor == "silencio":
            mensaje = "Sin narración: se omite la generación de voces"
        elif subfase == "audio":
            mensaje = (f"Generando audios: {len(audios_preparados)}/{len(textos)}; "
                       "después se sincronizan las palabras")
        else:
            listas = cacheados + completados - len(fallos)
            tarea = "Sincronizando palabras" if proveedor == "voicestudio" else "Generando voces"
            mensaje = (f"{tarea}: {listas}/{len(textos)} "
                       f"({cacheados} en caché; {len(pendientes) - completados} pendientes; {len(fallos)} fallos)")
        actualizar_estado(nombre, fase_render="voces", mensaje=mensaje, progreso=None, voces=contadores(completados))
        if progreso:
            progreso(mensaje, -1)

    avisar(0)
    if proveedor == "voicestudio":
        # Genera exactamente los mismos MP3 primero y alinea después. No se omite ASR ni se cambian voces.
        for texto in pendientes:
            try:
                voz.preparar_audio(texto)
                audios_preparados.add(texto)
            except Exception as error:
                # sintetizar volverá a intentarlo; el fallo solo se contabiliza si también falla ese intento.
                if progreso:
                    progreso(f"Audio pendiente de reintento: {texto[:40]}…: {error}", -1)
            avisar(0)
        subfase = "sincronizacion"
        avisar(0)
    # VoiceStudio corre en la GPU de esta máquina: de a uno para no quedarse sin VRAM.
    with ThreadPoolExecutor(max_workers=1 if proveedor == "voicestudio" else 4) as grupo:
        futuros = {grupo.submit(voz.sintetizar, t): t for t in pendientes}
        for k, futuro in enumerate(as_completed(futuros), 1):
            try:
                futuro.result()
                audios_preparados.add(futuros[futuro])
            except Exception as error:  # el render lo vuelve a intentar uno por uno
                fallos.append(f"{futuros[futuro][:40]}…: {error}")
            avisar(k)
    return {**contadores(len(pendientes)), "fallos": fallos[:5]}


def renderizar(nombre: str, calidad: str = CALIDAD_PREDETERMINADA, progreso: Progreso | None = None, voz: str | None = None,
               velocidad_voz: float | None = None, velocidad_animaciones: float | None = None,
               voz_fluida: bool | None = None) -> dict:
    """Renderiza guion.json con la resolución y los FPS del perfil elegido.

    `voz` cambia la voz de la calidad (edge, voicestudio o silencio) sin tocar la imagen."""
    if calidad not in CALIDADES:
        raise ErrorProyecto(f"Calidad desconocida {calidad!r}. Usa: {', '.join(CALIDADES)}")
    carpeta = ruta(nombre)
    preferencias = _leer(carpeta / "preferencias.json") if (carpeta / "preferencias.json").is_file() else {}
    if not isinstance(preferencias, dict):
        raise ErrorProyecto("Las preferencias del proyecto deben ser un objeto JSON.")
    try:
        velocidad_voz, velocidad_animaciones = validar_velocidades(
            velocidad_voz if velocidad_voz is not None else preferencias.get("velocidad_voz"),
            velocidad_animaciones if velocidad_animaciones is not None else preferencias.get("velocidad_animaciones"))
    except ValueError as error:
        raise ErrorProyecto(str(error)) from error
    fluida = voz_fluida if voz_fluida is not None else preferencias.get("voz_fluida", False)
    if not isinstance(fluida, bool):
        raise ErrorProyecto("El modo de narración continua debe estar activado o desactivado.")
    if not (carpeta / "guion.json").is_file():
        raise ErrorProyecto("El proyecto no tiene guion.json; genera el guion primero.")
    perfil = CALIDADES[calidad]
    proveedor = proveedor_voz(calidad, voz)
    actualizar_estado(nombre, etapa=f"renderizando {calidad}", fase_render="voces",
                      mensaje="Preparando voces", progreso=None, voces=None)
    if proveedor == "voicestudio":
        from .voz import crear_voz

        listo, mensaje = crear_voz("voicestudio", carpeta / "cache_voz").disponible()
        if not listo:
            raise ErrorProyecto(mensaje)
    salida = carpeta / "salida"
    salida.mkdir(exist_ok=True)
    # El límite de Manim (100) borraba casi todos los parciales de un video de cientos de animaciones.
    # Un archivo propio conserva la caché de este proyecto sin cambiar ajustes globales ni la calidad.
    configuracion_cache = salida / "cache-manim.cfg"
    configuracion_cache.write_text("[CLI]\nmax_files_cached = 2000\n", encoding="utf-8")
    entorno = {**os.environ, "VIDEOCODIGO_GUION_ENTRADA": str(carpeta / "guion.json"),
               "VIDEOCODIGO_PROYECTO": str(carpeta), "VIDEOCODIGO_VOZ": proveedor,
               "VIDEOCODIGO_CACHE": str(carpeta / "cache_voz"),
               "VIDEOCODIGO_VELOCIDAD_VOZ": str(velocidad_voz),
               "VIDEOCODIGO_VELOCIDAD_ANIMACIONES": str(velocidad_animaciones),
               "VIDEOCODIGO_VOZ_FLUIDA": "1" if fluida else "0",
               "VIDEOCODIGO_GUION": str(salida / f"narrado_{calidad}.json"),
               "PYTHONIOENCODING": "utf-8", "PYTHONWARNINGS": "ignore"}
    orden = [sys.executable, "-m", "manim", "render", *perfil["banderas"], "--media_dir", str(carpeta / "media"),
             "--config_file", str(configuracion_cache), "--progress_bar", "none", str(ESCENA), "VideoGuion"]
    voces = presintetizar(nombre, calidad, progreso, proveedor, velocidad_voz)
    mensaje_manim = "Renderizando animaciones con Manim"
    actualizar_estado(nombre, fase_render="animaciones", mensaje=mensaje_manim, progreso=None, voces=voces)
    if progreso:
        progreso(mensaje_manim, -1)
    previo = (leer(nombre)["estado"].get("salidas", {}).get(calidad) or {}).get("animaciones")
    registro = salida / f"render_{calidad}.log"
    hechas, inicio = 0, time.time()
    with registro.open("w", encoding="utf-8") as log:
        proceso = subprocess.Popen(orden, cwd=RAIZ, env=entorno, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace")
        for linea in proceso.stdout:
            log.write(linea)
            if re.search(r"Animation \d+", linea):
                hechas += 1
                fraccion = min(hechas / previo, 0.99) if previo else -1
                if hechas % 10 == 0:
                    actualizar_estado(nombre, mensaje=f"{hechas} animaciones", progreso=round(fraccion * 100) if previo else None)
                if progreso:
                    progreso(f"{hechas} animaciones", fraccion)
        codigo = proceso.wait()
    video = carpeta / "media" / "videos" / "escena_guion" / perfil["carpeta"] / "VideoGuion.mp4"
    if codigo != 0 or not video.is_file():
        ultimas = registro.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
        actualizar_estado(nombre, etapa="error", mensaje=f"Manim falló (código {codigo})")
        raise ErrorProyecto("El render falló. Últimas líneas:\n" + "\n".join(ultimas))
    mensaje_exportacion = "Exportando video, subtítulos y datos"
    actualizar_estado(nombre, fase_render="exportacion", mensaje=mensaje_exportacion, progreso=None)
    if progreso:
        progreso(mensaje_exportacion, -1)
    destino = salida / f"{calidad}.mp4"
    shutil.copy2(video, destino)
    subtitulos = video.with_suffix(".srt")
    if subtitulos.is_file():
        shutil.copy2(subtitulos, salida / f"{calidad}.srt")
    info = {"ruta": str(destino), "duracion": _duracion(destino), "megas": round(destino.stat().st_size / 1e6, 1),
            "resolucion": perfil["resolucion"], "fps": perfil["fps"],
            "animaciones": hechas, "segundos_render": round(time.time() - inicio), "fecha": _ahora(), "voz": proveedor,
            "velocidad_voz": velocidad_voz, "velocidad_animaciones": velocidad_animaciones, "voz_fluida": fluida}
    narrado = salida / f"narrado_{calidad}.json"
    if narrado.is_file():
        datos = _leer(narrado)
        info.update(caracteres_narrados=datos.get("caracteres"))
    actualizar_estado(nombre, etapa=calidad, fase_render="terminado", mensaje=f"video {calidad} listo",
                      progreso=100, salidas={calidad: info})
    return info


def _duracion(video: Path) -> float | None:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                           capture_output=True, text=True, timeout=30, check=True)
        return round(float(r.stdout.strip()), 1)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def fotogramas(nombre: str, calidad: str = CALIDAD_PREDETERMINADA, cada: float = 5.0) -> list[str]:
    """Hojas de miniaturas del video para revisarlo de un vistazo (una imagen cada `cada` segundos)."""
    carpeta = ruta(nombre)
    video = carpeta / "salida" / f"{calidad}.mp4"
    if not video.is_file():
        raise ErrorProyecto(f"No hay video {calidad} todavía.")
    destino = carpeta / "salida" / f"hojas_{calidad}"
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"fps=1/{cada},scale=640:-1,tile=3x3",
                    "-fps_mode", "vfr", str(destino / "hoja_%02d.jpg")], check=True, timeout=600)
    return [str(p) for p in sorted(destino.glob("hoja_*.jpg"))]


def continuar(nombre: str, modelo: str | None = None, calidad: str = CALIDAD_PREDETERMINADA, capturar: bool = True,
              progreso: Progreso | None = None, voz: str | None = None,
              duracion_objetivo_minutos: float | None = None, velocidad_voz: float | None = None,
              velocidad_animaciones: float | None = None, voz_fluida: bool | None = None) -> dict:
    """Retoma un proyecto: termina el guion si falta (lo ya respondido por el modelo sale de la caché) y renderiza."""
    guion = None
    if not (ruta(nombre) / "guion.json").is_file():
        guion = generar_guion(nombre, modelo, capturar, progreso, duracion_objetivo_minutos)
    return {"proyecto": nombre, "guion": guion,
            "video": renderizar(nombre, calidad, progreso, voz, velocidad_voz, velocidad_animaciones, voz_fluida)}


def hacer_video(fuente: str | Path, nombre: str | None = None, modelo: str | None = None, calidad: str = CALIDAD_PREDETERMINADA,
                capturar: bool = True, progreso: Progreso | None = None, voz: str | None = None,
                duracion_objetivo_minutos: float | None = None, velocidad_voz: float | None = None,
                velocidad_animaciones: float | None = None, voz_fluida: bool | None = None) -> dict:
    """Todo de una: crear el proyecto, escribir el guion con el modelo local y renderizar."""
    manifiesto = crear(fuente, nombre)
    guion = generar_guion(manifiesto["nombre"], modelo, capturar, progreso, duracion_objetivo_minutos)
    video = renderizar(manifiesto["nombre"], calidad, progreso, voz, velocidad_voz, velocidad_animaciones, voz_fluida)
    return {"proyecto": manifiesto["nombre"], "guion": guion, "video": video}
