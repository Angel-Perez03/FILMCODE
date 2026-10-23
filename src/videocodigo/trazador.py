"""Ejecuta una llamada de Python y registra, línea por línea, el valor de las variables.

Se corre en un proceso aparte (`python -m videocodigo.trazador ...`) para que el código del
usuario no comparta memoria con el backend y se pueda cortar por tiempo.

Si el archivo es un espejo en Python de código en otro lenguaje, cada línea puede terminar en
`#@N` para indicar a qué línea del original corresponde.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import re
import runpy
import sys
from collections import deque
from pathlib import Path

LIMITE_ITEMS = 40
MARCA_LINEA = re.compile(r"#@(\d+)\s*$")


class _Limite(Exception):
    pass


def a_json(valor, profundidad: int = 0):
    """Copia un valor de Python a algo que JSON entiende (∞ como texto, tuplas como listas)."""
    if valor is None or isinstance(valor, (bool, int)):
        return valor
    if isinstance(valor, float):
        if math.isinf(valor):
            return "∞" if valor > 0 else "-∞"
        return "NaN" if math.isnan(valor) else valor
    if isinstance(valor, str):
        return valor if len(valor) <= 200 else valor[:199] + "…"
    if profundidad >= 4:
        return _corto(valor)
    if isinstance(valor, (list, tuple, deque)):
        items = [a_json(v, profundidad + 1) for v in list(valor)[:LIMITE_ITEMS]]
        return items + (["…"] if len(valor) > LIMITE_ITEMS else [])
    if isinstance(valor, dict):
        return {str(k): a_json(v, profundidad + 1) for k, v in list(valor.items())[:LIMITE_ITEMS]}
    if isinstance(valor, (set, frozenset)):
        try:
            return [a_json(v, profundidad + 1) for v in sorted(valor)[:LIMITE_ITEMS]]
        except TypeError:
            return [a_json(v, profundidad + 1) for v in list(valor)[:LIMITE_ITEMS]]
    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        return {"__tipo__": type(valor).__name__,
                **{f.name: a_json(getattr(valor, f.name), profundidad + 1) for f in dataclasses.fields(valor)}}
    if hasattr(valor, "__dict__") and not callable(valor):
        atributos = {k: a_json(v, profundidad + 1) for k, v in vars(valor).items() if not k.startswith("_")}
        return {"__tipo__": type(valor).__name__, **atributos}
    return _corto(valor)


def _corto(valor) -> str:
    texto = repr(valor)
    return texto if len(texto) <= 120 else texto[:119] + "…"


def _variables(local: dict) -> dict:
    salida = {}
    for nombre, valor in local.items():
        if nombre.startswith("__") or callable(valor) or isinstance(valor, type(sys)):
            continue
        salida[nombre] = a_json(valor)
    return salida


def trazar(archivo: str | Path, llamada: str, funciones: list[str] | None = None, max_pasos: int = 4000) -> dict:
    ruta = Path(archivo).resolve()
    fuente = ruta.read_text(encoding="utf-8")
    mapa = {i + 1: int(m.group(1)) for i, linea in enumerate(fuente.splitlines()) if (m := MARCA_LINEA.search(linea))}
    objetivo = os.path.normcase(str(ruta))
    sys.path.insert(0, str(ruta.parent))
    espacio = runpy.run_path(str(ruta), run_name="__traza__")

    pasos: list[dict] = []
    marcos: dict[int, int] = {}
    pila: list[int] = []
    contador = [0]

    def registrar(frame, evento: str, extra: dict | None = None) -> None:
        if len(pasos) >= max_pasos:
            raise _Limite()
        paso = {"paso": len(pasos), "evento": evento, "linea": frame.f_lineno, "funcion": frame.f_code.co_name,
                "marco": marcos.get(id(frame), -1), "profundidad": len(pila), "vars": _variables(frame.f_locals)}
        if mapa:
            paso["linea_original"] = mapa.get(frame.f_lineno)
        if extra:
            paso.update(extra)
        pasos.append(paso)

    def local(frame, evento, arg):
        if evento == "line":
            registrar(frame, "linea")
        elif evento == "return":
            registrar(frame, "retorno", {"valor": a_json(arg)})
            if pila:
                pila.pop()
        elif evento == "exception":
            registrar(frame, "excepcion", {"error": f"{arg[0].__name__}: {arg[1]}"})
        return local

    def global_(frame, evento, arg):
        if evento != "call" or os.path.normcase(frame.f_code.co_filename) != objetivo:
            return None
        if funciones and frame.f_code.co_name not in funciones:
            return None
        contador[0] += 1
        marcos[id(frame)] = contador[0]
        pila.append(contador[0])
        return local

    resultado, error, truncado = None, None, False
    codigo = compile(llamada, "<llamada>", "eval")
    sys.settrace(global_)
    try:
        resultado = a_json(eval(codigo, espacio))
    except _Limite:
        truncado = True
    except Exception as ex:  # el error del código del usuario es parte del resultado
        error = f"{type(ex).__name__}: {ex}"
    finally:
        sys.settrace(None)

    _agregar_cambios(pasos)
    visitas: dict[str, int] = {}
    for p in pasos:
        if p["evento"] == "linea":
            visitas[str(p["linea"])] = visitas.get(str(p["linea"]), 0) + 1
    return {"archivo": str(ruta), "llamada": llamada, "funciones": funciones or [], "codigo": fuente.splitlines(),
            "pasos": pasos, "resultado": resultado, "error": error, "truncado": truncado,
            "visitas_por_linea": visitas}


def _agregar_cambios(pasos: list[dict]) -> None:
    """A cada línea le agrega `cambios`: lo que quedó distinto después de ejecutarla."""
    siguiente: dict[int, dict] = {}
    for paso in reversed(pasos):
        despues = siguiente.get(paso["marco"])
        if paso["evento"] == "linea":
            nuevas = despues["vars"] if despues else paso["vars"]
            paso["cambios"] = {k: v for k, v in nuevas.items() if paso["vars"].get(k, object()) != v}
        siguiente[paso["marco"]] = paso


def main() -> None:
    parser = argparse.ArgumentParser(description="Traza una llamada de Python línea por línea.")
    parser.add_argument("archivo")
    parser.add_argument("llamada", help='Expresión a evaluar en el módulo, p. ej. "dijkstra(GRAFO, 0)"')
    parser.add_argument("--funciones", default="", help="Solo estas funciones (separadas por coma)")
    parser.add_argument("--max-pasos", type=int, default=4000)
    parser.add_argument("--salida", required=True, help="Archivo JSON de salida")
    args = parser.parse_args()
    funciones = [f.strip() for f in args.funciones.split(",") if f.strip()] or None
    traza = trazar(args.archivo, args.llamada, funciones, args.max_pasos)
    Path(args.salida).write_text(json.dumps(traza, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
