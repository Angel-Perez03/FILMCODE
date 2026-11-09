"""Ajusta en staging el video y todos sus relojes, antes de publicar la salida."""

from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from .formato_video import dimensiones_salida, filtro_vertical, orientacion_salida


class ErrorExportacion(ValueError):
    """La salida no se puede entregar con las propiedades solicitadas."""


class ExportacionLarga(ErrorExportacion):
    def __init__(self, duracion_original: float, objetivo: float):
        self.duracion_original = duracion_original
        super().__init__(f"El video de {duracion_original:.1f} s no cabe en {objetivo:g} s sin acelerar demasiado. "
                         "Acorta el guion o aumenta la duración elegida.")


class ExportacionCorta(ErrorExportacion):
    def __init__(self, duracion_original: float, objetivo: float):
        self.duracion_original = duracion_original
        super().__init__(f"El video de {duracion_original:.1f} s queda muy por debajo de {objetivo:g} s. "
                         "Añade contenido al guion o elige una duración menor.")


@dataclass(frozen=True)
class _Medio:
    duracion: float
    ancho: int
    alto: int
    fps: Fraction
    fotogramas: int | None
    demora_video: float
    demora_audio: float | None


def _segundos(valor: object) -> float:
    if isinstance(valor, bool):
        raise ValueError("Tiempo inválido")
    numero = float(valor)
    if not math.isfinite(numero) or numero < 0:
        raise ValueError("Tiempo inválido")
    return numero


def _sondear(video: Path) -> _Medio:
    try:
        proceso = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration,start_time:stream=codec_type,width,height,avg_frame_rate,nb_frames,start_time",
             "-of", "json", str(video)],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=30, check=True,
        )
        datos = json.loads(proceso.stdout)
        imagen = next(p for p in datos["streams"] if p["codec_type"] == "video")
        audio = next((p for p in datos["streams"] if p["codec_type"] == "audio"), None)
        formato = datos["format"]
        inicio = float(formato.get("start_time", "0"))

        def demora(pista):
            diferencia = float(pista.get("start_time", inicio)) - inicio
            return _segundos(max(diferencia, 0.0))

        fps = Fraction(imagen["avg_frame_rate"])
        duracion = _segundos(formato["duration"])
        ancho, alto = int(imagen["width"]), int(imagen["height"])
        if duracion <= 0 or not 1 <= fps <= 240 or min(ancho, alto) <= 0:
            raise ValueError("Medio vacío o sin frecuencia válida")
        cuadros = imagen.get("nb_frames")
        return _Medio(duracion, ancho, alto, fps, int(cuadros) if cuadros and cuadros != "N/A" else None,
                      demora(imagen), None if audio is None else demora(audio))
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError, StopIteration, ZeroDivisionError) as exc:
        raise ErrorExportacion("No se pudieron comprobar los tiempos del video con FFprobe.") from exc


_TIEMPO = r"\d{2,}:\d{2}:\d{2},\d{3}"
_CUE = re.compile(rf"^({_TIEMPO})[ \t]+-->[ \t]+({_TIEMPO})([^\n]*)$", re.MULTILINE)


def _leer_marca(texto: str) -> float:
    h, m, s = texto.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _marca(segundos: float) -> str:
    segundos, ms = divmod(round(segundos * 1000), 1000)
    minutos, segundos = divmod(segundos, 60)
    horas, minutos = divmod(minutos, 60)
    return f"{horas:02}:{minutos:02}:{segundos:02},{ms:03}"


def _retimar_srt(texto: str, factor: float) -> tuple[str, float]:
    final = 0.0

    def cambiar(cue: re.Match[str]) -> str:
        nonlocal final
        inicio, fin = (_leer_marca(tiempo) for tiempo in cue.groups()[:2])
        if fin < inicio:
            raise ErrorExportacion("Los tiempos de los subtítulos no son válidos.")
        final = max(final, fin)
        return f"{_marca(inicio * factor)} --> {_marca(fin * factor)}{cue[3]}"

    texto, cantidad = _CUE.subn(cambiar, texto)
    if texto.strip() and not cantidad:
        raise ErrorExportacion("No se encontraron tiempos válidos en los subtítulos.")
    return texto, final


def _retimar_narrado(documento: dict, factor: float, total: float) -> float:
    """Desplaza bloques y capítulos si existen; conserva textos y demás metadatos."""
    final = 0.0
    try:
        for bloque in documento["bloques"]:
            inicio = _segundos(bloque["inicio"])
            fin = inicio + _segundos(bloque["duracion"])
            final = max(final, fin)
            bloque["inicio"] = round(inicio * factor, 3)
            bloque["duracion"] = round(round(fin * factor, 3) - bloque["inicio"], 3)
        for capitulo in documento.get("capitulos", []):
            inicio = _segundos(capitulo["inicio"])
            final = max(final, inicio)
            capitulo["inicio"] = round(inicio * factor, 3)
        documento["duracion_total"] = total
    except (TypeError, KeyError, ValueError, AttributeError, OverflowError) as exc:
        raise ErrorExportacion("No se pudieron ajustar los tiempos de la transcripción.") from exc
    return final


def _plan(original: float, contenido: float, objetivo: float, fps: float) -> float:
    if contenido > objetivo:
        # Un pequeño margen de final evita que el redondeo de fotogramas o del tempo recorte el audio.
        factor = (objetivo - min(0.07, 1 / fps + 0.02)) / contenido
        if factor < 0.8:
            raise ExportacionLarga(original, objetivo)
        return factor
    if original < objetivo:
        retencion = min(6.0, objetivo * 0.1)
        factor = max(1.0, (objetivo - retencion) / original)
        if factor > 1.1:
            raise ExportacionCorta(original, objetivo)
        return min(factor, objetivo / contenido)
    return 1.0


def preparar_exportacion(video: Path, subtitulos: Path, narrado: Path, *,
                         segundos: float | None, calidad: str) -> dict:
    """Entrega archivos listos en staging; el llamador publica la salida completa.

    No sustituye el MP4 antes de verificar duración, encuadre y metadatos. Si la
    duración no cae en un fotograma, elige el fotograma más cercano.
    """
    carpeta = video.parent.resolve()
    for ruta in (video, subtitulos, narrado):
        if ruta.resolve().parent != carpeta or ruta.is_symlink() or ruta.is_junction():
            raise ErrorExportacion("La salida temporal no pertenece a la carpeta del render.")

    original = _sondear(video)
    orientacion = orientacion_salida(calidad)
    vertical = filtro_vertical(calidad)
    dimensiones = dimensiones_salida(calidad) if vertical else (original.ancho, original.alto)
    factor, objetivo, fotogramas = 1.0, original.duracion, None
    texto_srt, texto_narrado = None, None
    filtros_video, filtros_audio = [], []

    if segundos is not None:
        try:
            segundos = _segundos(segundos)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ErrorExportacion("La duración de exportación no es válida.") from exc
        if not 1 <= segundos <= 7200:
            raise ErrorExportacion("La duración de exportación debe estar entre 1 y 7200 segundos.")
        fps = float(original.fps)
        fotogramas = round(segundos * fps)
        objetivo = fotogramas / fps
        try:
            srt = subtitulos.read_text(encoding="utf-8-sig") if subtitulos.is_file() else None
            # Valida y calcula el fin sin cambiar el documento que se escribirá después.
            json_narrado = narrado.read_text(encoding="utf-8-sig") if narrado.is_file() else None
            fin_srt = _retimar_srt(srt, 1)[1] if srt is not None else 0.0
            fin_narrado = _retimar_narrado(json.loads(json_narrado), 1, original.duracion) if json_narrado else 0.0
            factor = _plan(original.duracion, max(original.duracion, fin_srt, fin_narrado), objetivo, fps)
            if srt is not None:
                texto_srt = _retimar_srt(srt, factor)[0]
            if json_narrado is not None:
                datos = json.loads(json_narrado)
                _retimar_narrado(datos, factor, round(objetivo, 6))
                texto_narrado = json.dumps(datos, ensure_ascii=False, indent=2)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ErrorExportacion("No se pudieron leer los subtítulos o la transcripción de este render.") from exc

        demora = round(original.demora_video * factor * fps)
        filtros_video += [f"setpts=(PTS-STARTPTS)*{factor:.12f}", f"fps={original.fps}",
                          f"tpad=start_mode=clone:start={demora}:stop_mode=clone:stop=-1",
                          f"trim=end_frame={fotogramas}"]
        if original.demora_audio is not None:
            demora_muestras = round(original.demora_audio * factor * 48000)
            filtros_audio = ["asetpts=PTS-STARTPTS", "aresample=48000"]
            if factor != 1:
                filtros_audio.append(f"atempo={1 / factor:.12f}")
            if demora_muestras:
                filtros_audio.append(f"adelay={demora_muestras}S:all=1")
            # El audio se puede rellenar, pero no se corta. Si sobrepasa el final, no se publica.
            filtros_audio.append(f"apad=whole_len={round(objetivo * 48000)}")

    if vertical:
        filtros_video.append(vertical)
    medido = original
    if filtros_video:
        with TemporaryDirectory(prefix=".exportacion-", dir=carpeta) as directorio:
            temporal = Path(directorio) / "video.mp4"
            orden = ["ffmpeg", "-hide_banner", "-v", "error", "-nostdin", "-y", "-i", str(video),
                     "-map", "0:v:0", "-map", "0:a:0?", "-vf", ",".join(filtros_video),
                     "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
            if filtros_audio:
                orden += ["-af", ",".join(filtros_audio), "-c:a", "aac", "-b:a", "192k"]
            else:
                orden += ["-c:a", "copy"]
            try:
                subprocess.run([*orden, "-movflags", "+faststart", str(temporal)],
                               capture_output=True, timeout=max(120, objetivo * 4 + 30), check=True)
                medido = _sondear(temporal)
                if (medido.ancho, medido.alto) != dimensiones:
                    raise ErrorExportacion("El video exportado no tiene las dimensiones solicitadas.")
                if fotogramas is not None and (medido.fotogramas != fotogramas or
                                                 abs(medido.duracion - objetivo) > 0.002):
                    raise ErrorExportacion("No se pudo verificar la duración solicitada sin cortar el audio.")
                if fotogramas is None and abs(medido.duracion - original.duracion) > 1 / float(original.fps):
                    raise ErrorExportacion("El cambio de orientación alteró la duración del video.")
                if (medido.demora_audio is None) != (original.demora_audio is None):
                    raise ErrorExportacion("El video exportado no conserva la pista de audio original.")

                preparados = []
                for nombre, texto, destino in (("subtitulos.srt", texto_srt, subtitulos),
                                               ("narrado.json", texto_narrado, narrado)):
                    if texto is not None:
                        parte = Path(directorio) / nombre
                        parte.write_text(texto, encoding="utf-8")
                        preparados.append((parte, destino))
                for parte, destino in preparados:
                    parte.replace(destino)
                temporal.replace(video)
            except (OSError, subprocess.SubprocessError) as exc:
                raise ErrorExportacion("FFmpeg no pudo preparar el video para la exportación.") from exc

    return {"duracion": medido.duracion, "megas": round(video.stat().st_size / 1e6, 1),
            "duracion_original": original.duracion, "factor_tiempo": factor,
            "orientacion": orientacion, "ancho": medido.ancho, "alto": medido.alto}
