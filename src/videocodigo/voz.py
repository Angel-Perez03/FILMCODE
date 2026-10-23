"""Síntesis de voz con caché: VoiceStudio (local, render final), edge-tts (borrador) o silencio.

Cada narración devuelve un `Segmento` con la duración y el instante en que suena cada carácter,
para que las animaciones caigan en la palabra exacta. El audio se guarda por huella del texto y
los ajustes: volver a renderizar no vuelve a sintetizar.
"""

from __future__ import annotations

import asyncio
import difflib
import hashlib
import ipaddress
import json
import math
import os
import re
import subprocess
import threading
import unicodedata
import uuid
from dataclasses import asdict, dataclass, fields
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .config import AjustesVoz, ajustes_voz

MARCA = re.compile(r"\[\[([\w\-]+)\]\]")
PALABRA = re.compile(r"\w+")
MAX_CARACTERES = 4500


class ErrorVoz(RuntimeError):
    """Fallo al sintetizar o al consultar el proveedor de voz."""


@dataclass
class Segmento:
    texto: str
    duracion: float
    tiempos: list[float]          # inicio (s) de cada carácter de `texto`
    audio: str | None = None      # ruta al audio; None en modo silencio
    proveedor: str = "silencio"

    def tiempo_en(self, indice: int) -> float:
        if not self.tiempos or indice >= len(self.tiempos):
            return self.duracion
        return self.tiempos[max(indice, 0)]


def extraer_marcas(texto: str) -> tuple[str, dict[str, int]]:
    """Quita las marcas [[nombre]] y devuelve el texto limpio y la posición de cada marca."""
    partes = MARCA.split(texto)
    limpio, marcas = "", {}
    for i, parte in enumerate(partes):
        if i % 2:
            if parte in marcas:
                raise ValueError(f"Marca repetida en la narración: [[{parte}]]")
            marcas[parte] = len(limpio)
            continue
        parte = re.sub(r"\s+", " ", parte)
        if not limpio:
            parte = parte.lstrip()
        elif limpio.endswith(" ") and parte.startswith(" "):
            parte = parte[1:]
        limpio += parte
    limpio = limpio.rstrip()
    return limpio, {k: min(v, len(limpio)) for k, v in marcas.items()}


def interpolar(n: int, anclas: list[tuple[int, float]], duracion: float) -> list[float]:
    """Tiempo por carácter interpolando entre anclas (índice, segundos)."""
    puntos = sorted({(0, 0.0), *anclas, (n, duracion)})
    limpios: list[tuple[int, float]] = []
    for i, t in puntos:
        t = min(max(t, limpios[-1][1] if limpios else 0.0), duracion)
        if limpios and limpios[-1][0] == i:
            continue
        limpios.append((i, t))
    tiempos, k = [], 0
    for i in range(n):
        while k + 1 < len(limpios) and limpios[k + 1][0] <= i:
            k += 1
        a, ta = limpios[k]
        b, tb = limpios[k + 1] if k + 1 < len(limpios) else (n, duracion)
        tiempos.append(ta + (tb - ta) * (i - a) / max(b - a, 1))
    return tiempos


@lru_cache(maxsize=256)
def _duracion_audio_guardada(ruta: str, _tamano: int, _modificado: int) -> float:
    """El tamaño y la fecha invalidan la caché cuando cambia el audio."""
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", ruta],
        capture_output=True, text=True, timeout=30, check=True,
    )
    duracion = float(salida.stdout.strip())
    if not math.isfinite(duracion) or duracion <= 0:
        raise ValueError("El audio no tiene una duración válida.")
    return duracion


def duracion_audio(ruta: Path) -> float | None:
    try:
        ruta = Path(ruta).resolve()
        datos = ruta.stat()
        return _duracion_audio_guardada(str(ruta), datos.st_size, datos.st_mtime_ns)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


@lru_cache(maxsize=256)
def _metadatos_guardados(ruta: str, _tamano: int, _modificado: int) -> dict:
    """Reutiliza JSON ya leído; nunca almacena lecturas fallidas."""
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def _huella(datos: dict) -> str:
    crudo = json.dumps(datos, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(crudo).hexdigest()[:20]


class Voz:
    """Base: valida el texto, consulta la caché y delega en `_generar`."""

    nombre = "base"

    def __init__(self, cache: Path | str):
        self.cache = Path(cache)

    def firma(self) -> dict:
        return {}

    def huella(self, texto: str) -> str:
        return _huella({"proveedor": self.nombre, **self.firma(), "texto": texto})

    def en_cache(self, texto: str) -> bool:
        return self._leer_cache(texto.strip()) is not None

    def _leer_cache(self, texto: str) -> Segmento | None:
        meta = self.cache / f"{self.huella(texto)}.json"
        try:
            identidad = meta.stat()
        except FileNotFoundError:
            return None
        datos = dict(_metadatos_guardados(str(meta.resolve()), identidad.st_size, identidad.st_mtime_ns))
        audio = self.cache / datos["audio"] if datos.get("audio") else None
        if audio is not None and not audio.is_file():
            return None
        datos["audio"] = str(audio) if audio else None
        # El consumidor recibe su propia lista; no puede modificar la caché.
        datos["tiempos"] = list(datos["tiempos"])
        campos = {f.name for f in fields(Segmento)}
        return Segmento(**{k: v for k, v in datos.items() if k in campos})

    @staticmethod
    def _validar_texto(texto: str) -> str:
        texto = texto.strip()
        if not texto:
            raise ErrorVoz("La narración está vacía.")
        if len(texto) > MAX_CARACTERES:
            raise ErrorVoz(f"Narración de {len(texto)} caracteres; parte el bloque (máximo {MAX_CARACTERES}).")
        return texto

    def sintetizar(self, texto: str) -> Segmento:
        texto = self._validar_texto(texto)
        self.cache.mkdir(parents=True, exist_ok=True)
        clave = self.huella(texto)
        meta = self.cache / f"{clave}.json"
        existente = self._leer_cache(texto)
        if existente is not None:
            return existente
        segmento = self._generar(texto, self.cache / f"{clave}.mp3")
        guardado = asdict(segmento)
        guardado["audio"] = Path(segmento.audio).name if segmento.audio else None
        meta.write_text(json.dumps(guardado, ensure_ascii=False), encoding="utf-8")
        return segmento

    def _generar(self, texto: str, destino: Path) -> Segmento:  # pragma: no cover - abstracto
        raise NotImplementedError


class VozSilencio(Voz):
    """Sin audio: estima la duración por número de palabras. Sirve para revisar ritmo e imagen."""

    nombre = "silencio"

    def __init__(self, cache: Path | str = ".", palabras_por_minuto: int = 150):
        super().__init__(cache)
        self.ppm = palabras_por_minuto

    def sintetizar(self, texto: str) -> Segmento:
        texto = texto.strip()
        if not texto:
            raise ErrorVoz("La narración está vacía.")
        duracion = max(1.0, len(texto.split()) * 60 / self.ppm + 0.3)
        tiempos = [duracion * i / len(texto) for i in range(len(texto))]
        return Segmento(texto, duracion, tiempos, None, self.nombre)


class VozEdge(Voz):
    """Voces neuronales de Microsoft vía edge-tts: gratis, necesita internet."""

    nombre = "edge"

    def __init__(self, cache: Path | str, voz: str = "es-CO-GonzaloNeural", velocidad: str = "+0%"):
        super().__init__(cache)
        self.voz, self.velocidad = voz, velocidad

    def firma(self) -> dict:
        return {"voz": self.voz, "velocidad": self.velocidad}

    def _generar(self, texto: str, destino: Path) -> Segmento:
        import edge_tts

        palabras: list[tuple[float, float, str]] = []

        async def correr() -> None:
            com = edge_tts.Communicate(texto, self.voz, rate=self.velocidad, boundary="WordBoundary")
            with open(destino, "wb") as archivo:
                async for trozo in com.stream():
                    if trozo["type"] == "audio":
                        archivo.write(trozo["data"])
                    elif trozo["type"] == "WordBoundary":
                        palabras.append((trozo["offset"] / 1e7, trozo["duration"] / 1e7, trozo["text"]))

        try:
            asyncio.run(correr())
        except Exception as error:  # edge-tts lanza varios tipos según la red
            destino.unlink(missing_ok=True)
            raise ErrorVoz(f"edge-tts falló ({type(error).__name__}: {error}). ¿Hay internet?") from error
        fin = palabras[-1][0] + palabras[-1][1] + 0.3 if palabras else 1.0
        duracion = duracion_audio(destino) or fin
        anclas, cursor = [], 0
        for inicio, largo, palabra in palabras:
            i = texto.find(palabra, cursor)
            if i < 0:
                continue
            anclas += [(i, inicio), (i + len(palabra), inicio + largo)]
            cursor = i + len(palabra)
        return Segmento(texto, duracion, interpolar(len(texto), anclas, duracion), str(destino), self.nombre)


class VozVoiceStudio(Voz):
    """VoiceStudio (open source, corre en esta máquina) por su API compatible con OpenAI.

    La síntesis no devuelve tiempos, así que el audio se transcribe con el Whisper del mismo
    backend y las palabras reconocidas se alinean con el texto enviado.
    """

    nombre = "voicestudio"

    def __init__(self, cache: Path | str, url: str, voz: str, modelo: str, idioma: str, clave: str = "",
                 estilo: str = ""):
        super().__init__(cache)
        self.url, self.voz, self.modelo, self.idioma, self.estilo = url.rstrip("/"), voz, modelo, idioma, estilo
        self.cabeceras = {"Authorization": f"Bearer {clave}"} if clave else {}
        self._conexiones = threading.local()
        try:
            host = urlsplit(self.url).hostname or ""
        except ValueError:
            host = ""
        self._loopback = host.lower().rstrip(".") == "localhost"
        try:
            self._loopback = self._loopback or ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass

    def _sesion(self) -> requests.Session:
        # Cada hilo reutiliza sus conexiones sin compartir una Session mutable.
        sesion = getattr(self._conexiones, "sesion", None)
        if sesion is None:
            sesion = requests.Session()
            if self._loopback:
                sesion.trust_env = False
            self._conexiones.sesion = sesion
        return sesion

    def firma(self) -> dict:
        firma = {"voz": self.voz, "modelo": self.modelo, "idioma": self.idioma}
        if self.estilo:  # sin estilo la huella no cambia: la caché de antes sigue valiendo
            firma["estilo"] = self.estilo
        return firma

    def disponible(self) -> tuple[bool, str]:
        try:
            r = self._sesion().get(f"{self.url}/health", headers=self.cabeceras, timeout=5)
        except requests.RequestException:
            return False, f"VoiceStudio no responde en {self.url}. Abre la app de VoiceStudio."
        return (True, "VoiceStudio listo") if r.ok else (False, f"VoiceStudio respondió {r.status_code} en /health")

    def _post(self, ruta: str, **kwargs) -> requests.Response:
        try:
            r = self._sesion().post(f"{self.url}{ruta}", headers=self.cabeceras, timeout=600, **kwargs)
        except requests.RequestException as error:
            raise ErrorVoz(f"VoiceStudio no responde en {self.url} ({error}). ¿Está abierta la app?") from error
        if not r.ok:
            raise ErrorVoz(f"VoiceStudio respondió {r.status_code} en {ruta}: {r.text[:300]}")
        return r

    def preparar_audio(self, texto: str) -> float:
        """Genera o recupera el mismo MP3, dejando la alineación para sintetizar."""
        texto = self._validar_texto(texto)
        self.cache.mkdir(parents=True, exist_ok=True)
        destino = self.cache / f"{self.huella(texto)}.mp3"
        return self._asegurar_audio(texto, destino)

    def _asegurar_audio(self, texto: str, destino: Path) -> float:
        # Una transcripción interrumpida puede dejar el audio válido sin su JSON.
        # Su ruta ya incluye la huella del texto y de los ajustes de esta voz.
        duracion = duracion_audio(destino) if destino.is_file() else None
        if duracion is None:
            pedido = {"model": self.modelo, "voice": self.voz, "input": texto, "response_format": "mp3", "language": self.idioma}
            if self.estilo:
                pedido["instruct"] = self.estilo
            r = self._post("/v1/audio/speech", json=pedido)
            destino.write_bytes(r.content)
            duracion = duracion_audio(destino)
        if duracion is None:
            destino.unlink(missing_ok=True)
            raise ErrorVoz("VoiceStudio devolvió algo que no es audio.")
        return duracion

    def _generar(self, texto: str, destino: Path) -> Segmento:
        duracion = self._asegurar_audio(texto, destino)
        with destino.open("rb") as audio:
            datos = self._post("/v1/audio/transcriptions", files={"file": (destino.name, audio, "audio/mpeg")}, data={
                "model": "whisper-1", "response_format": "verbose_json", "language": self.idioma,
                "timestamp_granularities[]": "word",
            }).json()
        palabras = datos.get("words") or [p for s in datos.get("segments") or [] for p in s.get("words") or []]
        tiempos = alinear_palabras(texto, [(float(p["start"]), float(p["end"]), p["word"]) for p in palabras], duracion)
        return Segmento(texto, duracion, tiempos, str(destino), self.nombre)

    def voces(self) -> list[dict]:
        try:
            r = self._sesion().get(f"{self.url}/v1/audio/voices", headers=self.cabeceras, timeout=30)
        except requests.RequestException as error:
            raise ErrorVoz(f"VoiceStudio no responde en {self.url} ({error}).") from error
        if not r.ok:
            raise ErrorVoz(f"VoiceStudio respondió {r.status_code} en /v1/audio/voices: {r.text[:300]}")
        datos = r.json()
        return datos.get("voices", datos)


def _validar_velocidad(valor: float | None) -> float:
    if valor is None:
        try:
            valor = float(os.environ.get("VIDEOCODIGO_VELOCIDAD_VOZ", "1.0"))
        except ValueError as error:
            raise ErrorVoz("La velocidad de voz debe estar entre 0.75 y 1.5.") from error
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or not 0.75 <= valor <= 1.5:
        raise ErrorVoz("La velocidad de voz debe estar entre 0.75 y 1.5.")
    return float(valor)


class VozConVelocidad(Voz):
    """Cambia el tempo de una copia; conserva el audio y la alineación originales."""

    def __init__(self, original: Voz, velocidad: float):
        super().__init__(original.cache / "velocidad")
        self.original = original
        self.nombre = original.nombre
        self.factor = _validar_velocidad(velocidad)

    def firma(self) -> dict:
        return {**self.original.firma(), "velocidad_voz": self.factor, "audio_derivado": "atempo-pcm-v1"}

    def _clave(self, segmento: Segmento | None, texto: str) -> str:
        identidad = None
        if segmento is not None and segmento.audio:
            ruta = Path(segmento.audio).resolve()
            datos = ruta.stat()
            identidad = [str(ruta), datos.st_size, datos.st_mtime_ns]
        return _huella({"original": self.original.huella(texto), "firma": self.firma(), "audio": identidad})

    def huella(self, texto: str) -> str:
        texto = texto.strip()
        return self._clave(self.original._leer_cache(texto), texto)

    def en_cache(self, texto: str) -> bool:
        texto = texto.strip()
        original = self.original._leer_cache(texto)
        if original is None:
            return False
        if original.audio is None:
            return True
        try:
            destino = self.cache / f"{self._clave(original, texto)}.wav"
            return duracion_audio(destino) is not None
        except OSError:
            return False

    def disponible(self) -> tuple[bool, str]:
        return self.original.disponible()

    def preparar_audio(self, texto: str) -> float:
        # La preparación por lotes sigue produciendo solo los MP3 originales.
        return self.original.preparar_audio(texto)

    def voces(self) -> list[dict]:
        return self.original.voces()

    def sintetizar(self, texto: str) -> Segmento:
        original = self.original.sintetizar(texto)
        if original.audio is None:
            duracion = original.duracion / self.factor
            audio = None
        else:
            self.cache.mkdir(parents=True, exist_ok=True)
            destino = self.cache / f"{self._clave(original, original.texto)}.wav"
            duracion = duracion_audio(destino)
            if duracion is None:
                temporal = destino.with_name(f".{destino.stem}.{uuid.uuid4().hex}.wav")
                try:
                    subprocess.run(
                        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                         "-i", original.audio, "-map", "0:a:0", "-vn", "-af", f"atempo={self.factor:g}",
                         "-c:a", "pcm_s16le", "-f", "wav", str(temporal)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120, check=True,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    duracion = duracion_audio(temporal)
                    if duracion is None:
                        raise ErrorVoz("El audio con velocidad ajustada no tiene una duración válida.")
                    temporal.replace(destino)
                except (OSError, subprocess.SubprocessError) as error:
                    detalle = getattr(error, "stderr", None)
                    if isinstance(detalle, bytes):
                        detalle = detalle.decode("utf-8", errors="replace")
                    raise ErrorVoz(f"No se pudo ajustar la velocidad de la voz: {str(detalle or error)[:300]}") from error
                finally:
                    temporal.unlink(missing_ok=True)
            audio = str(destino)
        tiempos = [min(duracion, max(0.0, instante / self.factor)) for instante in original.tiempos]
        return Segmento(original.texto, duracion, tiempos, audio, original.proveedor)


def _normal(palabra: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", palabra).encode("ascii", "ignore").decode()
    return sin_tildes.lower()


def alinear_palabras(texto: str, palabras: list[tuple[float, float, str]], duracion: float) -> list[float]:
    """Tiempo por carácter a partir de palabras reconocidas (inicio, fin, palabra) que pueden no coincidir del todo."""
    propias = list(PALABRA.finditer(texto))
    oidas = [(ini, fin, _normal(m.group())) for ini, fin, p in palabras for m in PALABRA.finditer(p)]
    emparejador = difflib.SequenceMatcher(None, [_normal(m.group()) for m in propias], [o[2] for o in oidas],
                                          autojunk=False)
    anclas = []
    for bloque in emparejador.get_matching_blocks():
        for k in range(bloque.size):
            m, (ini, fin, _) = propias[bloque.a + k], oidas[bloque.b + k]
            anclas += [(m.start(), ini), (m.end(), fin)]
    return interpolar(len(texto), anclas, duracion)


def crear_voz(proveedor: str | None = None, cache: Path | str = "cache_voz", ajustes: AjustesVoz | None = None,
              velocidad: float | None = None) -> Voz:
    factor = _validar_velocidad(velocidad)
    a = ajustes or ajustes_voz(proveedor)
    if a.proveedor == "silencio":
        voz = VozSilencio(cache, a.palabras_por_minuto)
    elif a.proveedor == "edge":
        voz = VozEdge(cache, a.edge_voz, a.edge_velocidad)
    else:
        voz = VozVoiceStudio(cache, a.voicestudio_url, a.voicestudio_voz, a.voicestudio_modelo, a.voicestudio_idioma,
                             a.voicestudio_clave, a.voicestudio_estilo)
    return voz if factor == 1 else VozConVelocidad(voz, factor)


VOCES_EDGE_ES = [
    {"id": "es-CO-GonzaloNeural", "nombre": "Gonzalo", "acento": "Colombia", "genero": "masculino"},
    {"id": "es-CO-SalomeNeural", "nombre": "Salomé", "acento": "Colombia", "genero": "femenino"},
    {"id": "es-MX-JorgeNeural", "nombre": "Jorge", "acento": "México", "genero": "masculino"},
    {"id": "es-MX-DaliaNeural", "nombre": "Dalia", "acento": "México", "genero": "femenino"},
    {"id": "es-AR-TomasNeural", "nombre": "Tomás", "acento": "Argentina", "genero": "masculino"},
    {"id": "es-ES-AlvaroNeural", "nombre": "Álvaro", "acento": "España", "genero": "masculino"},
    {"id": "es-ES-ElviraNeural", "nombre": "Elvira", "acento": "España", "genero": "femenino"},
]
