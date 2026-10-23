"""Prioridad real de un trabajo y sus procesos descendientes en Windows."""

from __future__ import annotations

import os

import psutil


def leer_prioridad(proceso: psutil.Process) -> bool | None:
    """Devuelve baja/alta solo cuando todo el árbol usa una clase conocida."""
    if os.name != "nt":
        return None
    try:
        clase = proceso.nice()
        if clase not in {psutil.BELOW_NORMAL_PRIORITY_CLASS, psutil.HIGH_PRIORITY_CLASS}:
            return None
        for hijo in proceso.children(recursive=True):
            try:
                if hijo.nice() != clase:
                    return None
            except psutil.NoSuchProcess:
                continue
        return clase == psutil.BELOW_NORMAL_PRIORITY_CLASS
    except (psutil.Error, OSError):
        return None


def aplicar_prioridad(proceso: psutil.Process, prioridad_baja: bool) -> None:
    """Cambia el árbol sin reiniciarlo; revierte si falta algún permiso."""
    if os.name != "nt":
        raise NotImplementedError("El cambio de prioridad está disponible en Windows.")
    clase = psutil.BELOW_NORMAL_PRIORITY_CLASS if prioridad_baja else psutil.HIGH_PRIORITY_CLASS
    anteriores: list[tuple[psutil.Process, int]] = []
    cambiados: list[tuple[psutil.Process, int]] = []
    try:
        # Leer todas las clases antes de modificar evita cambios si ya falta acceso.
        anteriores.append((proceso, proceso.nice()))
        for hijo in proceso.children(recursive=True):
            try:
                anteriores.append((hijo, hijo.nice()))
            except psutil.NoSuchProcess:
                continue
        for actual, anterior in anteriores:
            if anterior == clase:
                continue
            try:
                actual.nice(clase)
                cambiados.append((actual, anterior))
            except psutil.NoSuchProcess:
                if actual is proceso:
                    raise
        if not proceso.is_running():
            raise psutil.NoSuchProcess(proceso.pid)
    except (psutil.Error, OSError) as error:
        restaurado = True
        for actual, anterior in reversed(cambiados):
            try:
                actual.nice(anterior)
            except psutil.NoSuchProcess:
                continue
            except (psutil.Error, OSError):
                restaurado = False
        if isinstance(error, psutil.NoSuchProcess):
            raise
        detalle = "No hay permisos para cambiar la prioridad de todo el trabajo."
        if not restaurado:
            detalle += " No se pudo restaurar la prioridad de todos los procesos; revisa su estado."
        raise PermissionError(detalle) from error


def mantener_prioridad(proceso: psutil.Process) -> None:
    """Propaga a hijos nuevos la clase actual, sin reescribir nunca la raíz."""
    if os.name != "nt":
        return
    clase = proceso.nice()
    if clase not in {psutil.BELOW_NORMAL_PRIORITY_CLASS, psutil.HIGH_PRIORITY_CLASS}:
        return
    for hijo in proceso.children(recursive=True):
        # Una petición de la API puede cambiar la raíz mientras recorremos el árbol.
        if proceso.nice() != clase:
            return
        try:
            if hijo.nice() != clase:
                hijo.nice(clase)
        except psutil.NoSuchProcess:
            continue
