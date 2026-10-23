"""Síntesis breve solicitada explícitamente desde Ajustes."""

import json
import sys
from dataclasses import replace
from pathlib import Path

from videocodigo import config, voz


def main():
    proveedor, elegida, texto = sys.argv[1:]
    if proveedor not in {"edge", "voicestudio"} or not 0 < len(texto) <= 200:
        return 1
    ajustes = config.ajustes_voz(proveedor)
    ajustes = replace(ajustes, **{"edge_voz" if proveedor == "edge" else "voicestudio_voz": elegida})
    cache = config.RAIZ / ".web" / "pruebas_voz"
    try:
        segmento = voz.crear_voz(proveedor, cache, ajustes).sintetizar(texto)
        print(json.dumps({"archivo": Path(segmento.audio).name}))
        return 0
    except Exception:
        print("No se pudo generar la prueba de voz.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
