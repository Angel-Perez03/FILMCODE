"""Proyectos locales e importación de fuentes con límites explícitos."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from shutil import copyfile

from fastapi import APIRouter, HTTPException, Request
from starlette.datastructures import UploadFile
from starlette.concurrency import run_in_threadpool
from videocodigo import guion as contrato_guion
from videocodigo import ingesta, proyecto
from videocodigo.duracion import estimar_segundos

from .archivos import (archivo_seguro, carpeta_proyecto, carpeta_web, es_enlace,
                       escribir_json, invalidar_estado, leer_estado, leer_json, relativa_segura)
from .fuentes import MAX_TOTAL, admitido, copiar_local, inspeccionar
from .formato_video import calidad_base, calidades_salida, dimensiones_salida, orientacion_salida
from .seguridad import MAX_VIDEO_REFERENCIA

router = APIRouter()


def videos_disponibles(carpeta: Path, estado: dict) -> list[dict]:
    guion = archivo_seguro(carpeta, "guion.json")
    modificado = guion.stat().st_mtime if guion.is_file() else 0
    salidas = estado.get("salidas", {})
    salidas = salidas if isinstance(salidas, dict) else {}
    videos = []
    for calidad in calidades_salida():
        archivo = archivo_seguro(carpeta, f"salida/{calidad}.mp4")
        if not archivo.is_file():
            continue
        datos = salidas.get(calidad, {})
        datos = datos if isinstance(datos, dict) else {}
        paleta = datos.get("paleta_referencia")
        paleta = paleta if isinstance(paleta, dict) else {}
        fecha = datos.get("fecha")
        try:
            renderizado = datetime.fromisoformat(fecha).timestamp() if fecha else archivo.stat().st_mtime
        except (TypeError, ValueError):
            renderizado = archivo.stat().st_mtime
        perfil = proyecto.CALIDADES[calidad_base(calidad)]
        ancho, alto = dimensiones_salida(calidad)
        videos.append({"calidad": calidad, "duracion": datos.get("duracion"),
                       "resolucion": datos.get("resolucion", perfil["resolucion"]),
                       "fps": datos.get("fps", perfil["fps"]),
                       "orientacion": orientacion_salida(calidad), "ancho": ancho, "alto": alto,
                       "duracion_fija_segundos": datos.get("duracion_fija_segundos"),
                       "usa_referencia_visual": bool(paleta),
                       "fondo_video": datos.get("fondo_video") or paleta.get("fondo"),
                       "velocidad_voz": datos.get("velocidad_voz"),
                       "megas": datos.get("megas", round(archivo.stat().st_size / 1_000_000, 2)),
                       "fecha": fecha or datetime.fromtimestamp(renderizado).isoformat(timespec="seconds"),
                       "animaciones": datos.get("animaciones"), "segundos_render": datos.get("segundos_render"),
                       "desactualizado": modificado > renderizado})
    return videos


def detalle(nombre: str, gestor) -> dict:
    carpeta = carpeta_proyecto(nombre)
    manifiesto = leer_json(archivo_seguro(carpeta, "proyecto.json"), {})
    if not isinstance(manifiesto, dict):
        raise HTTPException(422, "El manifiesto del proyecto debe ser un objeto JSON.")
    estado = leer_estado(nombre)
    tiene_guion = archivo_seguro(carpeta, "guion.json").is_file()
    guion = leer_json(archivo_seguro(carpeta, "guion.json"), {}) if tiene_guion else {}
    titulo = guion.get("titulo") if isinstance(guion, dict) else None
    # Los proyectos antiguos podían conservar el recuento de un guion anterior.
    # Usa el documento que se va a renderizar, sin modificar su estado durante un trabajo.
    if isinstance(guion, dict) and isinstance(guion.get("escenas"), list):
        try:
            caracteres = sum(len(t) for t in contrato_guion.textos(guion))
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
        else:
            resumen = estado.get("guion") if isinstance(estado.get("guion"), dict) else {}
            estado = {**estado, "guion": {**resumen, "escenas": len(guion["escenas"]),
                      "caracteres": caracteres, "duracion_estimada_segundos": estimar_segundos(caracteres)}}
    situacion, trabajo = gestor.situacion(nombre, estado)
    return {"nombre": nombre, "titulo": titulo or manifiesto.get("titulo", nombre),
            "tipo": manifiesto.get("fuente", {}).get("tipo", "codigo"),
            "etapa": estado.get("etapa", "creado"), "mensaje": estado.get("mensaje", ""),
            "progreso": estado.get("progreso"), "actualizado": estado.get("actualizado"),
            "tiene_guion": tiene_guion,
            "tiene_guion_con_errores": archivo_seguro(carpeta, "guion_con_errores.json").is_file(),
            "videos": videos_disponibles(carpeta, estado), "situacion": situacion, "trabajo": trabajo,
            "miniatura": f"/api/proyectos/{nombre}/miniatura", "manifiesto": manifiesto, "estado": estado,
            "preferencias": leer_json(archivo_seguro(carpeta, "preferencias.json"), {}),
            "archivos": {clave: archivo_seguro(carpeta, ruta).is_file() for clave, ruta in {
                "capturas": "capturas.json", "llm": "llm/registro.jsonl", "guion": "guion.json",
                "guion_con_errores": "guion_con_errores.json"}.items()}}


@router.get("/proyectos")
def listar(request: Request):
    base = Path(proyecto.VIDEOS)
    if not base.exists():
        return []
    if es_enlace(base):
        raise HTTPException(400, "La carpeta de proyectos no puede ser un enlace.")
    salida = []
    for carpeta in sorted(base.iterdir()):
        if carpeta.name.startswith((".", "_")) or es_enlace(carpeta) or not carpeta.is_dir():
            continue
        if carpeta.name != proyecto.nombre_valido(carpeta.name) or not (carpeta / "proyecto.json").is_file():
            continue
        salida.append(detalle(carpeta.name, request.app.state.gestor))
    return sorted(salida, key=lambda item: item.get("actualizado") or "", reverse=True)


@router.get("/proyectos/{nombre}")
def ver(nombre: str, request: Request):
    return detalle(nombre, request.app.state.gestor)


@router.post("/fuentes/revisar")
async def revisar(request: Request):
    datos = await datos_json(request)
    return await run_in_threadpool(inspeccionar, datos.get("ruta"))


async def datos_json(request: Request) -> dict:
    try:
        cuerpo = await request.body()
        if len(cuerpo) > 2_000_000:
            raise HTTPException(413, "La petición supera el límite permitido.")
        datos = json.loads(cuerpo)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(400, "El cuerpo debe ser JSON válido.") from exc
    if not isinstance(datos, dict):
        raise HTTPException(400, "El cuerpo debe ser un objeto JSON.")
    return datos


def nombre_disponible(texto: str) -> str:
    base = proyecto.nombre_valido(texto)
    candidato = base
    numero = 2
    while (Path(proyecto.VIDEOS) / candidato).exists():
        sufijo = f"-{numero}"
        candidato = base[:60 - len(sufijo)].rstrip("-") + sufijo
        numero += 1
    return candidato


def crear_desde(fuente: Path, datos: dict, gestor, referencia=None) -> dict:
    nombre = datos.get("nombre")
    titulo = datos.get("titulo")
    if nombre is not None and (not isinstance(nombre, str) or nombre != proyecto.nombre_valido(nombre)):
        raise HTTPException(400, "Usa un nombre de hasta 60 caracteres, con minúsculas, números y guiones.")
    if titulo is not None and (not isinstance(titulo, str) or len(titulo) > 250):
        raise HTTPException(400, "El título debe tener como máximo 250 caracteres.")
    with gestor.bloqueo:
        if es_enlace(Path(proyecto.VIDEOS)):
            raise HTTPException(400, "La carpeta de proyectos no puede ser un enlace.")
        elegido = nombre_disponible(nombre or fuente.stem)
        creado = proyecto.crear(fuente, nombre=elegido, titulo=titulo)
        if referencia is not None:
            medio, nombre_medio, paleta = referencia
            carpeta = carpeta_proyecto(elegido)
            relativa = f"referencia/estilo{medio.suffix.lower()}"
            destino = archivo_seguro(carpeta, relativa)
            destino.parent.mkdir(exist_ok=True)
            copyfile(medio, destino)
            estado_archivo = destino.stat()
            escribir_json(archivo_seguro(carpeta, "referencia/estilo.json"), {
                "firma": [estado_archivo.st_size, estado_archivo.st_mtime_ns], "paleta": paleta,
            })
            manifiesto = archivo_seguro(carpeta, "proyecto.json")
            creado = {**creado, "referencia_visual": {"archivo": relativa, "nombre": nombre_medio}}
            escribir_json(manifiesto, creado)
        return creado


def _fuente_textual(datos: dict, temporal: Path) -> Path:
    if ("ruta" in datos) == ("markdown" in datos):
        raise HTTPException(400, "Indica una ruta o Markdown, solo una de las dos opciones.")
    if "ruta" in datos:
        return copiar_local(datos["ruta"], temporal)
    contenido = datos["markdown"]
    if not isinstance(contenido, str) or not contenido.strip():
        raise HTTPException(400, "La guía Markdown está vacía.")
    if len(contenido.encode("utf-8")) > ingesta.MAX_BYTES:
        raise HTTPException(400, "El archivo pesa más de 400 KB.")
    fuente = archivo_seguro(temporal, datos.get("archivo", "guia.md"))
    if fuente.suffix.lower() not in ingesta.EXT_DOCUMENTO:
        raise HTTPException(400, "La guía debe usar extensión .md, .markdown o .txt.")
    fuente.parent.mkdir(parents=True, exist_ok=True)
    fuente.write_text(contenido, encoding="utf-8")
    return fuente


def crear_json(datos: dict, gestor) -> dict:
    subidas = archivo_seguro(carpeta_web(), "subidas")
    subidas.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=subidas, prefix="fuente-") as directorio:
        return crear_desde(_fuente_textual(datos, Path(directorio)), datos, gestor)


async def _copiar_referencia(archivo: UploadFile, temporal: Path) -> tuple[Path, str, dict[str, str]]:
    from .referencia_video import ErrorReferenciaVideo, EXTENSIONES_IMAGEN, EXTENSIONES_REFERENCIA, MAX_BYTES_IMAGEN, paleta_referencia

    nombre = relativa_segura(archivo.filename or "")
    extension = nombre.suffix.lower()
    if len(nombre.parts) != 1 or extension not in EXTENSIONES_REFERENCIA:
        raise HTTPException(400, "Selecciona una imagen PNG, JPG o WebP, o un video MP4, WebM, MOV o MKV.")
    limite = MAX_BYTES_IMAGEN if extension in EXTENSIONES_IMAGEN else MAX_VIDEO_REFERENCIA
    demasiado_grande = f"La referencia puede pesar hasta {limite // (1024 * 1024)} MiB."
    if archivo.size is not None and archivo.size > limite:
        raise HTTPException(413, demasiado_grande)
    destino = archivo_seguro(temporal, f"estilo{extension}")

    def guardar():
        total = 0
        with destino.open("xb") as salida:
            while bloque := archivo.file.read(1024 * 1024):
                total += len(bloque)
                if total > limite:
                    raise HTTPException(413, demasiado_grande)
                salida.write(bloque)
        if not total:
            raise HTTPException(400, "El archivo de referencia está vacío.")

    await run_in_threadpool(guardar)
    try:
        paleta = await run_in_threadpool(paleta_referencia, temporal, destino)
    except ErrorReferenciaVideo as error:
        raise HTTPException(422, str(error)) from error
    return destino, nombre.name, paleta


async def crear_subida(request: Request, gestor, con_referencia=False) -> dict:
    subidas = archivo_seguro(carpeta_web(), "subidas")
    subidas.mkdir(exist_ok=True)
    async with request.form(max_files=401 if con_referencia else 400, max_fields=10, max_part_size=400_000) as formulario:
        referencias = formulario.getlist("referencia_visual")
        if con_referencia and (len(referencias) != 1 or not isinstance(referencias[0], UploadFile)):
            raise HTTPException(400, "Selecciona una sola imagen o un solo video de referencia.")
        archivos = [valor for campo, valor in formulario.multi_items()
                    if isinstance(valor, UploadFile) and campo != "referencia_visual"]
        if not con_referencia and (not archivos or referencias):
            raise HTTPException(400, "Selecciona al menos un archivo.")
        if len(archivos) > 400:
            raise HTTPException(400, "La fuente supera el máximo de 400 archivos.")
        datos = {clave: formulario.get(clave) for clave in ("nombre", "titulo") if formulario.get(clave)}
        texto = {clave: formulario.get(clave) for clave in ("ruta", "markdown", "archivo") if clave in formulario}
        if con_referencia and (any(not isinstance(valor, str) for valor in texto.values())
                               or (archivos and ("ruta" in texto or "markdown" in texto))):
            raise HTTPException(400, "Selecciona una sola fuente principal junto con la referencia visual.")
        if con_referencia and not archivos and not ({"ruta", "markdown"} & texto.keys()):
            raise HTTPException(400, "Añade código o una guía para indicar qué debe explicar el video.")
        with tempfile.TemporaryDirectory(dir=subidas, prefix="subida-") as directorio:
            temporal = Path(directorio)
            contenedor = temporal / "fuente"
            contenedor.mkdir()
            referencia = None
            if con_referencia:
                referencia = await _copiar_referencia(referencias[0], temporal)
                if not archivos:
                    fuente = await run_in_threadpool(_fuente_textual, texto, contenedor)
                    return await run_in_threadpool(crear_desde, fuente, datos, gestor, referencia)
            total = 0
            vistos: set[str] = set()
            destinos = []
            for archivo in archivos:
                relativa = relativa_segura(archivo.filename or "")
                if any(parte in ingesta.IGNORAR for parte in relativa.parts) or not admitido(relativa):
                    raise HTTPException(400, "La subida contiene un archivo o una carpeta no admitida.")
                clave = relativa.as_posix().casefold()
                if clave in vistos:
                    raise HTTPException(400, "Hay rutas de archivo repetidas en la subida.")
                vistos.add(clave)
                contenido = await archivo.read(ingesta.MAX_BYTES + 1)
                total += len(contenido)
                if len(contenido) > ingesta.MAX_BYTES or total > MAX_TOTAL:
                    raise HTTPException(400, "Máximo 400 KB por archivo y 20 MB por subida.")
                destino = archivo_seguro(contenedor, relativa)
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(contenido)
                destinos.append(destino)
            if len(destinos) == 1 and len(destinos[0].relative_to(contenedor).parts) == 1:
                fuente = destinos[0]
            else:
                hijos = list(contenedor.iterdir())
                fuente = hijos[0] if len(hijos) == 1 and hijos[0].is_dir() else contenedor
            return await run_in_threadpool(crear_desde, fuente, datos, gestor, referencia)


@router.post("/proyectos", status_code=201)
async def crear(request: Request):
    gestor = request.app.state.gestor
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        return await crear_subida(request, gestor)
    return await run_in_threadpool(crear_json, await datos_json(request), gestor)


@router.post("/proyectos/con-referencia", status_code=201)
async def crear_con_referencia(request: Request):
    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        raise HTTPException(400, "Adjunta la imagen o el video como archivo local.")
    return await crear_subida(request, request.app.state.gestor, con_referencia=True)


@router.post("/proyectos/{nombre}/archivar")
def archivar(nombre: str, request: Request):
    gestor = request.app.state.gestor
    with gestor.bloqueo:
        carpeta = carpeta_proyecto(nombre)
        activo = gestor.ocupado(nombre)
        if activo:
            raise HTTPException(409, "No se puede archivar un proyecto con un trabajo en curso.")
        destino = archivo_seguro(Path(proyecto.VIDEOS),
                                 f"_archivo/{nombre}-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}")
        destino.parent.mkdir(parents=True, exist_ok=True)
        carpeta.rename(destino)
        invalidar_estado(nombre)
        return {"archivado": True, "nombre": nombre, "ruta": str(destino.relative_to(proyecto.VIDEOS))}
