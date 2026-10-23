"""Trabajos de la CLI, registro persistente y supervisión sin bloquear la API."""

from __future__ import annotations

import copy
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
from fastapi import HTTPException
from videocodigo import config, proyecto
from videocodigo.duracion import validar_minutos
from videocodigo.velocidades import validar_velocidades

from .archivos import archivo_seguro, carpeta_proyecto, escribir_json, invalidar_estado, leer_estado, leer_json
from .deteccion import detener_arbol, externos, proceso_vivo
from .prioridad import aplicar_prioridad, leer_prioridad, mantener_prioridad
from .seguridad import sanitizar

PREFERENCIAS = {"calidad", "modelo", "capturar", "voz", "voz_edge", "voz_voicestudio", "prioridad_baja",
               "duracion_objetivo_minutos", "velocidad_voz", "velocidad_animaciones", "voz_fluida"}


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class GestorTrabajos:
    def __init__(self, raiz: Path, pruebas: bool = False, comando_prueba: list[str] | None = None):
        if comando_prueba is not None and not pruebas:
            raise ValueError("El comando simulado solo se admite en pruebas.")
        self.raiz = Path(raiz).resolve()
        self.registro = archivo_seguro(self.raiz / ".web", "trabajos.json")
        self.bloqueo = threading.RLock()
        self.prueba_voz_activa = False
        self.control_recursos = None
        self._comando_prueba = comando_prueba
        self._trabajos: dict[str, dict] = {}
        self._procesos: dict[str, subprocess.Popen] = {}
        self._externos: dict[str, dict] = {}
        self._ultima_busqueda = 0.0
        self._ultima_revision_prioridad = 0.0
        self._ultimo_guardado = 0.0
        self._cerrado = False
        if self.registro.is_file():
            datos = leer_json(self.registro, [])
            if not isinstance(datos, list):
                raise ValueError("El registro de trabajos no tiene el formato esperado.")
            self._trabajos = {t["id"]: t for t in datos if isinstance(t, dict) and "id" in t}
        self._actualizar()

    def _guardar(self, forzar: bool = False) -> None:
        if self._cerrado:
            return
        if not forzar and time.monotonic() - self._ultimo_guardado < 1:
            return
        self.registro.parent.mkdir(parents=True, exist_ok=True)
        escribir_json(self.registro, sanitizar(list(self._trabajos.values())))
        self._ultimo_guardado = time.monotonic()

    def _publico(self, trabajo: dict) -> dict:
        datos = copy.deepcopy({k: v for k, v in trabajo.items()
                               if k not in {"cancelando", "reanudado"}})
        datos.setdefault("prioridad_baja", None)
        return sanitizar(datos)

    def _actualizar(self, forzar: bool = False) -> None:
        with self.bloqueo:
            cambio = False
            for trabajo in self._trabajos.values():
                if trabajo.get("estado") != "corriendo" or trabajo.get("cancelando"):
                    continue
                manejador = self._procesos.get(trabajo["id"])
                if manejador and manejador.poll() is not None:
                    self._procesos.pop(trabajo["id"], None)
                instantanea = {}
                if re.fullmatch(r"[a-f0-9]{32}", trabajo["id"]):
                    archivo = archivo_seguro(self.registro.parent, f"supervisores/{trabajo['id']}.json")
                    instantanea = leer_json(archivo, {})
                if isinstance(instantanea, dict) and instantanea:
                    campos = {k: v for k, v in instantanea.items() if k in {
                        "estado", "progreso", "mensaje", "lineas", "lineas_total", "resultado", "error", "fin"}}
                    trabajo.update(campos)
                    if trabajo["estado"] != "corriendo":
                        invalidar_estado(trabajo["proyecto"])
                        cambio = True
                        continue
                vivo = proceso_vivo(trabajo.get("pid"), trabajo.get("proceso_creado"))
                try:
                    estado = leer_estado(trabajo["proyecto"])
                except (HTTPException, OSError, ValueError, proyecto.ErrorProyecto):
                    estado = {}
                if vivo:
                    if not instantanea:
                        trabajo.update(progreso=estado.get("progreso"), mensaje=estado.get("mensaje", "Trabajo recuperado"))
                    continue
                etapa = estado.get("etapa", "")
                reciente = estado.get("actualizado", "") >= trabajo.get("inicio", "~")
                final = "terminado" if reciente and etapa in proyecto.CALIDADES else "interrumpido"
                if reciente and etapa == "error":
                    final = "error"
                trabajo.update(estado=final, fin=ahora(), mensaje=estado.get("mensaje") or "El proceso ya no está activo")
                if final != "terminado":
                    trabajo["error"] = trabajo["mensaje"]
                cambio = True
            if forzar or time.monotonic() - self._ultima_busqueda >= 1:
                propios = {t["pid"] for t in self._trabajos.values() if t.get("estado") == "corriendo" and t.get("pid")}
                hallados = externos(self.raiz, propios)
                actuales = {}
                for dato in hallados:
                    identificador = f"externo-{dato['pid']}-{int(dato['proceso_creado'] * 1000)}"
                    trabajo = self._externos.get(identificador, {
                        "id": identificador, "externo": True, "estado": "corriendo", "calidad": None,
                        "inicio": datetime.fromtimestamp(dato["proceso_creado"]).isoformat(timespec="seconds"),
                        "fin": None, "progreso": None, "mensaje": "Trabajo iniciado desde una terminal",
                        "resultado": None, "error": None, "lineas": [], "lineas_total": 0,
                    })
                    trabajo.update(dato)
                    actuales[identificador] = trabajo
                self._externos = actuales
                self._ultima_busqueda = time.monotonic()
            if time.monotonic() - self._ultima_revision_prioridad >= 1:
                for trabajo in [*self._trabajos.values(), *self._externos.values()]:
                    if trabajo.get("estado") != "corriendo" or trabajo.get("cancelando"):
                        continue
                    vivo = proceso_vivo(trabajo.get("pid"), trabajo.get("proceso_creado"))
                    prioridad = None
                    if vivo is not None:
                        try:
                            # También cubre supervisores antiguos y trabajos de terminal.
                            mantener_prioridad(vivo)
                            prioridad = leer_prioridad(vivo)
                        except (psutil.Error, OSError, NotImplementedError):
                            pass
                    if trabajo.get("prioridad_baja") != prioridad:
                        cambio = True
                    trabajo["prioridad_baja"] = prioridad
                self._ultima_revision_prioridad = time.monotonic()
            if cambio:
                self._guardar(True)

    def ocupado(self, nombre: str | None = None) -> dict | None:
        with self.bloqueo:
            self._actualizar()
            for trabajo in [*self._trabajos.values(), *self._externos.values()]:
                if trabajo.get("estado") == "corriendo" and (nombre is None or trabajo["proyecto"] == nombre):
                    return self._publico(trabajo)
        return None

    def situacion(self, nombre: str, estado: dict) -> tuple[str, dict | None]:
        trabajo = self.ocupado(nombre)
        if trabajo:
            if trabajo.get("externo"):
                trabajo.update(progreso=estado.get("progreso"), mensaje=estado.get("mensaje", trabajo["mensaje"]))
                return "en_curso_externo", trabajo
            return "en_curso", trabajo
        etapa = estado.get("etapa", "")
        if etapa == "escribiendo guion" or etapa.startswith("renderizando"):
            return "interrumpido", None
        return ("error" if etapa == "error" else "listo"), None

    def listar(self) -> list[dict]:
        with self.bloqueo:
            self._actualizar()
            todos = [*self._trabajos.values(), *self._externos.values()]
            return [self._publico(t) for t in sorted(todos, key=lambda t: t.get("inicio", ""), reverse=True)]

    def obtener(self, identificador: str) -> dict:
        with self.bloqueo:
            self._actualizar()
            trabajo = self._trabajos.get(identificador) or self._externos.get(identificador)
            if trabajo is None:
                raise HTTPException(404, "No existe ese trabajo.")
            if trabajo.get("externo"):
                try:
                    estado = leer_estado(trabajo["proyecto"])
                    trabajo.update(progreso=estado.get("progreso"), mensaje=estado.get("mensaje", trabajo["mensaje"]))
                except (HTTPException, OSError, ValueError, proyecto.ErrorProyecto):
                    pass
            return self._publico(trabajo)

    def iniciar(self, nombre: str, opciones: dict) -> dict:
        from .sistema import comprobar_para_trabajo

        with self.bloqueo:
            carpeta = carpeta_proyecto(nombre)
            if self.prueba_voz_activa:
                raise HTTPException(409, "Hay una prueba de voz en curso.")
            self._actualizar(forzar=True)
            activo = self.ocupado()
            if activo:
                raise HTTPException(409, f"Ya hay un trabajo en curso en {activo['proyecto']}.")
            ruta_preferencias = archivo_seguro(carpeta, "preferencias.json")
            preferencias = leer_json(ruta_preferencias, {})
            preferencias = {k: v for k, v in preferencias.items() if k in PREFERENCIAS} if isinstance(preferencias, dict) else {}
            elegidas = {**preferencias, **{k: v for k, v in opciones.items() if v is not None}}
            for opcion in ("capturar", "prioridad_baja", "voz_fluida"):
                if opcion in elegidas and not isinstance(elegidas[opcion], bool):
                    raise HTTPException(422, "Las preferencias del trabajo contienen un valor no válido.")
            if self.control_recursos is not None:
                try:
                    self.control_recursos.verificar_inicio(elegidas.get("prioridad_baja", True))
                except RuntimeError as error:
                    raise HTTPException(409, str(error)) from error
            try:
                duracion = validar_minutos(elegidas.get("duracion_objetivo_minutos"))
                velocidad_voz, velocidad_animaciones = validar_velocidades(
                    elegidas.get("velocidad_voz"), elegidas.get("velocidad_animaciones"))
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
            tipo = elegidas.get("tipo")
            calidad = elegidas.get("calidad", proyecto.CALIDAD_PREDETERMINADA)
            if tipo not in {"guion", "render", "continuar", "fotogramas"} or calidad not in proyecto.CALIDADES:
                raise HTTPException(422, "Tipo de trabajo o calidad no válidos.")
            modelo = elegidas.get("modelo")
            if modelo and (not isinstance(modelo, str) or not re.fullmatch(r"(?:ollama:)?[a-zA-Z0-9][a-zA-Z0-9_.:/-]{0,180}", modelo) or modelo.startswith("openai:")):
                raise HTTPException(422, "Selecciona un modelo local de Ollama.")
            voz = elegidas.get("voz")
            if voz is not None and voz not in config.PROVEEDORES_VOZ:
                raise HTTPException(422, "La voz seleccionada no es válida.")
            if not self._comando_prueba:
                comprobar_para_trabajo(nombre, elegidas)
            comando = [sys.executable, "-m", "videocodigo", tipo, nombre]
            if tipo in {"render", "continuar", "fotogramas"}:
                if tipo != "fotogramas":
                    comando += ["--velocidad-voz", str(velocidad_voz), "--velocidad-animaciones", str(velocidad_animaciones)]
                    if elegidas.get("voz_fluida") is True:
                        comando.append("--voz-fluida")
                    elif elegidas.get("voz_fluida") is False:
                        comando.append("--sin-voz-fluida")
                comando += ["--calidad", calidad]
                if voz and tipo != "fotogramas":
                    comando += ["--voz", voz]
            if tipo in {"guion", "continuar"}:
                if duracion is not None:
                    comando += ["--duracion-minutos", str(duracion)]
                if modelo:
                    comando += ["--modelo", modelo]
                if elegidas.get("capturar") is False:
                    comando.append("--sin-capturas")
            entorno = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1",
                       "VIDEOCODIGO_RAIZ": str(self.raiz), "NO_PROXY": "localhost,127.0.0.1,::1",
                       "no_proxy": "localhost,127.0.0.1,::1"}
            for opcion, variable in [("voz_edge", "EDGE_VOZ"), ("voz_voicestudio", "VOICESTUDIO_VOZ")]:
                valor = elegidas.get(opcion)
                if valor:
                    if not isinstance(valor, str) or len(valor) > 200 or any(ord(c) < 32 for c in valor):
                        raise HTTPException(422, "La voz seleccionada no es válida.")
                    entorno[variable] = valor
            prioridad_baja = elegidas.get("prioridad_baja", True)
            banderas = 0
            if os.name == "nt":
                banderas = (subprocess.BELOW_NORMAL_PRIORITY_CLASS if prioridad_baja
                            else subprocess.HIGH_PRIORITY_CLASS) | subprocess.CREATE_NO_WINDOW
            identificador = uuid.uuid4().hex
            orden_supervisor = [sys.executable, "-m", "videocodigo_web.supervisor", identificador,
                                *(self._comando_prueba or comando)]
            try:
                proceso = subprocess.Popen(orden_supervisor, cwd=self.raiz, env=entorno,
                                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL, creationflags=banderas,
                                           start_new_session=os.name != "nt")
                creado = psutil.Process(proceso.pid).create_time()
            except (OSError, psutil.Error) as error:
                raise HTTPException(500, "No se pudo iniciar el proceso de FilmCode.") from error
            trabajo = {"id": identificador, "proyecto": nombre, "tipo": tipo, "calidad": calidad,
                       "estado": "corriendo", "inicio": ahora(), "fin": None, "progreso": None,
                       "mensaje": "Iniciando trabajo", "resultado": None, "error": None,
                       "lineas": [], "lineas_total": 0, "pid": proceso.pid, "proceso_creado": creado,
                       "externo": False, "cancelando": False,
                       "prioridad_baja": prioridad_baja if os.name == "nt" else None}
            self._trabajos[identificador] = trabajo
            self._procesos[identificador] = proceso
            try:
                escribir_json(ruta_preferencias, {k: v for k, v in elegidas.items() if k in PREFERENCIAS})
                self._guardar(True)
            except Exception:
                vivo = proceso_vivo(proceso.pid, creado)
                if vivo:
                    detener_arbol(vivo)
                self._procesos.pop(identificador, None)
                self._trabajos.pop(identificador, None)
                raise
            return self._publico(trabajo)

    def preferir_duracion(self, nombre: str, minutos: float | None) -> dict:
        with self.bloqueo:
            carpeta = carpeta_proyecto(nombre)
            if self.ocupado(nombre):
                raise HTTPException(409, "Espera a que termine el trabajo para cambiar la duración del video.")
            try:
                duracion = validar_minutos(minutos)
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
            archivo = archivo_seguro(carpeta, "preferencias.json")
            preferencias = leer_json(archivo, {})
            if not isinstance(preferencias, dict):
                raise HTTPException(422, "Las preferencias del proyecto deben ser un objeto JSON.")
            escribir_json(archivo, {**preferencias, "duracion_objetivo_minutos": duracion})
            return {"duracion_objetivo_minutos": duracion}

    def preferir_velocidades(self, nombre: str, voz: float, animaciones: float, fluida: bool = True) -> dict:
        with self.bloqueo:
            carpeta = carpeta_proyecto(nombre)
            if self.ocupado(nombre):
                raise HTTPException(409, "Espera a que termine el trabajo antes de cambiar las velocidades del video.")
            try:
                voz, animaciones = validar_velocidades(voz, animaciones)
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
            if not isinstance(fluida, bool):
                raise HTTPException(422, "El modo de narración continua debe estar activado o desactivado.")
            archivo = archivo_seguro(carpeta, "preferencias.json")
            preferencias = leer_json(archivo, {})
            if not isinstance(preferencias, dict):
                raise HTTPException(422, "Las preferencias del proyecto deben ser un objeto JSON.")
            valores = {"velocidad_voz": voz, "velocidad_animaciones": animaciones, "voz_fluida": fluida}
            escribir_json(archivo, {**preferencias, **valores})
            return valores

    def preferir_prioridad(self, nombre: str, prioridad_baja: bool) -> dict:
        with self.bloqueo:
            carpeta = carpeta_proyecto(nombre)
            activo = self.ocupado(nombre)
            if activo:
                trabajo = self.cambiar_prioridad(activo["id"], prioridad_baja)
                return {"prioridad_baja": trabajo["prioridad_baja"]}
            archivo = archivo_seguro(carpeta, "preferencias.json")
            preferencias = leer_json(archivo, {})
            if not isinstance(preferencias, dict):
                raise HTTPException(422, "Las preferencias del proyecto deben ser un objeto JSON.")
            escribir_json(archivo, {**preferencias, "prioridad_baja": prioridad_baja})
            return {"prioridad_baja": prioridad_baja}

    def cambiar_prioridad(self, identificador: str, prioridad_baja: bool) -> dict:
        with self.bloqueo:
            self.obtener(identificador)
            trabajo = self._trabajos.get(identificador) or self._externos.get(identificador)
            assert trabajo is not None
            if trabajo["estado"] != "corriendo" or trabajo.get("cancelando"):
                raise HTTPException(409, "El trabajo ya no está en curso.")
            vivo = proceso_vivo(trabajo.get("pid"), trabajo.get("proceso_creado"))
            if vivo is None:
                raise HTTPException(409, "El proceso ya terminó o su identidad cambió.")
            archivo = archivo_seguro(carpeta_proyecto(trabajo["proyecto"]), "preferencias.json")
            preferencias = leer_json(archivo, {})
            if not isinstance(preferencias, dict):
                raise HTTPException(422, "Las preferencias del proyecto deben ser un objeto JSON.")
            try:
                aplicar_prioridad(vivo, prioridad_baja)
            except NotImplementedError as error:
                raise HTTPException(501, str(error)) from error
            except psutil.NoSuchProcess as error:
                raise HTTPException(409, "El trabajo terminó mientras se cambiaba la prioridad.") from error
            except (PermissionError, psutil.AccessDenied) as error:
                raise HTTPException(403, str(error) if isinstance(error, PermissionError)
                                    else "No hay permisos para cambiar la prioridad de este trabajo.") from error
            trabajo["prioridad_baja"] = leer_prioridad(vivo)
            try:
                escribir_json(archivo, {**preferencias, "prioridad_baja": prioridad_baja})
                self._guardar(True)
            except OSError as error:
                raise HTTPException(500, "La prioridad cambió, pero no se pudo guardar la preferencia del proyecto.") from error
            return self._publico(trabajo)

    def cancelar(self, identificador: str, confirmar_externo: bool = False) -> dict:
        with self.bloqueo:
            self.obtener(identificador)
            trabajo = self._trabajos.get(identificador) or self._externos.get(identificador)
            assert trabajo is not None
            if trabajo["estado"] != "corriendo":
                return self._publico(trabajo)
            if trabajo.get("externo") and not confirmar_externo:
                raise HTTPException(409, "Confirma la cancelación del trabajo iniciado fuera de la aplicación.")
            vivo = proceso_vivo(trabajo.get("pid"), trabajo.get("proceso_creado"))
            if vivo is None:
                raise HTTPException(409, "El proceso ya terminó o su identidad cambió.")
            trabajo["cancelando"] = True
        try:
            detener_arbol(vivo)
        except PermissionError as error:
            with self.bloqueo:
                trabajo["cancelando"] = False
            raise HTTPException(409, str(error)) from error
        with self.bloqueo:
            trabajo.update(estado="cancelado", fin=ahora(), mensaje="Trabajo cancelado por el usuario", error=None)
            self._trabajos[identificador] = trabajo
            self._externos.pop(identificador, None)
            carpeta = carpeta_proyecto(trabajo["proyecto"])
            tiene_guion = archivo_seguro(carpeta, "guion.json").is_file()
            archivo_seguro(carpeta, "estado.json")
            archivo_seguro(carpeta, "estado.tmp")
            mensaje = f"{trabajo['tipo']} cancelado por el usuario" if tiene_guion else "guion cancelado; lo que ya respondió el modelo quedó en caché"
            proyecto.actualizar_estado(trabajo["proyecto"], etapa="guion" if tiene_guion else "creado", mensaje=mensaje, progreso=None)
            invalidar_estado(trabajo["proyecto"])
            self._guardar(True)
            return self._publico(trabajo)

    def cerrar(self) -> None:
        # Los procesos largos pertenecen al usuario; cerrar la API no los cancela.
        with self.bloqueo:
            if self._trabajos:
                self._guardar(True)
            self._cerrado = True
