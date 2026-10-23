"""Archivo de entrada para Manim: `manim render escena_guion.py VideoGuion` renderiza el guion indicado
en VIDEOCODIGO_GUION_ENTRADA."""

from videocodigo import motor


class VideoGuion(motor.VideoGuion):
    """Manim solo encuentra escenas definidas en el archivo que renderiza; por eso esta subclase."""
