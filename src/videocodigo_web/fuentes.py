"""Inspección acotada y preparación de fuentes sin recorrer dependencias."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException
from videocodigo import config, ingesta

from .archivos import archivo_seguro, es_enlace, relativa_segura

MAX_TOTAL = 20_000_000
MAX_ENTRADAS = 20_000


def admitido(ruta: Path) -> bool:
    return bool(ingesta.lenguaje_de(ruta) or ruta.suffix.lower() in ingesta.EXT_DOCUMENTO)


def lineas_de(ruta: Path) -> int:
    datos = ruta.read_bytes()
    return datos.count(b"\n") + (1 if datos and not datos.endswith(b"\n") else 0)


def descripcion(ruta: Path, relativa: Path) -> dict:
    return {"ruta": relativa.as_posix(), "bytes": ruta.stat().st_size,
            "lenguaje": ingesta.lenguaje_de(ruta) or "markdown", "lineas": lineas_de(ruta)}


def ruta_local(texto: str) -> Path:
    if not isinstance(texto, str) or not texto.strip() or len(texto) > 2000:
        raise HTTPException(400, "Escribe una ruta local válida.")
    ruta = Path(texto).expanduser().absolute()
    if str(ruta).startswith(("\\\\", "//")):
        raise HTTPException(400, "Usa una ruta de este equipo, no una carpeta de red.")
    if any(es_enlace(p) for p in (ruta, *ruta.parents)):
        raise HTTPException(400, "No se permiten enlaces simbólicos ni uniones de carpetas.")
    raiz_app = Path(config.RAIZ).absolute()
    partes = ruta.relative_to(raiz_app).parts if ruta.is_relative_to(raiz_app) else ruta.parts
    if any(p.startswith(".") for p in partes if p not in {".", ".."}):
        raise HTTPException(400, "No se pueden importar archivos o carpetas ocultos.")
    ruta = ruta.resolve()
    if ruta == Path(ruta.anchor) or ruta == Path.home().resolve():
        raise HTTPException(400, "Elige una carpeta de proyecto, no el disco ni tu carpeta personal.")
    return ruta


def inspeccionar(texto: str) -> dict:
    raiz = ruta_local(texto)
    if not raiz.exists():
        return {"existe": False, "tipo": None, "archivos": [], "total": 0, "bytes": 0, "ignorados": []}
    elegidos: list[dict] = []
    ignorados: list[dict] = []
    total = 0
    entradas = 0

    def agregar(archivo: Path, relativa: Path) -> None:
        nonlocal total
        relativa_segura(relativa.as_posix())
        if not admitido(archivo):
            ignorados.append({"ruta": relativa.as_posix(), "motivo": "Extensión no admitida"})
            return
        tamanio = archivo.stat().st_size
        if tamanio > ingesta.MAX_BYTES:
            raise HTTPException(400, f"{relativa.as_posix()}: el archivo pesa más de 400 KB.")
        total += tamanio
        if len(elegidos) >= ingesta.MAX_ARCHIVOS or total > MAX_TOTAL:
            raise HTTPException(400, "La fuente supera 400 archivos o 20 MB en total.")
        elegidos.append(descripcion(archivo, relativa))

    if raiz.is_file():
        agregar(raiz, Path(raiz.name))
        if not elegidos:
            raise HTTPException(400, "El tipo de archivo no está admitido.")
    elif raiz.is_dir():
        pendientes = [raiz]
        while pendientes:
            carpeta = pendientes.pop()
            try:
                with os.scandir(carpeta) as elementos:
                    for elemento in elementos:
                        entradas += 1
                        if entradas > MAX_ENTRADAS:
                            raise HTTPException(400, "La carpeta supera 20 000 entradas; elige una carpeta más concreta.")
                        archivo = Path(elemento.path)
                        relativa = archivo.relative_to(raiz)
                        if elemento.name.startswith(".") or elemento.name in ingesta.IGNORAR or es_enlace(archivo):
                            ignorados.append({"ruta": relativa.as_posix(), "motivo": "Carpeta ignorada, archivo oculto o enlace"})
                        elif elemento.is_dir(follow_symlinks=False):
                            pendientes.append(archivo)
                        elif elemento.is_file(follow_symlinks=False):
                            agregar(archivo, relativa)
            except PermissionError as exc:
                raise HTTPException(400, "No hay permiso para leer una carpeta de la fuente.") from exc
        if not elegidos:
            raise HTTPException(400, "La carpeta no contiene archivos admitidos.")
    else:
        raise HTTPException(400, "La fuente debe ser un archivo o una carpeta.")
    elegidos.sort(key=lambda d: d["ruta"])
    return {"existe": True, "tipo": ingesta.tipo_fuente(raiz), "archivos": elegidos,
            "total": len(elegidos), "bytes": total, "lineas": sum(a["lineas"] for a in elegidos),
            "ignorados": ignorados}


def copiar_local(texto: str, temporal: Path) -> Path:
    inventario = inspeccionar(texto)
    if not inventario["existe"]:
        raise HTTPException(404, "La fuente no existe.")
    original = ruta_local(texto)
    destino = archivo_seguro(temporal, original.name)
    base = original if original.is_dir() else original.parent
    for item in inventario["archivos"]:
        origen = archivo_seguro(base, item["ruta"])
        copia = archivo_seguro(destino, item["ruta"]) if original.is_dir() else destino
        copia.parent.mkdir(parents=True, exist_ok=True)
        with origen.open("rb") as flujo:
            contenido = flujo.read(ingesta.MAX_BYTES + 1)
        if len(contenido) != item["bytes"]:
            raise HTTPException(409, "La fuente cambió mientras se copiaba; revísala otra vez.")
        copia.write_bytes(contenido)
    return destino
