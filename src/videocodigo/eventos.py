"""De la traza a eventos visuales: qué nodo se visita, qué celda cambia, qué entra a la pila.

Así la animación del concepto sale de la ejecución real y no de lo que el modelo crea que pasa.
"""

from __future__ import annotations

from . import estilo

# Utilidades sobre la traza


def lineas_ejecutadas(traza: dict) -> list[dict]:
    return [p for p in traza["pasos"] if p["evento"] == "linea"]


def despues(paso: dict) -> dict:
    """Variables justo después de ejecutar la línea del paso."""
    return {**paso["vars"], **paso.get("cambios", {})}


def estado_tras_linea(traza: dict, linea: int, desde_paso: int = 0) -> tuple[int, dict] | None:
    """Primer paso (a partir de `desde_paso`) que ejecuta `linea`, con las variables resultantes."""
    for p in traza["pasos"]:
        if p["paso"] >= desde_paso and p["evento"] == "linea" and p["linea"] == linea:
            return p["paso"], despues(p)
    return None


def estado_final(traza: dict) -> dict:
    marcos_raiz = [p for p in traza["pasos"] if p["evento"] == "retorno" and p["profundidad"] <= 1]
    if marcos_raiz:
        return marcos_raiz[-1]["vars"]
    return despues(traza["pasos"][-1]) if traza["pasos"] else {}


# Formato de valores para pantalla


def a_letra(valor):
    if isinstance(valor, bool) or not isinstance(valor, int):
        return valor
    return estilo.letra(valor)


def formatear(valor, como_nodo: bool = False, decimales: int = 2, ancho: int | None = None) -> str:
    """Texto corto para la tabla de estado.

    `como_nodo` pasa índices enteros a letras (0 → A). Con `ancho`, las listas cortas salen en
    columnas de ese ancho, alineadas con una fila de encabezado 'nodo A B C…'.
    """
    if isinstance(valor, list) and not valor:
        return "[]"
    if como_nodo:
        if isinstance(valor, int) and not isinstance(valor, bool):
            return estilo.letra(valor)
        if isinstance(valor, list):
            partes = []
            for v in valor:
                if isinstance(v, list) and v and isinstance(v[-1], int):
                    partes.append("(" + ",".join([estilo.valor_corto(x, decimales) for x in v[:-1]] + [estilo.letra(v[-1])]) + ")")
                elif v is None:
                    partes.append("-")
                else:
                    partes.append(estilo.valor_corto(a_letra(v), decimales))
            if all(len(p) <= 3 for p in partes):
                return "".join(p.ljust(ancho) for p in partes).rstrip() if ancho else " ".join(partes)
            return "[" + ", ".join(partes) + "]"
    if isinstance(valor, list) and valor and all(isinstance(v, (int, float, str)) or v is None for v in valor):
        partes = [estilo.valor_corto(v, decimales) if v is not None else "-" for v in valor]
        if all(len(p) <= 4 for p in partes):
            columna = ancho or max(len(p) for p in partes) + 1
            return "".join(p.ljust(columna) for p in partes).rstrip()
    return estilo.valor_corto(valor, decimales)


# Grafos


def grafo_desde_valor(valor, letras: bool = True) -> dict:
    """Interpreta un grafo guardado como dict o lista de adyacencia, o como matriz de pesos.

    Devuelve {"nodos": [...], "aristas": [(u, v, w)], "dirigido": bool, "clave_a_nodo": {...}}.
    """
    adyacencia: dict[str, list[tuple[str, object]]] = {}
    if isinstance(valor, dict):
        claves = list(valor.keys())
        for k, vecinos in valor.items():
            adyacencia[str(k)] = _vecinos(vecinos)
    elif isinstance(valor, list) and valor and all(isinstance(f, list) for f in valor):
        n = len(valor)
        es_matriz = all(len(f) == n and all(isinstance(x, (int, float, str)) or x is None for x in f) for f in valor)
        claves = [str(i) for i in range(n)]
        for i, fila in enumerate(valor):
            if es_matriz:
                adyacencia[str(i)] = [(str(j), w) for j, w in enumerate(fila)
                                      if w not in (0, None, "∞", False) and i != j]
            else:
                adyacencia[str(i)] = _vecinos(fila)
    else:
        raise ValueError("No reconozco el formato del grafo (se espera dict o lista de adyacencia, o matriz).")
    claves = [str(k) for k in claves]
    for vecinos in adyacencia.values():
        for v, _ in vecinos:
            if v not in claves:
                claves.append(v)
    numericas = all(k.lstrip("-").isdigit() for k in claves)
    clave_a_nodo = {k: (estilo.letra(int(k)) if letras and numericas else k) for k in claves}
    pares = {(u, v): w for u, vs in adyacencia.items() for v, w in vs}
    dirigido = any((v, u) not in pares or pares[(v, u)] != w for (u, v), w in pares.items())
    aristas, vistas = [], set()
    for (u, v), w in pares.items():
        if not dirigido and (v, u) in vistas:
            continue
        vistas.add((u, v))
        aristas.append((clave_a_nodo[u], clave_a_nodo[v], w))
    return {"nodos": [clave_a_nodo[k] for k in claves], "aristas": aristas, "dirigido": dirigido,
            "clave_a_nodo": clave_a_nodo}


def _vecinos(vecinos) -> list[tuple[str, object]]:
    if isinstance(vecinos, dict):
        return [(str(v), w) for v, w in vecinos.items()]
    salida = []
    for item in vecinos or []:
        if isinstance(item, list) and len(item) >= 2:
            salida.append((str(item[0]), item[1]))
        else:
            salida.append((str(item), None))
    return salida


def _nodo_de(valor, clave_a_nodo: dict) -> str | None:
    if valor is None:
        return None
    return clave_a_nodo.get(str(valor))


def _valores_por_nodo(valores, clave_a_nodo: dict) -> dict:
    if isinstance(valores, dict):
        return {clave_a_nodo[k]: v for k, v in valores.items() if k in clave_a_nodo}
    if isinstance(valores, list):
        return {clave_a_nodo[str(i)]: v for i, v in enumerate(valores) if str(i) in clave_a_nodo}
    return {}


def bloques_grafo(traza: dict, argumento: str, valores: str | None = None, actual: str | None = None,
                  max_bloques: int = 14) -> dict:
    """Agrupa la ejecución en bloques 'tomamos el nodo X y estos valores cambian'."""
    pasos = lineas_ejecutadas(traza)
    if not pasos or argumento not in pasos[0]["vars"]:
        raise ValueError(f"La variable del grafo {argumento!r} no aparece en la traza.")
    grafo = grafo_desde_valor(pasos[0]["vars"][argumento])
    c2n = grafo["clave_a_nodo"]
    bloques: list[dict] = [{"nodo": None, "cambios": [], "paso": pasos[0]["paso"]}]
    previos: dict = {}
    nodo_actual, visitados = None, set()
    for p in pasos:
        estado = despues(p)
        if actual and actual in estado:
            nuevo = _nodo_de(estado[actual], c2n)
            if nuevo and nuevo != nodo_actual:
                nodo_actual = nuevo
                bloques.append({"nodo": nuevo, "cambios": [], "paso": p["paso"], "repetido": nuevo in visitados})
                visitados.add(nuevo)
        if valores and valores in estado:
            actuales = _valores_por_nodo(estado[valores], c2n)
            for n, v in actuales.items():
                if n in previos and previos[n] != v:
                    bloques[-1]["cambios"].append({"nodo": n, "antes": previos[n], "despues": v})
            if not previos:
                bloques[0]["iniciales"] = actuales
            previos = actuales
    bloques = [b for b in bloques if b["nodo"] is None or not (b.get("repetido") and not b["cambios"])]
    if len(bloques) > max_bloques + 1:
        bloques = bloques[: max_bloques] + [bloques[-1]]
    return {"grafo": grafo, "bloques": bloques, "finales": previos}


def narrar_bloque_grafo(bloque: dict) -> str:
    """Narración de respaldo (sin modelo) para un bloque del grafo."""
    if bloque["nodo"] is None:
        return "Arrancamos: el origen vale cero y todo lo demás vale infinito por ahora."
    partes = [f"Tomamos el nodo {bloque['nodo']}."]
    for c in bloque["cambios"]:
        antes, nuevo = estilo.valor_corto(c["antes"]), estilo.valor_corto(c["despues"])
        if antes == estilo.INFINITO:
            partes.append(f"{c['nodo']} queda en {nuevo}.")
        else:
            partes.append(f"{c['nodo']} pasa de {antes} a {nuevo}.")
    if not bloque["cambios"]:
        partes.append("No mejora a ningún vecino.")
    return " ".join(partes)


# Arreglos y listas


def eventos_arreglo(traza: dict, variable: str, punteros: list[str] = (), max_eventos: int = 30) -> dict:
    """Cambios de un arreglo a lo largo de la ejecución: intercambios, asignaciones y punteros."""
    pasos = lineas_ejecutadas(traza)
    inicial = next((p["vars"][variable] for p in pasos if variable in p["vars"]), None)
    if not isinstance(inicial, list):
        raise ValueError(f"La variable {variable!r} no es una lista en la traza.")
    eventos, previo, posiciones = [], list(inicial), {}
    for p in pasos:
        estado = despues(p)
        for nombre in punteros:
            valor = estado.get(nombre)
            if isinstance(valor, int) and 0 <= valor < len(previo) and posiciones.get(nombre) != valor:
                posiciones[nombre] = valor
                eventos.append({"tipo": "puntero", "nombre": nombre, "i": valor, "paso": p["paso"]})
        actual = estado.get(variable)
        if not isinstance(actual, list) or actual == previo:
            continue
        if len(actual) != len(previo):
            eventos.append({"tipo": "reemplazar", "valores": actual, "paso": p["paso"]})
        else:
            distintos = [i for i, (a, b) in enumerate(zip(previo, actual)) if a != b]
            if len(distintos) == 2 and previo[distintos[0]] == actual[distintos[1]] and previo[distintos[1]] == actual[distintos[0]]:
                eventos.append({"tipo": "intercambio", "i": distintos[0], "j": distintos[1], "paso": p["paso"]})
            else:
                eventos += [{"tipo": "poner", "i": i, "valor": actual[i], "paso": p["paso"]} for i in distintos]
        previo = list(actual)
    importantes = [e for e in eventos if e["tipo"] != "puntero"]
    if len(eventos) > max_eventos:
        eventos = importantes[:max_eventos] if len(importantes) >= max_eventos else _recortar(eventos, max_eventos)
    return {"inicial": inicial, "eventos": eventos, "final": previo}


def _recortar(eventos: list[dict], maximo: int) -> list[dict]:
    """Conserva los eventos importantes y solo el último movimiento de puntero antes de cada uno."""
    salida, pendientes = [], {}
    for ev in eventos:
        if ev["tipo"] == "puntero":
            pendientes[ev["nombre"]] = ev
            continue
        salida += list(pendientes.values()) + [ev]
        pendientes = {}
    return salida[:maximo]


def narrar_evento_arreglo(evento: dict, arreglo: list) -> str:
    if evento["tipo"] == "intercambio":
        return f"Intercambiamos el {estilo.valor_corto(arreglo[evento['i']])} con el {estilo.valor_corto(arreglo[evento['j']])}."
    if evento["tipo"] == "poner":
        return f"En la posición {evento['i']} queda un {estilo.valor_corto(evento['valor'])}."
    if evento["tipo"] == "puntero":
        return f"{evento['nombre']} se mueve a la posición {evento['i']}."
    return "El arreglo cambia de tamaño."


def eventos_lista(traza: dict, variable: str, max_eventos: int = 24) -> dict:
    """Entradas y salidas de una pila o cola (append, pop, pop(0), heappush…)."""
    pasos = lineas_ejecutadas(traza)
    previo = next((p["vars"][variable] for p in pasos if isinstance(p["vars"].get(variable), list)), None)
    if previo is None:
        raise ValueError(f"La variable {variable!r} no es una lista en la traza.")
    inicial, eventos = list(previo), []
    for p in pasos:
        actual = despues(p).get(variable)
        if not isinstance(actual, list) or actual == previo:
            continue
        if len(actual) == len(previo) + 1 and actual[:-1] == previo:
            eventos.append({"tipo": "meter", "valor": actual[-1], "paso": p["paso"]})
        elif len(actual) == len(previo) - 1 and actual == previo[1:]:
            eventos.append({"tipo": "sacar", "indice": 0, "valor": previo[0], "paso": p["paso"]})
        elif len(actual) == len(previo) - 1 and actual == previo[:-1]:
            eventos.append({"tipo": "sacar", "indice": -1, "valor": previo[-1], "paso": p["paso"]})
        else:
            eventos.append({"tipo": "reemplazar", "valores": actual, "paso": p["paso"]})
        previo = list(actual)
    return {"inicial": inicial, "eventos": eventos[:max_eventos], "final": previo}


def narrar_evento_lista(evento: dict, nombre: str = "la pila") -> str:
    if evento["tipo"] == "meter":
        return f"Entra {estilo.valor_corto(evento['valor'])} a {nombre}."
    if evento["tipo"] == "sacar":
        return f"Sale {estilo.valor_corto(evento['valor'])}."
    return f"{nombre.capitalize()} se reacomoda."
