"""Presupuesto conjunto de CPU con afinidad restaurable, sin tocar Job Objects.

Todos los procesos autorizados comparten los mismos procesadores lógicos. El
porcentaje es discreto: en 16 procesadores, 30/80/10 permiten 25/75/6,25 %.
No reserva CPU, no limita GPU/RAM y nunca termina ni suspende procesos.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

import psutil


class _MutexWindows:
    """Serializa las copias de la API que comparten este checkout."""

    def __init__(self, nombre: str):
        if os.name != "nt":
            raise NotImplementedError("El presupuesto de CPU requiere Windows.")
        self.dll = ctypes.WinDLL("kernel32", use_last_error=True)
        firmas = {
            "CreateMutexW": ([ctypes.c_void_p, ctypes.c_int32, ctypes.c_wchar_p], ctypes.c_void_p),
            "WaitForSingleObject": ([ctypes.c_void_p, ctypes.c_uint32], ctypes.c_uint32),
            "ReleaseMutex": ([ctypes.c_void_p], ctypes.c_int32),
            "CloseHandle": ([ctypes.c_void_p], ctypes.c_int32),
        }
        for nombre_funcion, (argumentos, resultado) in firmas.items():
            funcion = getattr(self.dll, nombre_funcion)
            funcion.argtypes, funcion.restype = argumentos, resultado
        self.manejador = self.dll.CreateMutexW(None, False, nombre)
        if not self.manejador:
            raise ctypes.WinError(ctypes.get_last_error())

    def __enter__(self):
        resultado = self.dll.WaitForSingleObject(self.manejador, 5_000)
        if resultado == 0x00000102:
            raise TimeoutError("Otra instancia está actualizando el presupuesto de CPU.")
        # Un mutex abandonado se obtiene igualmente; el registro se guarda antes de cambiar afinidades.
        if resultado not in (0, 0x00000080):
            raise ctypes.WinError(ctypes.get_last_error())
        return self

    def __exit__(self, *_):
        if not self.dll.ReleaseMutex(self.manejador):
            raise ctypes.WinError(ctypes.get_last_error())

    def cerrar(self):
        if self.manejador:
            if not self.dll.CloseHandle(self.manejador):
                raise ctypes.WinError(ctypes.get_last_error())
            self.manejador = None


def _crear_mutex(nombre: str):
    return _MutexWindows(nombre)


class LimiteCPUWindows:
    """Conserva afinidades originales por PID y creación para restaurarlas al acabar.

    Cerrar solo libera el mutex: conserva el presupuesto de trabajos activos al
    reiniciar la API. El controlador debe llamar liberar_limite cuando corresponda.
    """

    def __init__(self, raiz: Path):
        self.raiz = Path(raiz).resolve()
        identidad = str(self.raiz).casefold().encode("utf-8")
        self.nombre = "Local\\FilmCode-CPU-" + hashlib.sha256(identidad).hexdigest()[:24]
        self.archivo = self.raiz / ".web" / "recursos-cpu-originales.json"
        self._mutex = None
        self._bloqueo = threading.RLock()

    @contextmanager
    def _exclusivo(self):
        with self._bloqueo:
            if self._mutex is None:
                self._mutex = _crear_mutex(self.nombre)
            with self._mutex:
                yield

    def _ruta_segura(self):
        for ruta in (self.archivo.parent, self.archivo):
            if ruta.is_symlink() or getattr(ruta, "is_junction", lambda: False)():
                raise OSError("El registro de recursos no puede atravesar enlaces o uniones.")

    def _leer(self) -> list[dict]:
        self._ruta_segura()
        if not self.archivo.exists():
            return []
        if self.archivo.stat().st_size > 1_000_000:
            raise OSError("El registro de afinidades originales es demasiado grande.")
        try:
            datos = json.loads(self.archivo.read_text(encoding="utf-8"))
            entradas = datos["procesos"]
            if datos.get("version") != 1 or not isinstance(entradas, list):
                raise ValueError
            for entrada in entradas:
                if (type(entrada["pid"]) is not int or entrada["pid"] <= 0
                        or type(entrada["creado"]) not in (int, float)):
                    raise ValueError
                for clave in ("original", "aplicada"):
                    mascara = entrada[clave]
                    if (not isinstance(mascara, list) or not mascara
                            or any(type(cpu) is not int or cpu < 0 for cpu in mascara)):
                        raise ValueError
            return entradas
        except (ValueError, KeyError, TypeError) as error:
            raise OSError("El registro de afinidades originales no es válido; no se modificarán procesos.") from error

    def _guardar(self, entradas: list[dict]):
        self._ruta_segura()
        self.archivo.parent.mkdir(exist_ok=True)
        temporal = self.archivo.with_name(f".{self.archivo.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporal.write_text(json.dumps({"version": 1, "procesos": entradas}), encoding="utf-8")
            temporal.replace(self.archivo)
        finally:
            temporal.unlink(missing_ok=True)

    @staticmethod
    def _vivo(entrada: dict):
        try:
            proceso = psutil.Process(entrada["pid"])
            if abs(proceso.create_time() - entrada["creado"]) <= 0.001 and proceso.is_running():
                return proceso
        except psutil.NoSuchProcess:
            pass
        return None

    @staticmethod
    def _mascara(proceso) -> list[int]:
        return sorted(set(proceso.cpu_affinity()))

    def _familias(self, raices, entradas):
        registrados = {entrada["pid"]: dict(entrada) for entrada in entradas}
        procesos = {}
        for raiz in raices:
            procesos[raiz.pid] = raiz
            try:
                hijos = raiz.children(recursive=True)
            except psutil.NoSuchProcess:
                continue
            for hijo in hijos:
                procesos[hijo.pid] = hijo
        for proceso in procesos.values():
            try:
                creado = proceso.create_time()
                if not proceso.is_running():
                    continue
                actual = self._mascara(proceso)
                if proceso.pid in registrados:
                    if abs(registrados[proceso.pid]["creado"] - creado) > 0.001:
                        raise OSError("Un PID cambió durante la actualización de recursos; reintenta.")
                    continue
                original = actual
                # Un hijo nuevo puede haber heredado la cuota del padre ya registrado.
                for padre in proceso.parents():
                    anterior = registrados.get(padre.pid)
                    if (anterior and abs(padre.create_time() - anterior["creado"]) <= 0.001
                            and actual == anterior["aplicada"]):
                        original = anterior["original"]
                        break
                entrada = {"pid": proceso.pid, "creado": creado,
                           "original": list(original), "aplicada": actual}
                registrados[proceso.pid] = entrada
            except psutil.NoSuchProcess:
                continue
        return list(registrados.values())

    def limitar(self, procesos: list[psutil.Process], porcentaje: int) -> None:
        """Aplica una única máscara al conjunto, sin superar las afinidades originales."""
        if type(porcentaje) is not int or not 1 <= porcentaje <= 100:
            raise ValueError("El presupuesto de CPU debe ser un entero entre 1 y 100.")
        if not procesos:
            raise ValueError("Hace falta al menos un proceso autorizado para limitar la CPU.")
        with self._exclusivo():
            anteriores = self._leer()
            vivas = [entrada for entrada in anteriores if self._vivo(entrada) is not None]
            entradas = self._familias(procesos, vivas)
            disponibles = set.intersection(*(set(entrada["original"]) for entrada in entradas)) if entradas else set()
            if not disponibles:
                raise OSError("Los procesos no tienen procesadores permitidos en común.")
            total = psutil.cpu_count(logical=True)
            if not total:
                raise OSError("No se pudo comprobar el número de procesadores lógicos.")
            mascara = sorted(disponibles)[:max(1, total * porcentaje // 100)]
            preparados = []
            for entrada in entradas:
                proceso = self._vivo(entrada)
                if proceso is not None:
                    preparados.append((proceso, self._mascara(proceso), entrada))
                    entrada["aplicada"] = mascara
            # Write-ahead: ninguna afinidad cambia sin dejar antes la original recuperable.
            self._guardar(entradas)
            cambiados = []
            try:
                for proceso, actual, _ in preparados:
                    if actual != mascara:
                        proceso.cpu_affinity(mascara)
                        cambiados.append((proceso, actual))
                    if self._mascara(proceso) != mascara:
                        raise OSError(f"No se pudo confirmar la afinidad del proceso {proceso.pid}.")
            except (psutil.Error, OSError) as error:
                restaurado = True
                for proceso, actual in reversed(cambiados):
                    try:
                        proceso.cpu_affinity(actual)
                    except psutil.NoSuchProcess:
                        continue
                    except (psutil.Error, OSError):
                        restaurado = False
                if restaurado:
                    self._guardar(anteriores)
                detalle = "" if restaurado else " Quedaron afinidades pendientes de restaurar en el registro."
                raise OSError(f"No se pudo aplicar el presupuesto a todos los procesos: {error}.{detalle}") from error

    def consultar(self) -> float | None:
        """Porcentaje real discreto, solo si todos los miembros vivos lo confirman."""
        with self._exclusivo():
            mascaras = []
            for entrada in self._leer():
                proceso = self._vivo(entrada)
                if proceso is not None:
                    actual = self._mascara(proceso)
                    if actual != entrada["aplicada"]:
                        raise OSError("La afinidad real de un proceso no coincide con el presupuesto solicitado.")
                    mascaras.append(actual)
            if not mascaras:
                return None
            if any(mascara != mascaras[0] for mascara in mascaras):
                raise OSError("Los procesos no comparten una única máscara de CPU.")
            total = psutil.cpu_count(logical=True)
            if not total:
                raise OSError("No se pudo comprobar el número de procesadores lógicos.")
            return round(100 * len(mascaras[0]) / total, 2)

    def liberar_limite(self) -> None:
        """Restaura originales verificando PID y creación; conserva pendientes si falla."""
        with self._exclusivo():
            entradas = self._leer()
            if not entradas:
                return
            raices = [proceso for entrada in entradas if (proceso := self._vivo(entrada)) is not None]
            vivas = [entrada for entrada in entradas if self._vivo(entrada) is not None]
            entradas = self._familias(raices, vivas)
            self._guardar(entradas)
            pendientes = []
            for entrada in entradas:
                try:
                    proceso = self._vivo(entrada)
                    if proceso is None:
                        continue
                    proceso.cpu_affinity(entrada["original"])
                    if self._mascara(proceso) != entrada["original"]:
                        raise OSError("Windows no confirmó la afinidad original.")
                except psutil.NoSuchProcess:
                    continue
                except (psutil.Error, OSError):
                    pendientes.append(entrada)
            self._guardar(pendientes)
            if pendientes:
                raise OSError("No se pudo restaurar la afinidad de todos los procesos; "
                              "el registro conserva sus valores originales para reintentar.")

    def cerrar(self) -> None:
        """Cierra solo el mutex: no altera procesos ni borra originales pendientes."""
        with self._bloqueo:
            if self._mutex is not None:
                self._mutex.cerrar()
                self._mutex = None
