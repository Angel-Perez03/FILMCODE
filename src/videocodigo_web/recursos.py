"""Presupuesto de CPU conjunto y vigilancia de RAM, sin cargar modelos."""

from __future__ import annotations

import copy
import ipaddress
import threading
from pathlib import Path
from urllib.parse import urlsplit

import psutil
from fastapi import HTTPException
from videocodigo import config

from .deteccion import proceso_vivo
from .recursos_windows import LimiteCPUWindows
from .seguridad import url_local

GIB = 1024 ** 3
HISTERESIS_RAM = 256 * 1024 ** 2
CPU_MITIGACION = 10
PERFILES = {True: {"perfil": "baja", "cpu": 30, "reserva": 3 * GIB},
            False: {"perfil": "alta", "cpu": 80, "reserva": 2 * GIB}}


def _puertos_servicios() -> tuple[dict[str, int], list[str]]:
    puertos, errores = {}, []
    for nombre, ajustes, atributo in (
        ("Ollama", lambda: config.ajustes_llm("ollama:local"), "url"),
        ("VoiceStudio", lambda: config.ajustes_voz("voicestudio"), "voicestudio_url"),
    ):
        try:
            direccion = urlsplit(url_local(getattr(ajustes(), atributo)))
            puertos[nombre] = direccion.port or 80
        except (HTTPException, ValueError, OSError):
            errores.append(f"{nombre}: no se pudo verificar su puerto local configurado.")
    return puertos, errores


def _es_loopback(direccion: str) -> bool:
    try:
        return ipaddress.ip_address(direccion).is_loopback
    except ValueError:
        return False


def _servicios_locales() -> tuple[dict[str, list[psutil.Process]], list[str]]:
    puertos, errores = _puertos_servicios()
    encontrados: dict[str, list[psutil.Process]] = {nombre: [] for nombre in puertos}
    try:
        conexiones = psutil.net_connections(kind="tcp")
    except (psutil.Error, OSError):
        return encontrados, [*errores, "No hay permisos para identificar los servicios locales."]
    vistos: set[tuple[str, int]] = set()
    for conexion in conexiones:
        if (conexion.status != psutil.CONN_LISTEN or not conexion.laddr
                or not _es_loopback(conexion.laddr.ip)):
            continue
        for nombre, puerto in puertos.items():
            if conexion.laddr.port != puerto or (nombre, conexion.pid) in vistos:
                continue
            vistos.add((nombre, conexion.pid))
            if not conexion.pid:
                errores.append(f"{nombre}: no se pudo identificar el PID del listener local.")
                continue
            try:
                proceso = psutil.Process(conexion.pid)
                proceso.create_time()
                # Confirmar que el PID todavía posee el listener evita reutilizaciones.
                posee_puerto = any(c.status == psutil.CONN_LISTEN and c.laddr
                                  and c.laddr.port == puerto and _es_loopback(c.laddr.ip)
                                  for c in proceso.net_connections(kind="tcp"))
                if proceso.is_running() and posee_puerto:
                    encontrados[nombre].append(proceso)
                else:
                    errores.append(f"{nombre}: cambió la identidad del proceso del servicio.")
            except psutil.NoSuchProcess:
                continue
            except (psutil.Error, OSError):
                errores.append(f"{nombre}: no hay permisos para verificar su proceso.")
    return encontrados, errores


class ControlRecursos:
    """No suspende procesos ni promete una reserva forzada de RAM o GPU."""

    def __init__(self, raiz: Path, fabrica_limite=None):
        self.raiz = Path(raiz).resolve()
        self._fabrica = fabrica_limite or LimiteCPUWindows
        self._limite = None
        self._bloqueo = threading.RLock()
        self._proteccion_ram = False
        self._estado = self._inactivo()

    @staticmethod
    def _inactivo() -> dict:
        return {"activo": False, "perfil": None, "limite_cpu": None, "objetivo_cpu": None, "aplicado": False,
                "ram_libre_gib": 0.0, "reserva_ram_gib": 0.0, "proteccion_ram": False,
                "politica_ram": "mitigacion", "pausado": False, "servicios": [], "errores": [],
                "mensaje": "Sin trabajo activo: los servicios no tienen un límite de FilmCode."}

    def verificar_inicio(self, prioridad_baja: bool) -> None:
        """Rechaza comenzar con menos RAM que la reserva elegida; no lanza nada."""
        if not isinstance(prioridad_baja, bool):
            raise ValueError("Selecciona un perfil de recursos válido.")
        try:
            libre = psutil.virtual_memory().available
        except (psutil.Error, OSError) as error:
            raise RuntimeError("No se pudo comprobar la RAM disponible antes de iniciar.") from error
        perfil = PERFILES[prioridad_baja]
        if libre < perfil["reserva"]:
            raise RuntimeError(f"Hay {libre / GIB:.1f} GiB de RAM disponibles; el perfil "
                               f"{perfil['perfil']} necesita al menos {perfil['reserva'] / GIB:.0f} GiB "
                               "libres para empezar. Cierra otras aplicaciones y vuelve a intentarlo.")

    def actualizar(self, trabajos: list[dict]) -> dict:
        """Recibe el registro; cada raíz se verifica por PID y hora de creación."""
        with self._bloqueo:
            raices = []
            for trabajo in trabajos:
                if trabajo.get("estado") != "corriendo":
                    continue
                proceso = proceso_vivo(trabajo.get("pid"), trabajo.get("proceso_creado"))
                if proceso is not None:
                    raices.append((trabajo, proceso))
            errores = []
            try:
                libre = psutil.virtual_memory().available
            except (psutil.Error, OSError):
                libre = 0
                errores.append("No se pudo medir la RAM disponible; se aplica la mitigación preventiva.")
            if not raices:
                self._proteccion_ram = False
                self._estado = self._inactivo()
                self._estado["ram_libre_gib"] = round(libre / GIB, 2)
                try:
                    if self._limite is None:
                        # Recupera afinidades originales incluso tras una caída de la API.
                        self._limite = self._fabrica(self.raiz)
                    if self._limite is not None:
                        self._limite.liberar_limite()
                except NotImplementedError:
                    pass
                except (RuntimeError, OSError, psutil.Error):
                    errores.append("No se pudo restaurar la afinidad de CPU; revisa los permisos de Windows.")
                    self._estado["mensaje"] = errores[-1]
                self._estado["errores"] = errores
                return self.estado()
            # Si existen varios trabajos recuperados, prevalece el perfil más conservador.
            baja = any(trabajo.get("prioridad_baja") is not False for trabajo, _ in raices)
            perfil = PERFILES[baja]
            if libre < perfil["reserva"]:
                self._proteccion_ram = True
            elif libre >= perfil["reserva"] + HISTERESIS_RAM:
                self._proteccion_ram = False
            porcentaje = CPU_MITIGACION if self._proteccion_ram else perfil["cpu"]
            servicios, fallos_servicios = _servicios_locales()
            errores.extend(fallos_servicios)
            controlados = []
            try:
                if self._limite is None:
                    self._limite = self._fabrica(self.raiz)
                for _trabajo, proceso in raices:
                    try:
                        self._limite.limitar([proceso], porcentaje)
                    except (RuntimeError, OSError, psutil.Error):
                        errores.append(f"FilmCode (PID {proceso.pid}, creado {_trabajo['proceso_creado']:.6f}): "
                                       "no se pudo limitar todo su árbol.")
                for nombre, procesos in servicios.items():
                    if not procesos:
                        continue
                    try:
                        self._limite.limitar(procesos, porcentaje)
                        controlados.append(nombre)
                    except (RuntimeError, OSError, psutil.Error):
                        identidades = []
                        for proceso in procesos:
                            try:
                                identidades.append(f"PID {proceso.pid}, creado {proceso.create_time():.6f}")
                            except (psutil.Error, OSError):
                                identidades.append(f"PID {proceso.pid}, identidad ya no verificable")
                        errores.append(f"{nombre} ({'; '.join(identidades)}): "
                                       "no se pudo incluir todo su árbol en el límite de CPU.")
                real = self._limite.consultar()
                confirmado = type(real) in {int, float} and 0 < real <= porcentaje + 1e-9
                if not confirmado:
                    errores.append("Windows no confirmó una afinidad de CPU dentro del presupuesto solicitado.")
            except (RuntimeError, OSError, psutil.Error):
                confirmado = False
                errores.append("Windows no permitió configurar o comprobar el límite conjunto de CPU.")
            aplicado = confirmado and not errores
            cpu = f"{real:.2f}".replace(".", ",") if confirmado else str(porcentaje)
            if self._proteccion_ram:
                accion = "CPU por afinidad compartida reducida" if aplicado else "se intenta reducir la CPU"
                mensaje = (f"RAM baja: {accion} al {cpu} % del total y nuevos trabajos bloqueados. "
                           "No se pausan procesos ni se libera memoria automáticamente; "
                           "esta mitigación no garantiza evitar que se agote la RAM.")
            else:
                accion = "CPU disponible por afinidad compartida" if aplicado else "Objetivo de CPU conjunta"
                mensaje = (f"{accion}: {cpu} % del total. Se vigilan "
                           f"{perfil['reserva'] / GIB:.0f} GiB libres de RAM; no es una reserva forzada "
                           "ni un límite de GPU.")
            if not aplicado:
                mensaje = "Límite de recursos incompleto. " + mensaje
            self._estado = {"activo": True, "perfil": perfil["perfil"],
                            "limite_cpu": real if confirmado else None, "objetivo_cpu": porcentaje,
                            "aplicado": aplicado, "ram_libre_gib": round(libre / GIB, 2),
                            "reserva_ram_gib": perfil["reserva"] / GIB,
                            "proteccion_ram": self._proteccion_ram, "politica_ram": "mitigacion",
                            "pausado": False, "servicios": controlados, "errores": errores,
                            "mensaje": mensaje}
            return self.estado()

    def estado(self) -> dict:
        with self._bloqueo:
            return copy.deepcopy(self._estado)

    def cerrar(self) -> None:
        """Al dejar de vigilar, restaura la afinidad de los servicios compartidos."""
        with self._bloqueo:
            if self._limite is not None:
                try:
                    self._limite.liberar_limite()
                finally:
                    self._limite.cerrar()
                    self._limite = None
