"""Identidad de procesos y trabajos iniciados fuera de la API."""

from __future__ import annotations

import os
import re
from pathlib import Path

import psutil

ORDENES = {"guion", "render", "continuar", "fotogramas", "hacer"}


def proceso_vivo(pid: int | None, creado: float | None) -> psutil.Process | None:
    if not pid or creado is None:
        return None
    try:
        proceso = psutil.Process(pid)
        if abs(proceso.create_time() - creado) > 0.01:
            return None
        if not proceso.is_running() or proceso.status() == psutil.STATUS_ZOMBIE:
            return None
        return proceso
    except (psutil.Error, OSError):
        return None


def _opcion(argumentos: list[str], nombre: str) -> str | None:
    for indice, argumento in enumerate(argumentos):
        if argumento == nombre and indice + 1 < len(argumentos):
            return argumentos[indice + 1]
        if argumento.startswith(nombre + "="):
            return argumento.split("=", 1)[1]
    return None


def identificar(argumentos: list[str], raiz: Path, cwd: str = "") -> tuple[str, str] | None:
    """Solo reconoce argumentos completos; nunca busca coincidencias parciales."""
    try:
        indice = argumentos.index("-m")
    except ValueError:
        return None
    if len(argumentos) <= indice + 2:
        return None
    modulo = argumentos[indice + 1]
    resto = argumentos[indice + 2:]
    if modulo == "videocodigo_web.supervisor":
        if (len(resto) < 6 or not re.fullmatch(r"[a-f0-9]{32}", resto[0])
                or not _es_python(Path(resto[1]).name) or resto[2:4] != ["-m", "videocodigo"]):
            return None
        return identificar(resto[1:], raiz, cwd)
    if modulo == "videocodigo" and len(resto) >= 2 and resto[0] in ORDENES:
        from videocodigo.proyecto import nombre_valido

        tipo = resto[0]
        nombre = resto[1]
        if tipo == "hacer":
            nombre = _opcion(resto, "--nombre") or nombre_valido(Path(nombre).stem)
            nombre = nombre_valido(nombre)
        if nombre != nombre_valido(nombre):
            return None
        return nombre, tipo
    if modulo == "manim":
        videos = (raiz / "videos").resolve()
        for argumento in resto:
            valor = argumento.split("=", 1)[-1] if argumento.startswith("--") else argumento
            try:
                ruta = Path(valor)
                if not ruta.is_absolute():
                    ruta = Path(cwd or raiz) / ruta
                relativa = ruta.resolve().relative_to(videos)
                if len(relativa.parts) >= 2 and relativa.parts[1] == "media":
                    return relativa.parts[0], "render"
            except (ValueError, OSError):
                continue
    return None


def _es_python(nombre: str | None) -> bool:
    """Solo un intérprete lleva «-m videocodigo» o «-m manim»; py.exe es el lanzador de Windows."""
    nombre = (nombre or "").lower()
    return nombre.startswith("python") or nombre in {"py.exe", "pyw.exe"}


def externos(raiz: Path, propios: set[int]) -> list[dict]:
    candidatos: list[dict] = []
    # Leer la orden y la carpeta de los ~400 procesos del equipo tardaba 10-30 s con un render en marcha,
    # y se hace con el cerrojo del gestor tomado: el nombre se lee al instante y filtra antes.
    for proceso in psutil.process_iter(["name"]):
        try:
            if proceso.pid in propios or proceso.pid == os.getpid() or not _es_python(proceso.info["name"]):
                continue
            datos = proceso.as_dict(["pid", "ppid", "cmdline", "create_time", "cwd", "exe"])
            argumentos = datos.get("cmdline") or []
            cwd = datos.get("cwd") or ""
            identificado = identificar(argumentos, raiz, cwd)
            if not identificado:
                continue
            # Una CLI de otro checkout no ocupa los proyectos de esta instalación.
            ejecutable = Path(datos.get("exe") or "")
            lanzador = Path(argumentos[0]) if argumentos else ejecutable
            indice = argumentos.index("-m")
            if argumentos[indice + 1] == "videocodigo_web.supervisor":
                # El entorno de la CLI anidada determina a qué checkout pertenece.
                ejecutable = lanzador = Path(argumentos[indice + 3])
            mismo_entorno = (ejecutable.is_relative_to(raiz / ".venv")
                             or lanzador.is_relative_to(raiz / ".venv"))
            if "videocodigo" in argumentos and not mismo_entorno and Path(cwd or ".").resolve() != raiz.resolve():
                continue
            ancestros = {padre.pid for padre in proceso.parents()}
            if ancestros & propios:
                continue
            nombre, tipo = identificado
            candidatos.append({"pid": datos["pid"], "proceso_creado": datos["create_time"],
                               "proyecto": nombre, "tipo": tipo, "ancestros": ancestros})
        except (psutil.Error, OSError, ValueError):
            continue
    pids = {c["pid"] for c in candidatos}
    return [{k: v for k, v in c.items() if k != "ancestros"}
            for c in candidatos if not (c["ancestros"] & pids)]


def detener_arbol(proceso: psutil.Process) -> None:
    """Congela al padre mientras captura descendientes, y espera su terminación."""
    descendientes: list[psutil.Process] = []
    try:
        proceso.suspend()
        descendientes = proceso.children(recursive=True)
        for hijo in descendientes:
            try:
                hijo.suspend()
            except psutil.Error:
                pass
        conocidos = {h.pid for h in descendientes}
        descendientes += [h for h in proceso.children(recursive=True) if h.pid not in conocidos]
    except psutil.NoSuchProcess:
        return
    except psutil.AccessDenied as error:
        raise PermissionError("No hay permisos para detener este proceso.") from error
    procesos = list(reversed(descendientes)) + [proceso]
    for actual in procesos:
        try:
            actual.terminate()
            if os.name != "nt":
                actual.resume()
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            try:
                actual.resume()
            except psutil.Error:
                pass
    _, pendientes = psutil.wait_procs(procesos, timeout=5)
    for actual in pendientes:
        try:
            actual.kill()
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            pass
    _, pendientes = psutil.wait_procs(pendientes, timeout=2)
    if pendientes:
        raise PermissionError("No se pudo detener todo el árbol de procesos; revisa sus permisos.")
