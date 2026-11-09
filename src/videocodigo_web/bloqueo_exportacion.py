"""Exclusión entre la publicación del video y la cancelación del trabajo."""

import os
from contextlib import contextmanager
from pathlib import Path

from .archivos import archivo_seguro


class ExportacionEnCurso(RuntimeError):
    pass


@contextmanager
def bloquear_exportacion(carpeta: Path):
    # Cerrar el archivo (también si termina el proceso) libera el bloqueo.
    with archivo_seguro(carpeta, "publicacion.lock").open("a+b") as archivo:
        try:
            if os.name == "nt":
                import msvcrt

                archivo.seek(0)
                msvcrt.locking(archivo.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(archivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ExportacionEnCurso("FilmCode está guardando el video. Espera a que termine ese paso.") from error
        yield
