"""El guion: contrato en JSON entre quien decide el video (un modelo, Claude o una persona) y el motor.

Un guion tiene `fragmentos` (trozos de código, con traza opcional) y `escenas` en orden.
`validar()` devuelve errores en español, pensados para devolvérselos al modelo y que corrija.
"""

from __future__ import annotations

import json
from pathlib import Path

from .estilo import MAX_LINEAS, NOMBRES_ICONOS

MAX_TEXTO = 900
MAX_ESCENAS = 60

# Escenas y los campos que exige cada una
ESCENAS = {
    "portada": ["titulo"],
    "idea": ["bloques"],
    "lista": ["items"],
    "archivos": ["rutas", "bloques"],
    "diagrama": ["cajas", "bloques"],
    "grafo": ["nodos", "aristas", "bloques"],
    "arreglo": ["valores", "bloques"],
    "arbol": ["raiz", "bloques"],
    "pila": ["bloques"],
    "codigo": ["fragmento", "lineas"],
    "grafo_traza": ["fragmento", "argumento"],
    "arreglo_traza": ["fragmento", "variable"],
    "lista_traza": ["fragmento", "variable"],
    "terminal": ["comandos"],
    "tabla": ["encabezados", "filas", "bloques"],
    "capas": ["capas", "bloques"],
    "piezas": ["items", "bloques"],
    "cierre": ["bloques"],
}

ACCIONES = {
    "grafo": {"cerrar": ["nodo"], "marcar": ["nodo"], "abrir": ["nodo"], "valor": ["nodo", "valor"],
              "camino": ["nodos"], "resaltar_arista": ["de", "a"], "pulso": ["de", "a"], "peso": ["de", "a", "valor"]},
    "arreglo": {"intercambiar": ["i", "j"], "poner": ["i", "valor"], "resaltar": ["indices"], "comparar": ["i", "j"],
                "puntero": ["nombre", "i"], "normal": [], "listo": ["indices"]},
    "arbol": {"resaltar": ["nodo"], "camino": ["nodos"], "normal": []},
    "pila": {"meter": ["valor"], "sacar": [], "tachar": ["indice"], "resaltar": ["indice"]},
}


def cargar(ruta: str | Path) -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def guardar(guion: dict, ruta: str | Path) -> None:
    Path(ruta).write_text(json.dumps(guion, ensure_ascii=False, indent=2), encoding="utf-8")


def textos(guion: dict) -> list[str]:
    """Todo lo que se va a narrar, en orden (sirve para estimar el costo de la voz)."""
    salida = []
    for esc in guion.get("escenas", []):
        salida += [t for t in esc.get("narracion", []) if t]
        for clave in ("intro", "cierre", "resultado", "reto"):
            if isinstance(esc.get(clave), str) and esc[clave].strip():
                salida.append(esc[clave])
        for lista in ("bloques", "items", "lineas"):
            for b in esc.get(lista, []) or []:
                texto = b if isinstance(b, str) else b.get("texto")
                if texto:
                    salida.append(texto)
        for cmd in esc.get("comandos", []) or []:
            salida += [t for t in (cmd.get("texto"), cmd.get("texto_salida")) if t]
            salida += [p["texto"] for p in cmd.get("partes", []) or [] if p.get("texto")]
    return salida


def validar(guion: dict, base: str | Path) -> list[str]:
    """Revisa estructura y referencias. Lista vacía = guion válido."""
    base = Path(base)
    errores: list[str] = []
    if not isinstance(guion, dict):
        return ["El guion debe ser un objeto JSON."]
    fragmentos = guion.get("fragmentos") or {}
    if not isinstance(fragmentos, dict):
        errores.append("'fragmentos' debe ser un objeto {id: {...}}.")
        fragmentos = {}
    lineas_por_fragmento = {}
    for fid, frag in fragmentos.items():
        archivo = base / str(frag.get("archivo", ""))
        if not archivo.is_file():
            errores.append(f"Fragmento {fid}: no existe el archivo {frag.get('archivo')!r}.")
            continue
        total = len(archivo.read_text(encoding="utf-8").splitlines())
        desde, hasta = int(frag.get("desde", 1)), int(frag.get("hasta", total))
        if not 1 <= desde <= hasta <= total:
            errores.append(f"Fragmento {fid}: líneas {desde}-{hasta} fuera del archivo (tiene {total}).")
        elif hasta - desde + 1 > MAX_LINEAS:
            errores.append(f"Fragmento {fid}: {hasta - desde + 1} líneas; el máximo por pantalla es {MAX_LINEAS}.")
        lineas_por_fragmento[fid] = (desde, hasta)
        if frag.get("traza") and not (base / frag["traza"]).is_file():
            errores.append(f"Fragmento {fid}: no existe la traza {frag['traza']!r}.")

    escenas = guion.get("escenas")
    if not isinstance(escenas, list) or not escenas:
        return errores + ["'escenas' debe ser una lista con al menos una escena."]
    if len(escenas) > MAX_ESCENAS:
        errores.append(f"Hay {len(escenas)} escenas; el máximo es {MAX_ESCENAS}.")
    for n, esc in enumerate(escenas, 1):
        donde = f"Escena {n}"
        tipo = esc.get("tipo") if isinstance(esc, dict) else None
        if tipo not in ESCENAS:
            errores.append(f"{donde}: tipo {tipo!r} desconocido. Usa uno de: {', '.join(ESCENAS)}.")
            continue
        donde += f" ({tipo})"
        for campo in ESCENAS[tipo]:
            if esc.get(campo) in (None, "", [], {}):
                errores.append(f"{donde}: falta el campo '{campo}'.")
        for texto in _textos_escena(esc):
            if len(texto) > MAX_TEXTO:
                errores.append(f"{donde}: una narración tiene {len(texto)} caracteres; pártela (máx. {MAX_TEXTO}).")
        if "fragmento" in esc:
            fid = esc["fragmento"]
            if fid not in fragmentos:
                errores.append(f"{donde}: el fragmento {fid!r} no está en 'fragmentos'.")
            elif tipo.endswith("_traza") and not fragmentos[fid].get("traza"):
                errores.append(f"{donde}: el fragmento {fid!r} no tiene traza; usa una escena sin traza.")
            elif tipo == "codigo" and fid in lineas_por_fragmento:
                desde, hasta = lineas_por_fragmento[fid]
                for item in esc.get("lineas", []):
                    a, b = int(item.get("desde", 0)), int(item.get("hasta", item.get("desde", 0)))
                    if not desde <= a <= b <= hasta:
                        errores.append(f"{donde}: líneas {a}-{b} fuera del fragmento ({desde}-{hasta}).")
                    if not item.get("texto"):
                        errores.append(f"{donde}: las líneas {a}-{b} no tienen texto.")
        errores += _validar_acciones(esc, tipo, donde)
        errores += _validar_visual(esc, tipo, donde)
        if tipo == "terminal":
            errores += _validar_terminal(esc, donde)
        if tipo == "tabla":
            errores += _validar_tabla(esc, donde)
    return errores


def _icono(nombre, donde: str, errores: list[str]) -> None:
    if nombre and nombre not in NOMBRES_ICONOS:
        errores.append(f"{donde}: el ícono {nombre!r} no existe. Usa uno de: {', '.join(NOMBRES_ICONOS)}.")


def _en_rango(valor, total: int, donde: str, campo: str, errores: list[str]) -> None:
    for i in valor if isinstance(valor, list) else ([] if valor in (None, "") else [valor]):
        if not isinstance(i, int) or not 0 <= i < total:
            errores.append(f"{donde}: '{campo}' = {i!r} fuera de rango (0-{total - 1}).")


def _validar_visual(esc: dict, tipo: str, donde: str) -> list[str]:
    """Íconos que existan, flechas y flujos entre cajas reales, índices de capas y piezas en rango."""
    errores: list[str] = []
    _icono(esc.get("icono"), donde, errores)
    bloques = [b for b in esc.get("bloques", []) or [] if isinstance(b, dict)]
    for k, b in enumerate(bloques, 1):
        _icono(b.get("icono"), f"{donde}, bloque {k}", errores)
        _icono(b.get("viajero"), f"{donde}, bloque {k}", errores)
    if tipo == "diagrama":
        cajas = esc.get("cajas") or {}
        for clave, caja in cajas.items():
            if isinstance(caja, dict):
                _icono(caja.get("icono"), f"{donde}, caja {clave}", errores)
                if not caja.get("titulo"):
                    errores.append(f"{donde}: la caja {clave!r} no tiene 'titulo'.")
        pares = set()
        for f in esc.get("flechas", []) or []:
            if not isinstance(f, list) or len(f) < 2 or f[0] not in cajas or f[1] not in cajas:
                errores.append(f"{donde}: la flecha {f!r} une cajas que no existen.")
            else:
                pares.add((f[0], f[1]))
        for k, b in enumerate(bloques, 1):
            if b.get("resaltar") and b["resaltar"] not in cajas:
                errores.append(f"{donde}, bloque {k}: no hay caja {b['resaltar']!r} para resaltar.")
            flujo = b.get("flujo")
            if flujo and not (isinstance(flujo, list) and len(flujo) == 2
                              and ((flujo[0], flujo[1]) in pares or (flujo[1], flujo[0]) in pares)):
                errores.append(f"{donde}, bloque {k}: el flujo {flujo!r} debe seguir una flecha que exista.")
    elif tipo == "capas":
        capas = esc.get("capas") or []
        for k, capa in enumerate(capas, 1):
            if not isinstance(capa, dict) or not capa.get("titulo"):
                errores.append(f"{donde}: la capa {k} necesita 'titulo'.")
            else:
                _icono(capa.get("icono"), f"{donde}, capa {k}", errores)
        for k, b in enumerate(bloques, 1):
            _en_rango(b.get("mostrar"), len(capas), f"{donde}, bloque {k}", "mostrar", errores)
            _en_rango(b.get("resaltar"), len(capas), f"{donde}, bloque {k}", "resaltar", errores)
    elif tipo == "piezas":
        items = esc.get("items") or []
        for k, item in enumerate(items, 1):
            if not isinstance(item, dict) or not item.get("titulo"):
                errores.append(f"{donde}: la pieza {k} necesita 'titulo'.")
            else:
                _icono(item.get("icono"), f"{donde}, pieza {k}", errores)
        if isinstance(esc.get("destino"), dict):
            _icono(esc["destino"].get("icono"), f"{donde}, destino", errores)
        for k, b in enumerate(bloques, 1):
            _en_rango(b.get("mostrar"), len(items), f"{donde}, bloque {k}", "mostrar", errores)
            if b.get("instalar") and not esc.get("destino"):
                errores.append(f"{donde}, bloque {k}: 'instalar' necesita un 'destino' en la escena.")
    elif tipo == "lista":
        if esc.get("estilo") not in (None, "puntos", "check"):
            errores.append(f"{donde}: 'estilo' debe ser 'puntos' o 'check'.")
        for k, item in enumerate(esc.get("items", []) or [], 1):
            if not isinstance(item, dict) or not item.get("texto"):
                errores.append(f"{donde}: el ítem {k} necesita 'texto'.")
    elif tipo == "cierre" and esc.get("resumen") is not None:
        if not isinstance(esc["resumen"], list) or not all(isinstance(r, str) for r in esc["resumen"]):
            errores.append(f"{donde}: 'resumen' debe ser una lista de textos cortos.")
    return errores


def _validar_terminal(esc: dict, donde: str) -> list[str]:
    errores = []
    for k, cmd in enumerate(esc.get("comandos", []) or [], 1):
        if not isinstance(cmd, dict) or not str(cmd.get("comando", "")).strip():
            errores.append(f"{donde}, comando {k}: falta 'comando'.")
            continue
        if not cmd.get("texto"):
            errores.append(f"{donde}, comando {k}: falta 'texto' (la narración del comando).")
        for parte in cmd.get("partes", []) or []:
            fragmento = parte.get("fragmento", "")
            if not fragmento or fragmento not in cmd["comando"]:
                errores.append(f"{donde}, comando {k}: el fragmento {fragmento!r} no aparece literal en el comando.")
            if not parte.get("texto"):
                errores.append(f"{donde}, comando {k}: la parte {fragmento!r} no tiene 'texto'.")
        salida = cmd.get("salida") or []
        if not isinstance(salida, list) or not all(isinstance(s, str) for s in salida):
            errores.append(f"{donde}, comando {k}: 'salida' debe ser una lista de líneas de texto.")
        elif len(salida) > 12:
            errores.append(f"{donde}, comando {k}: la salida tiene {len(salida)} líneas; deja 12 o menos.")
    return errores


def _validar_tabla(esc: dict, donde: str) -> list[str]:
    encabezados, filas = esc.get("encabezados") or [], esc.get("filas") or []
    errores = []
    if not all(isinstance(f, list) for f in filas):
        return [f"{donde}: 'filas' debe ser una lista de listas."]
    for k, fila in enumerate(filas, 1):
        if len(fila) > len(encabezados):
            errores.append(f"{donde}: la fila {k} tiene más columnas que encabezados.")
    for k, bloque in enumerate(esc.get("bloques", []) or [], 1):
        if not isinstance(bloque, dict) or not bloque.get("texto"):
            errores.append(f"{donde}, bloque {k}: cada bloque necesita 'texto'.")
            continue
        resaltar = bloque.get("resaltar")
        indices = resaltar if isinstance(resaltar, list) else ([] if resaltar is None else [resaltar])
        for i in indices:
            if not isinstance(i, int) or not 0 <= i < len(filas):
                errores.append(f"{donde}, bloque {k}: fila a resaltar {i!r} fuera de rango (0-{len(filas) - 1}).")
    return errores


def _textos_escena(esc: dict) -> list[str]:
    return textos({"escenas": [esc]})


def _validar_acciones(esc: dict, tipo: str, donde: str) -> list[str]:
    familia = {"grafo": "grafo", "arreglo": "arreglo", "arbol": "arbol", "pila": "pila"}.get(tipo)
    if not familia:
        return []
    errores = []
    nodos = set(map(str, esc.get("nodos", []))) if tipo == "grafo" else None
    largo = len(esc.get("valores", [])) if tipo == "arreglo" else None
    for k, bloque in enumerate(esc.get("bloques", []), 1):
        if not isinstance(bloque, dict) or not bloque.get("texto"):
            errores.append(f"{donde}, bloque {k}: cada bloque necesita 'texto'.")
            continue
        for accion in bloque.get("acciones", []) or []:
            nombre = accion.get("accion")
            if nombre not in ACCIONES[familia]:
                errores.append(f"{donde}, bloque {k}: acción {nombre!r} no existe. Usa: {', '.join(ACCIONES[familia])}.")
                continue
            for campo in ACCIONES[familia][nombre]:
                if campo not in accion:
                    errores.append(f"{donde}, bloque {k}: la acción {nombre} necesita '{campo}'.")
            if nodos is not None:
                usados = [accion.get(c) for c in ("nodo", "de", "a") if accion.get(c) is not None] + list(accion.get("nodos", []))
                for u in usados:
                    if str(u) not in nodos:
                        errores.append(f"{donde}, bloque {k}: el nodo {u!r} no está en 'nodos'.")
            if largo is not None:
                for c in ("i", "j"):
                    if c in accion and not (isinstance(accion[c], int) and 0 <= accion[c] < largo):
                        errores.append(f"{donde}, bloque {k}: índice {c}={accion[c]!r} fuera del arreglo (0-{largo - 1}).")
    return errores
