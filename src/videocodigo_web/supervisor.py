"""Supervisor independiente: conserva trabajos y salidas al reiniciar la API."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import psutil
from videocodigo import config

from .prioridad import mantener_prioridad
from .seguridad import sanitizar

PATRON_PROGRESO = re.compile(r"^\[\s*(?:(\d+(?:\.\d+)?)%|·)\s*\]\s?(.*)$")


def supervisar(archivo: Path, comando: list[str]) -> int:
    config.cargar_entorno()
    bloqueo = threading.RLock()
    estado = {"estado": "corriendo", "progreso": None, "mensaje": "Iniciando trabajo",
              "lineas": [], "lineas_total": 0, "resultado": None, "error": None, "fin": None}
    ultimo_guardado = 0.0
    pendiente = True

    def guardar(forzar=False):
        nonlocal ultimo_guardado, pendiente
        with bloqueo:
            if not forzar and (not pendiente or time.monotonic() - ultimo_guardado < 0.25):
                return
            temporal = archivo.with_name(f".{archivo.name}.{uuid.uuid4().hex}.tmp")
            try:
                temporal.write_text(json.dumps(sanitizar(estado), ensure_ascii=False), encoding="utf-8")
                for intento in range(3):
                    try:
                        temporal.replace(archivo)
                        break
                    except PermissionError:
                        if intento == 2:
                            raise
                        time.sleep(0.05)
            finally:
                temporal.unlink(missing_ok=True)
            ultimo_guardado = time.monotonic()
            pendiente = False

    archivo.parent.mkdir(parents=True, exist_ok=True)
    guardar(True)
    try:
        supervisor = psutil.Process()
        # Windows solo hereda automáticamente las clases baja e inactiva.
        banderas = int(supervisor.nice()) if os.name == "nt" else 0
        proceso = subprocess.Popen(comando, cwd=config.RAIZ, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   creationflags=banderas)
    except (OSError, psutil.Error):
        estado.update(estado="error", error="No se pudo iniciar la CLI de FilmCode.", fin=datetime.now().isoformat(timespec="seconds"))
        guardar(True)
        return 1

    def leer_progreso():
        nonlocal pendiente
        assert proceso.stderr is not None
        for bruto in iter(lambda: proceso.stderr.readline(65536), b""):
            linea = sanitizar(bruto.decode("utf-8", errors="replace").rstrip())[:16000]
            with bloqueo:
                estado["lineas"].append(linea)
                estado["lineas"] = estado["lineas"][-200:]
                estado["lineas_total"] += 1
                pendiente = True
                coincidencia = PATRON_PROGRESO.match(linea)
                if coincidencia:
                    valor, mensaje = coincidencia.groups()
                    estado.update(progreso=min(100, max(0, float(valor))) if valor else None, mensaje=mensaje)
                try:
                    guardar()
                except OSError:
                    # Siempre drenar stderr, incluso si hay un bloqueo breve del disco.
                    pass
        proceso.stderr.close()

    terminado = threading.Event()

    def guardar_pendiente():
        ultima_prioridad = 0.0
        while not terminado.wait(0.25):
            if time.monotonic() - ultima_prioridad >= 1:
                try:
                    mantener_prioridad(supervisor)
                except (psutil.Error, OSError):
                    # La API lee la clase real y puede informar de acceso denegado.
                    pass
                ultima_prioridad = time.monotonic()
            try:
                guardar()
            except OSError:
                pass

    lector = threading.Thread(target=leer_progreso, daemon=True)
    lector.start()
    guardador = threading.Thread(target=guardar_pendiente, daemon=True)
    guardador.start()
    acumulado = bytearray()
    excesivo = False
    assert proceso.stdout is not None
    for bloque in iter(lambda: proceso.stdout.read(65536), b""):
        if len(acumulado) + len(bloque) <= 4_000_000:
            acumulado.extend(bloque)
        else:
            excesivo = True
    proceso.stdout.close()
    codigo = proceso.wait()
    lector.join()
    terminado.set()
    guardador.join()
    resultado, error = None, None
    if codigo == 0 and not excesivo:
        try:
            resultado = sanitizar(json.loads(acumulado.decode("utf-8")))
        except (ValueError, UnicodeError):
            error = "El proceso terminó sin devolver un resultado JSON válido."
    else:
        error = "La respuesta del proceso excedió el límite." if excesivo else "\n".join(estado["lineas"][-30:]) or f"El proceso terminó con código {codigo}."
    estado.update(estado="error" if error else "terminado", fin=datetime.now().isoformat(timespec="seconds"),
                  resultado=resultado, error=error, mensaje=error or "Trabajo terminado",
                  progreso=estado["progreso"] if error else 100)
    guardar(True)
    return 1 if error else 0


def main() -> int:
    if len(sys.argv) < 3 or not re.fullmatch(r"[a-f0-9]{32}", sys.argv[1]):
        return 2
    base = config.RAIZ / ".web"
    carpeta = base / "supervisores"
    if base.is_symlink() or base.is_junction() or carpeta.is_symlink() or carpeta.is_junction():
        return 2
    return supervisar(carpeta / f"{sys.argv[1]}.json", sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
