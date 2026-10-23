"""Empaqueta solo los archivos públicos del asistente de Windows, sin dependencias."""

from __future__ import annotations

import argparse
import io
import os
import zipfile
from pathlib import Path

ARCHIVOS = ("Instalar-FilmCode.cmd", "Instalar-FilmCode.ps1", "Operaciones-FilmCode.ps1", "README.md")
NOMBRE_ZIP = "instalador-windows.zip"


def _leer(carpeta: Path, nombre: str) -> bytes:
    archivo = carpeta / nombre
    actual = archivo
    while True:
        if actual.is_symlink() or actual.is_junction():
            raise ValueError("El instalador no admite enlaces ni uniones de carpetas.")
        if actual.parent == actual:
            break
        actual = actual.parent
    if not archivo.is_file() or archivo.stat().st_size > 250_000:
        raise ValueError(f"Falta un archivo válido del instalador: {nombre}.")
    datos = archivo.read_bytes()
    datos.decode("utf-8-sig")
    return datos


def verificar_paquete(carpeta: Path) -> None:
    archivo = carpeta / NOMBRE_ZIP
    if archivo.is_symlink() or archivo.is_junction():
        raise ValueError("El paquete del instalador no puede ser un enlace.")
    if archivo.stat().st_size > 1_000_000:
        raise ValueError("El paquete del instalador supera el tamaño previsto.")
    with zipfile.ZipFile(archivo) as paquete:
        if sorted(paquete.namelist()) != sorted(ARCHIVOS):
            raise ValueError("El ZIP del instalador contiene archivos no permitidos.")
        for entrada in paquete.infolist():
            if entrada.file_size > 250_000 or paquete.read(entrada) != _leer(carpeta, entrada.filename):
                raise ValueError("El paquete del instalador está desactualizado o fue alterado.")


def empaquetar(raiz: Path) -> Path:
    carpeta = raiz / "frontend/public/instalador"
    preparados = {nombre: _leer(carpeta, nombre) for nombre in ARCHIVOS}
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", compression=zipfile.ZIP_DEFLATED) as paquete:
        for nombre, datos in preparados.items():
            entrada = zipfile.ZipInfo(nombre, date_time=(2026, 1, 1, 0, 0, 0))
            entrada.compress_type = zipfile.ZIP_DEFLATED
            entrada.external_attr = 0o100644 << 16
            paquete.writestr(entrada, datos)
    destino = carpeta / NOMBRE_ZIP
    temporal = carpeta / (NOMBRE_ZIP + ".tmp")
    if destino.is_symlink() or destino.is_junction():
        raise ValueError("El destino no puede ser un enlace.")
    with temporal.open("xb") as archivo:
        archivo.write(memoria.getvalue())
    os.replace(temporal, destino)
    verificar_paquete(carpeta)
    return destino


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    raiz = Path(__file__).resolve().parents[2]
    archivo = empaquetar(raiz)
    print(f"Instalador público: {archivo.relative_to(raiz).as_posix()} ({archivo.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
