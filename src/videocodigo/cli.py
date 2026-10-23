"""Línea de comandos: capa delgada sobre proyecto.py. Imprime JSON en stdout y el progreso en stderr.

    python -m videocodigo hacer RUTA            # guion + video a 720p y 30 FPS
    python -m videocodigo render NOMBRE --calidad 1080p60
"""

from __future__ import annotations

import argparse
import json
import sys

from . import proyecto
from .config import PROVEEDORES_VOZ, ajustes_llm
from .duracion import validar_minutos


def _progreso(mensaje: str, fraccion: float) -> None:
    marca = f"{fraccion * 100:5.1f}%" if fraccion >= 0 else "   ·  "
    print(f"[{marca}] {mensaje}", file=sys.stderr, flush=True)


def _imprimir(datos) -> None:
    print(json.dumps(datos, ensure_ascii=False, indent=2))


def _resumen_estado(datos: dict) -> str:
    """Las dos o tres líneas que una persona quiere ver de un proyecto (el JSON sigue en stdout)."""
    estado, nombre = datos["estado"], datos["manifiesto"]["nombre"]
    progreso = estado.get("progreso")
    lineas = [f"Proyecto {nombre}: {estado.get('etapa')}"
              + (f" ({progreso} %)" if isinstance(progreso, (int, float)) and estado.get("etapa") != "error" else "")
              + f" — {estado.get('mensaje', '')}"]
    salidas = estado.get("salidas") or {}
    if salidas:
        for calidad, info in salidas.items():
            lineas.append(f"Video {calidad}: {info.get('ruta')} ({info.get('duracion')} s). Ábrelo con: start \"{info.get('ruta')}\"")
    else:
        lineas.append(f"Video: todavía no hay. Al terminar el render queda en videos\\{nombre}\\salida.")
    if estado.get("etapa") == "error":
        lineas.append(f"Para retomar: python -m videocodigo continuar {nombre}")
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="videocodigo", description="Videos que explican código, hechos por un modelo local.")
    sub = p.add_subparsers(dest="orden", required=True)

    h = sub.add_parser("hacer", help="Todo de una: crear, escribir el guion y renderizar")
    h.add_argument("fuente", help="Archivo o carpeta de código, o una guía en Markdown")
    h.add_argument("--nombre")
    h.add_argument("--modelo", help="p. ej. ollama:gemma4:12b (por defecto VIDEOCODIGO_MODELO)")
    h.add_argument("--calidad", default=proyecto.CALIDAD_PREDETERMINADA, choices=list(proyecto.CALIDADES))
    h.add_argument("--sin-capturas", action="store_true", help="No ejecutar comandos de verificación reales")
    h.add_argument("--voz", choices=list(PROVEEDORES_VOZ), help="Cambia la voz de la calidad: voicestudio (tu voz), edge o silencio")

    c = sub.add_parser("continuar", help="Retomar un proyecto: termina el guion si falta y renderiza")
    c.add_argument("proyecto")
    c.add_argument("--modelo")
    c.add_argument("--calidad", default=proyecto.CALIDAD_PREDETERMINADA, choices=list(proyecto.CALIDADES))
    c.add_argument("--sin-capturas", action="store_true")
    c.add_argument("--voz", choices=list(PROVEEDORES_VOZ), help="Cambia la voz de la calidad: voicestudio (tu voz), edge o silencio")

    n = sub.add_parser("nuevo", help="Crear el proyecto a partir de una fuente")
    n.add_argument("fuente")
    n.add_argument("--nombre")

    gu = sub.add_parser("guion", help="Escribir el guion con el modelo")
    gu.add_argument("proyecto")
    gu.add_argument("--modelo")
    gu.add_argument("--sin-capturas", action="store_true")
    for generador in (h, c, gu):
        generador.add_argument("--duracion-minutos", type=lambda valor: validar_minutos(float(valor)),
                               help="Duración aproximada del video final, de 1 a 120 minutos")

    r = sub.add_parser("render", help="Renderizar el video")
    r.add_argument("proyecto")
    r.add_argument("--calidad", default=proyecto.CALIDAD_PREDETERMINADA, choices=list(proyecto.CALIDADES))
    r.add_argument("--voz", choices=list(PROVEEDORES_VOZ), help="Cambia la voz de la calidad: voicestudio (tu voz), edge o silencio")
    for renderizador in (h, c, r):
        renderizador.add_argument("--velocidad-voz", type=float, help="Ritmo de la voz, de 0.75 a 1.5 (1 = normal)")
        renderizador.add_argument("--velocidad-animaciones", type=float,
                                  help="Rapidez de movimientos y transiciones, de 0.5 a 2 (1 = normal)")
        fluidez = renderizador.add_mutually_exclusive_group()
        fluidez.add_argument("--voz-fluida", dest="voz_fluida", action="store_true", default=None,
                             help="Reduce las pausas entre bloques de narración")
        fluidez.add_argument("--sin-voz-fluida", dest="voz_fluida", action="store_false")

    sub.add_parser("estado", help="Estado de un proyecto").add_argument("proyecto")
    f = sub.add_parser("fotogramas", help="Hojas de miniaturas para revisar el video")
    f.add_argument("proyecto")
    f.add_argument("--calidad", default=proyecto.CALIDAD_PREDETERMINADA, choices=list(proyecto.CALIDADES))
    f.add_argument("--cada", type=float, default=5.0)
    sub.add_parser("lista", help="Proyectos existentes")
    sub.add_parser("voces", help="Voces disponibles (VoiceStudio y edge)")
    m = sub.add_parser("modelo", help="¿Está listo el modelo local?")
    m.add_argument("--modelo")

    a = p.parse_args(argv)
    try:
        if a.orden == "hacer":
            _imprimir(proyecto.hacer_video(a.fuente, a.nombre, a.modelo, a.calidad, not a.sin_capturas, _progreso,
                                          a.voz, a.duracion_minutos, a.velocidad_voz, a.velocidad_animaciones, a.voz_fluida))
        elif a.orden == "continuar":
            _imprimir(proyecto.continuar(a.proyecto, a.modelo, a.calidad, not a.sin_capturas, _progreso,
                                        a.voz, a.duracion_minutos, a.velocidad_voz, a.velocidad_animaciones, a.voz_fluida))
        elif a.orden == "nuevo":
            _imprimir(proyecto.crear(a.fuente, a.nombre))
        elif a.orden == "guion":
            _imprimir(proyecto.generar_guion(a.proyecto, a.modelo, not a.sin_capturas, _progreso, a.duracion_minutos))
        elif a.orden == "render":
            _imprimir(proyecto.renderizar(a.proyecto, a.calidad, _progreso, a.voz,
                                         a.velocidad_voz, a.velocidad_animaciones, a.voz_fluida))
        elif a.orden == "estado":
            datos = proyecto.leer(a.proyecto)
            _imprimir(datos)
            print("\n" + _resumen_estado(datos), file=sys.stderr)
        elif a.orden == "fotogramas":
            _imprimir(proyecto.fotogramas(a.proyecto, a.calidad, a.cada))
        elif a.orden == "lista":
            _imprimir(proyecto.listar())
        elif a.orden == "voces":
            from .voz import VOCES_EDGE_ES, ErrorVoz, crear_voz

            try:
                locales = crear_voz("voicestudio").voces()
            except ErrorVoz as error:
                locales = {"error": str(error)}
            _imprimir({"voicestudio": locales, "edge": VOCES_EDGE_ES})
        elif a.orden == "modelo":
            from .llm import ClienteLLM

            listo, mensaje = ClienteLLM(ajustes_llm(a.modelo)).disponible()
            _imprimir({"listo": listo, "mensaje": mensaje})
    except proyecto.ErrorProyecto as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
