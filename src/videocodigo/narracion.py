"""Escena de Manim con narración sincronizada a la voz.

Uso dentro de una escena:

    with self.narrar("Salimos desde A [[a]], que vale cero.") as n:
        n.esperar("a")
        self.play(grafo.cerrar("A"), run_time=n.resto())

Las marcas [[nombre]] no se pronuncian; indican el instante en que se dice la palabra siguiente.
"""

from __future__ import annotations

import json
import math
import os
import re
from contextlib import contextmanager
from pathlib import Path

from manim import Animation, MovingCameraScene, Scene, Wait, config

from . import estilo, fondos
from .voz import Segmento, crear_voz, extraer_marcas

FRASE = re.compile(r"[^.!?…]+[.!?…]*")


class Narracion:
    """Reloj de un bloque de narración: cuánto falta para una marca o para que termine el audio."""

    def __init__(self, escena: Scene, inicio: float, segmento: Segmento, marcas: dict[str, int]):
        self.escena, self.inicio, self.segmento, self.marcas = escena, inicio, segmento, marcas

    @property
    def duracion(self) -> float:
        return self.segmento.duracion

    def tiempo(self, marca: str) -> float:
        """Segundos desde el inicio del bloque hasta la marca."""
        if marca not in self.marcas:
            raise KeyError(f"La narración no tiene la marca [[{marca}]]. Marcas: {sorted(self.marcas)}")
        return self.segmento.tiempo_en(self.marcas[marca])

    def hasta(self, marca: str, minimo: float = 0.2) -> float:
        """Segundos desde ahora hasta la marca (sirve como run_time)."""
        return max(minimo, self.inicio + self.tiempo(marca) - self.escena.time)

    def esperar(self, marca: str) -> None:
        falta = self.inicio + self.tiempo(marca) - self.escena.time
        if falta > 1.5 / config.frame_rate:
            self.escena.wait(falta)

    def restante(self) -> float:
        return self.inicio + self.duracion - self.escena.time

    def resto(self, minimo: float = 0.3) -> float:
        """run_time que llena lo que queda del audio (útil para la última animación del bloque)."""
        return max(minimo, self.restante())


class EscenaNarrada(MovingCameraScene):
    """Escena base: fondo con profundidad, cámara móvil, voz con caché y resumen de lo narrado al terminar."""

    pausa_entre_bloques = 0.35
    ambiente = "azul"
    velocidad_animaciones = 1.0

    def setup(self) -> None:
        try:
            factor = float(os.environ.get("VIDEOCODIGO_VELOCIDAD_ANIMACIONES", "1"))
        except ValueError as error:
            raise ValueError("La velocidad de las animaciones debe estar entre 0.5 y 2.") from error
        if not math.isfinite(factor) or not 0.5 <= factor <= 2:
            raise ValueError("La velocidad de las animaciones debe estar entre 0.5 y 2.")
        self.velocidad_animaciones = factor
        if os.environ.get("VIDEOCODIGO_VOZ_FLUIDA", "").strip().lower() in {"1", "true", "yes", "on"}:
            # Solo acorta la separación añadida por el motor; nunca el audio
            # ni las pausas que una escena haya pedido de forma explícita.
            self.pausa_entre_bloques = 0.12
        super().setup()
        self.camera.background_color = estilo.FONDO
        ambiente = os.environ.get("VIDEOCODIGO_AMBIENTE", self.ambiente)
        if ambiente != "plano":
            self.camera.background_image = str(fondos.generar(ambiente, ancho=config.pixel_width, alto=config.pixel_height))
            self.camera.init_background()
        cache = Path(os.environ.get("VIDEOCODIGO_CACHE", Path.cwd() / "cache_voz"))
        self.voz = crear_voz(os.environ.get("VIDEOCODIGO_VOZ"), cache)
        self._bloques: list[dict] = []

    def compile_animations(self, *args, **kwargs) -> list[Animation]:
        animaciones = super().compile_animations(*args, **kwargs)
        if self.velocidad_animaciones != 1:
            for animacion in animaciones:
                # Wait conserva el reloj de la voz, sus marcas y las pausas de
                # lectura. Los grupos y movimientos de cámara sí cambian ritmo.
                if not isinstance(animacion, Wait):
                    animacion.set_run_time(animacion.get_run_time() / self.velocidad_animaciones)
        return animaciones

    @contextmanager
    def narrar(self, texto: str, pausa: float | None = None, subtitulos: bool = True):
        limpio, marcas = extraer_marcas(texto)
        segmento = self.voz.sintetizar(limpio)
        inicio = self.time
        if segmento.audio:
            # Directo al escritor: Scene.add_sound descarta el audio si la animación previa vino de caché.
            self.renderer.file_writer.add_sound(segmento.audio, inicio)
        if subtitulos:
            self._subtitular(segmento)
        narracion = Narracion(self, inicio, segmento, marcas)
        yield narracion
        falta = narracion.restante()
        if falta > 1.5 / config.frame_rate:
            self.wait(falta)
        espera = self.pausa_entre_bloques if pausa is None else pausa
        if espera > 0:
            self.wait(espera)
        self._bloques.append({
            "inicio": round(inicio, 3),
            "duracion": round(segmento.duracion, 3),
            "texto": limpio,
            "proveedor": segmento.proveedor,
        })

    def silencio(self, segundos: float) -> None:
        if segundos > 1.5 / config.frame_rate:
            self.wait(segundos)

    def _subtitular(self, segmento: Segmento) -> None:
        for frase in FRASE.finditer(segmento.texto):
            contenido = frase.group().strip()
            if not contenido:
                continue
            ini = segmento.tiempo_en(frase.start())
            fin = segmento.tiempo_en(frase.end()) if frase.end() < len(segmento.texto) else segmento.duracion
            self.add_subcaption(contenido, duration=max(fin - ini, 0.5), offset=ini)

    def tear_down(self) -> None:
        super().tear_down()
        destino = os.environ.get("VIDEOCODIGO_GUION")
        if not destino:
            return
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        Path(destino).write_text(json.dumps({
            "duracion_total": round(self.time, 3),
            "bloques": self._bloques,
            "caracteres": sum(len(b["texto"]) for b in self._bloques),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
