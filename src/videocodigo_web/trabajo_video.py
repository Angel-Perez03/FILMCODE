"""Trabajos web con duración fija o salida vertical, sobre el render de FilmCode."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from videocodigo import config, proyecto
from videocodigo.cli import _progreso
from videocodigo.duracion import validar_minutos
from videocodigo.velocidades import validar_velocidades

from .ajuste_guion import preparar_guion
from .archivos import archivo_seguro, carpeta_proyecto, escribir_json, leer_json
from .bloqueo_exportacion import ExportacionEnCurso, bloquear_exportacion
from .exportacion import ErrorExportacion, ExportacionCorta, ExportacionLarga, preparar_exportacion
from .formato_video import calidad_base, calidad_salida, calidades_salida
from .medios import capitulos_de
from .seguridad import sanitizar

BORRADOR = "web-borrador"


def _archivos(salida: Path, calidad: str) -> tuple[Path, Path, Path]:
    return tuple(archivo_seguro(salida, nombre) for nombre in (
        f"{calidad}.mp4", f"{calidad}.srt", f"narrado_{calidad}.json"))


@contextmanager
def _render_provisional(base: str, salida: str):
    # Un perfil privado en este proceso reutiliza el render y sus cachés sin
    # sobrescribir el MP4 publicado. La API no reconoce el ID del borrador.
    actualizar = proyecto.actualizar_estado

    def estado_provisional(nombre, **campos):
        if BORRADOR in campos.get("salidas", {}):
            return actualizar(nombre, fase_render="exportacion", mensaje="Comprobando la duración y el formato", progreso=None)
        if campos.get("etapa") == f"renderizando {BORRADOR}":
            campos["etapa"] = f"renderizando {salida}"
        return actualizar(nombre, **campos)

    proyecto.CALIDADES[BORRADOR] = proyecto.CALIDADES[base]
    proyecto.actualizar_estado = estado_provisional
    try:
        yield
    finally:
        proyecto.actualizar_estado = actualizar
        del proyecto.CALIDADES[BORRADOR]


def _publicar(temporales: tuple[Path, ...], destinos: tuple[Path, ...], confirmar) -> None:
    """Valida todos los insumos antes de cambiar una salida y revierte si falla."""
    copias: dict[Path, Path] = {}
    cambiados: list[Path] = []
    if not temporales[0].is_file() or not temporales[2].is_file():
        raise ErrorExportacion("Faltan archivos del video provisional.")
    try:
        for destino in destinos:
            if destino.is_file():
                copia = destino.with_name(f".{destino.name}.{uuid.uuid4().hex}.bak")
                try:
                    os.link(destino, copia)
                except OSError:
                    shutil.copy2(destino, copia)
                copias[destino] = copia
        for temporal, destino in zip(temporales, destinos, strict=True):
            if temporal.is_file():
                temporal.replace(destino)
            else:
                destino.unlink(missing_ok=True)
            cambiados.append(destino)
        confirmar()
    except Exception:
        recuperacion_pendiente = False
        for destino in reversed(cambiados):
            try:
                if destino in copias:
                    copias[destino].replace(destino)
                else:
                    destino.unlink(missing_ok=True)
            except OSError:
                # Si Windows bloquea el destino, conserva el respaldo para recuperarlo.
                copias.pop(destino, None)
                recuperacion_pendiente = True
        if recuperacion_pendiente:
            raise ErrorExportacion("Un archivo está bloqueado. Se conservó el respaldo de la exportación anterior.") from None
        raise
    finally:
        for copia in copias.values():
            copia.unlink(missing_ok=True)


def renderizar(nombre: str, base: str, orientacion: str, segundos: int | None, voz: str | None,
               ritmo: float, animaciones: float, fluida: bool, progreso=_progreso) -> dict:
    carpeta = carpeta_proyecto(nombre)
    salida = archivo_seguro(carpeta, "salida")
    salida.mkdir(exist_ok=True)
    calidad = calidad_salida(base, orientacion)
    temporales = _archivos(salida, BORRADOR)
    destinos = _archivos(salida, calidad)
    log_provisional = archivo_seguro(salida, f"render_{BORRADOR}.log")
    log_final = archivo_seguro(salida, f"render_{calidad}.log")
    for relativa in ("guion.json", "estado.json", "estado.tmp", "preferencias.json", "cache_voz", "media", "salida/cache-manim.cfg"):
        archivo_seguro(carpeta, relativa)
    for archivo in (*temporales, log_provisional):
        archivo.unlink(missing_ok=True)

    def ajustar(presupuesto=None, fuente=None):
        progreso("Ajustando el guion a la duración elegida", -1)
        resultado = preparar_guion(carpeta, segundos, ritmo, animaciones, fluida,
                                   segundos_presupuesto=presupuesto, guion_fuente=fuente)
        if resultado.modificado:
            progreso("Guion ajustado; se conservó la versión anterior", -1)
        return resultado

    try:
        inicial = leer_json(archivo_seguro(carpeta, "guion.json"), {}) if segundos is not None else None
        ajuste = ajustar() if segundos is not None else None
        for intento in range(2):
            for archivo in temporales:
                archivo.unlink(missing_ok=True)
            with _render_provisional(base, calidad):
                info = proyecto.renderizar(nombre, BORRADOR, progreso, voz, ritmo, animaciones, fluida)
            progreso("Ajustando el archivo final", -1)
            try:
                medicion = preparar_exportacion(*temporales, segundos=segundos, calidad=calidad)
            except (ExportacionCorta, ExportacionLarga) as error:
                if intento or segundos is None or ajuste is None:
                    raise
                faltan_escenas = isinstance(error, ExportacionCorta)
                if faltan_escenas and not ajuste.modificado:
                    raise
                # El tiempo real de la voz y las animaciones corrige la estimación inicial.
                presupuesto = min(7200, ajuste.segundos_estimados * segundos / error.duracion_original * 0.97)
                ajuste = ajustar(presupuesto, inicial if faltan_escenas else None)
                if not ajuste.modificado:
                    raise
                continue
            break

        narracion = leer_json(temporales[2], {})
        guion = leer_json(archivo_seguro(carpeta, "guion.json"), {})
        escribir_json(temporales[2], {**narracion, "capitulos": capitulos_de(guion, narracion)})
        info.update(medicion, ruta=str(destinos[0]), fecha=datetime.now().isoformat(timespec="milliseconds"),
                    duracion_fija_segundos=segundos)
        with bloquear_exportacion(carpeta):
            _publicar(temporales, destinos, lambda: proyecto.actualizar_estado(
                nombre, etapa=calidad, fase_render="terminado", mensaje=f"Video {calidad} listo", progreso=100,
                salidas={calidad: info}))
        return info
    finally:
        if log_provisional.is_file():
            try:
                log_provisional.replace(log_final)
            except OSError:
                pass  # Un visor puede tener abierto el registro anterior.
        for archivo in temporales:
            archivo.unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tipo", choices=("guion", "render", "continuar", "fotogramas"))
    parser.add_argument("nombre")
    parser.add_argument("--calidad", choices=calidades_salida(), default=proyecto.CALIDAD_PREDETERMINADA)
    parser.add_argument("--orientacion", choices=("horizontal", "vertical"), default="horizontal")
    parser.add_argument("--modelo")
    parser.add_argument("--sin-capturas", action="store_true")
    parser.add_argument("--duracion-minutos", type=float)
    parser.add_argument("--voz", choices=config.PROVEEDORES_VOZ)
    parser.add_argument("--velocidad-voz", type=float, default=1.15)
    parser.add_argument("--velocidad-animaciones", type=float, default=1.0)
    fluidez = parser.add_mutually_exclusive_group()
    fluidez.add_argument("--voz-fluida", dest="fluida", action="store_true", default=True)
    fluidez.add_argument("--sin-voz-fluida", dest="fluida", action="store_false")
    args = parser.parse_args(argv)
    carpeta = None
    try:
        carpeta = carpeta_proyecto(args.nombre)
        if args.tipo == "fotogramas":
            for relativa in (f"salida/{args.calidad}.mp4", f"salida/hojas_{args.calidad}"):
                archivo_seguro(carpeta, relativa)
            datos = proyecto.fotogramas(args.nombre, args.calidad)
        else:
            minutos = validar_minutos(args.duracion_minutos)
            segundos = round(minutos * 60) if minutos is not None else None
            ritmo, animaciones = validar_velocidades(args.velocidad_voz, args.velocidad_animaciones)
            guion = None
            if args.tipo == "guion" or (args.tipo == "continuar" and not archivo_seguro(carpeta, "guion.json").is_file()):
                guion = proyecto.generar_guion(args.nombre, args.modelo, not args.sin_capturas, _progreso, minutos)
            if args.tipo == "guion":
                if segundos is not None:
                    preparar_guion(carpeta, segundos, ritmo, animaciones, args.fluida)
                datos = leer_json(archivo_seguro(carpeta, "estado.json"), {}).get("guion", guion)
            else:
                video = renderizar(args.nombre, calidad_base(args.calidad), args.orientacion, segundos,
                                   args.voz, ritmo, animaciones, args.fluida)
                datos = {"proyecto": args.nombre, "guion": guion, "video": video} if args.tipo == "continuar" else video
        print(json.dumps(datos, ensure_ascii=False))
        return 0
    except (ExportacionEnCurso, proyecto.ErrorProyecto, HTTPException, OSError, ValueError) as error:
        mensaje = error.detail if isinstance(error, HTTPException) else str(error)
        print(sanitizar(str(mensaje)), file=sys.stderr)
        if carpeta is not None:
            try:
                archivo_seguro(carpeta, "estado.json")
                archivo_seguro(carpeta, "estado.tmp")
                proyecto.actualizar_estado(args.nombre, etapa="error", mensaje=sanitizar(str(mensaje))[:300], progreso=None)
            except (HTTPException, OSError, ValueError, proyecto.ErrorProyecto):
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
