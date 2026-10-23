"""Instrucciones y esquemas JSON que el director le da al modelo. Todo en español.

Las tareas son pequeñas a propósito: un modelo local de 8–12B responde mejor a pedidos cortos y
concretos que a un guion entero de una vez.
"""

from __future__ import annotations

import copy

from .estilo import NOMBRES_ICONOS

SISTEMA = """Eres el guionista de videos educativos de programación en español, para un canal cercano y claro.
Escribes lo que una voz va a leer en voz alta y eliges qué se ve en pantalla.

Reglas de la narración:
- Español latino neutro, segunda persona ("tú"), frases cortas. De vez en cuando "fíjate" u "ojo", sin abusar.
- Escribe para el oído: nada de markdown, viñetas, emojis, comillas raras ni símbolos.
- Las opciones de un comando se nombran sin guiones: "la opción rm", "la opción i t", "la opción f s S L".
- Las rutas y archivos se nombran por lo que son: "la carpeta de llaves de apt", "el archivo de fuentes de Docker".
- Cada narración: una o dos frases, máximo unas 40 palabras.
- No inventes datos, versiones, cifras ni resultados que no estén en el material o que no sean de conocimiento general seguro.
- Responde solo con el JSON pedido."""

ICONO = {"type": "string", "enum": [*NOMBRES_ICONOS, ""]}
TEXTO = {"type": "string"}
ENTEROS = {"type": "array", "items": {"type": "integer"}, "maxItems": 6}


def _objeto(propiedades: dict, requeridos: list[str] | None = None) -> dict:
    return {"type": "object", "properties": propiedades, "required": requeridos or list(propiedades)}


def _lista(items: dict, minimo: int = 0, maximo: int | None = None) -> dict:
    """Arreglo con límites: sin maxItems, un modelo pequeño puede repetir elementos sin fin."""
    esquema = {"type": "array", "items": items, "minItems": minimo}
    if maximo is not None:
        esquema["maxItems"] = maximo
    return esquema


def con_cantidad(esquema: dict, ruta: str, minimo: int, maximo: int | None = None) -> dict:
    """Copia del esquema con otros límites en el arreglo de `ruta` (por ejemplo "comandos" u "objetivos")."""
    copia = copy.deepcopy(esquema)
    nodo = copia
    partes = ruta.split(".")
    for k, parte in enumerate(partes):
        nodo = nodo["properties"][parte]
        if k < len(partes) - 1:
            nodo = nodo["items"]
    nodo["minItems"] = minimo
    nodo["maxItems"] = minimo if maximo is None else maximo
    return copia


ESQUEMA_INTRO = _objeto({
    "gancho": _lista(TEXTO, 1, 2),
    "pantalla_gancho": TEXTO,
    "icono": ICONO,
    "objetivos": _lista(_objeto({"texto": TEXTO, "punto": TEXTO}), 0, 10),
})

ESQUEMA_PARTE = _objeto({"narracion": _lista(TEXTO, 1, 2), "icono": ICONO})

ESQUEMA_TERMINAL = _objeto({
    "intro": TEXTO,
    "comandos": _lista(_objeto({
        "texto": TEXTO,
        "partes": _lista(_objeto({"fragmento": TEXTO, "texto": TEXTO, "nota": TEXTO}), 0, 3),
        "salida": _lista(TEXTO, 0, 6),
        "texto_salida": TEXTO,
    }), 1, 12),
    "aviso": _objeto({"sello": {"type": "string", "enum": ["", "NOTA", "IMPORTANTE", "ADVERTENCIA", "SUGERENCIA"]},
                      "pantalla": TEXTO, "texto": TEXTO}),
})

ESQUEMA_TABLA = _objeto({"bloques": _lista(_objeto({"texto": TEXTO, "resaltar": ENTEROS}), 1, 3)})

ESQUEMA_PASOS = _objeto({
    "intro": TEXTO,
    "items": _lista(_objeto({"texto": TEXTO, "punto": TEXTO}), 1, 12),
})

ESQUEMA_IDEA = _objeto({"bloques": _lista(_objeto(
    {"texto": TEXTO, "pantalla": TEXTO, "icono": ICONO, "sello": TEXTO}), 1, 3)})

_ELEMENTO = _objeto({"titulo": TEXTO, "detalle": TEXTO, "icono": ICONO})
ESQUEMA_VISUALES = _objeto({"visuales": _lista(_objeto({
    "despues_de": {"type": "integer"},
    "tipo": {"type": "string", "enum": ["diagrama", "capas", "piezas"]},
    "titulo": TEXTO,
    "cajas": _lista(_objeto({"id": TEXTO, "titulo": TEXTO, "detalle": TEXTO, "icono": ICONO}), 0, 5),
    "flechas": _lista(_objeto({"de": TEXTO, "a": TEXTO, "etiqueta": TEXTO}), 0, 6),
    "capas": _lista(_ELEMENTO, 0, 5),
    "items": _lista(_ELEMENTO, 0, 6),
    "destino": _objeto({"titulo": TEXTO, "icono": ICONO}),
    "pasos": _lista(_objeto({
        "texto": TEXTO, "resaltar": TEXTO, "flujo_de": TEXTO, "flujo_a": TEXTO, "viajero": ICONO,
        "mostrar": ENTEROS, "instalar": {"type": "boolean"}}, ["texto"]), 2, 4),
}, ["despues_de", "tipo", "titulo", "pasos"]), 0, 2)})

ESQUEMA_CIERRE = _objeto({"texto": TEXTO, "puntos": _lista(TEXTO, 0, 10), "reto": TEXTO,
                          "despedida": TEXTO})

ESQUEMA_LINEAS = _objeto({
    "titulo": TEXTO,
    "intro": TEXTO,
    "lineas": _lista(_objeto({"desde": {"type": "integer"}, "hasta": {"type": "integer"}, "texto": TEXTO}), 1, 16),
    "estado": _lista(TEXTO, 0, 4),
    "resultado": TEXTO,
})

ESQUEMA_LLAMADA = _objeto({"llamada": TEXTO, "explicacion": TEXTO})

ESQUEMA_ELEGIR = _objeto({
    "tema": TEXTO,
    "fragmentos": _lista(_objeto({"archivo": TEXTO, "desde": {"type": "integer"}, "hasta": {"type": "integer"},
                                  "por_que": TEXTO}), 1, 3),
})


def intro(titulo: str, parrafos: list[str], objetivos: list[str]) -> str:
    lista = "\n".join(f"{i}. {o}" for i, o in enumerate(objetivos))
    return f"""Material: el comienzo de una guía titulada «{titulo}».

{chr(10).join(parrafos)}

Objetivos de la guía (en orden):
{lista or '(no hay)'}

Escribe:
- "gancho": dos narraciones para abrir el video. La primera engancha con una situación cotidiana relacionada con el tema; la segunda dice de qué trata el video.
- "pantalla_gancho": una frase muy corta para la pantalla; marca la palabra clave entre *asteriscos*.
- "icono": el ícono que mejor representa el tema.
- "objetivos": exactamente {len(objetivos)} elementos, uno por objetivo y en el mismo orden. "texto" es la narración (una frase) y "punto" un resumen de 3 a 6 palabras para la pantalla."""


def parte(titulo: str, parrafos: list[str], pasos: list[str]) -> str:
    return f"""Se viene una parte nueva del video: «{titulo}».
Texto de la guía para esta parte:
{chr(10).join(parrafos) or '(sin texto)'}
Pasos que incluye: {', '.join(pasos) or '(ninguno)'}

Escribe "narracion": una o dos narraciones que presenten esta parte y digan qué se va a lograr. Elige un "icono"."""


def terminal(titulo: str, parrafos: list[str], comandos: list[str], shell: str) -> str:
    lista = "\n".join(f"[{i}] {c}" for i, c in enumerate(comandos))
    return f"""Paso de la guía: «{titulo}» (comandos de {shell}).
Texto de la guía:
{chr(10).join(parrafos) or '(sin texto)'}

Comandos, en orden:
{lista}

Escribe:
- "intro": una narración que diga para qué sirve este paso.
- "comandos": exactamente {len(comandos)} elementos, uno por comando y en el mismo orden. Para cada uno:
  - "texto": qué hace el comando, dicho para el oído.
  - "partes": de 0 a 3 fragmentos que valga la pena explicar. "fragmento" se copia EXACTO del comando (letra por letra), "texto" lo explica en una frase y "nota" lo resume en 2 a 6 palabras para pantalla. Los comandos muy simples no llevan partes.
  - "salida": SOLO si es un comando de verificación (ver versión, estado, grupos, listar, ejecutar un contenedor de prueba), hasta 6 líneas de lo que imprime, tal como se ve en una terminal real (el usuario se llama "usuario"). Para comandos que instalan, actualizan, borran o configuran: lista vacía. Si no conoces la salida exacta, lista vacía. Si la salida es larga, pon las primeras líneas, una línea con … y la última.
  - "texto_salida": si hay salida, una frase sobre qué significa; si no, vacío.
- "aviso": si el texto trae una nota, advertencia o dato importante, "sello" (NOTA, IMPORTANTE, ADVERTENCIA o SUGERENCIA), "pantalla" (frase corta con la palabra clave entre *asteriscos*) y "texto" (la narración). Si no hay nada que avisar, los tres vacíos."""


def tabla(titulo: str, parrafos: list[str], encabezados: list[str], filas: list[list[str]]) -> str:
    cuerpo = "\n".join(f"[{i}] " + " | ".join(f) for i, f in enumerate(filas))
    return f"""Paso de la guía: «{titulo}». Hay una tabla:
{' | '.join(encabezados)}
{cuerpo}
Texto de la guía:
{chr(10).join(parrafos) or '(sin texto)'}

Escribe "bloques": de 1 a 3 narraciones que expliquen la tabla. En cada una, "resaltar" lleva los números de las filas de las que habla (lista vacía si habla de la tabla en general)."""


def pasos(titulo: str, parrafos: list[str], items: list[str]) -> str:
    lista = "\n".join(f"{i}. {t}" for i, t in enumerate(items))
    return f"""Paso de la guía: «{titulo}». Son estos pasos, en orden:
{lista}
Texto de la guía:
{chr(10).join(parrafos) or '(sin texto)'}

Escribe "intro" (una narración) e "items": exactamente {len(items)} elementos en el mismo orden, con "texto" (narración de una o dos frases) y "punto" (resumen de 3 a 6 palabras)."""


def ideas(titulo: str, parrafos: list[str]) -> str:
    return f"""Paso de la guía: «{titulo}», solo con texto:
{chr(10).join(parrafos)}

Escribe "bloques": de 1 a 3 narraciones. Cada una con "pantalla" (frase corta con la palabra clave entre *asteriscos*), "icono" y "sello" (vacío, o NOTA, IMPORTANTE, ADVERTENCIA si es un aviso)."""


def visuales(titulo: str, pasos_parte: list[tuple[str, str]]) -> str:
    lista = "\n".join(f"[{i}] {t}: {r}" for i, (t, r) in enumerate(pasos_parte))
    return f"""Parte del video: «{titulo}». Sus pasos, en orden:
{lista}

Propón de 1 a 2 animaciones que ayuden a ENTENDER el concepto (no a repetir los comandos). Tipos:
- "diagrama": cajas con ícono unidas por flechas, y pasos donde algo viaja de una caja a otra. Usa "cajas" (de 3 a 5, cada una con "id" corto sin espacios), "flechas" ("de" y "a" son ids) y en cada paso "resaltar" (un id o vacío), "flujo_de" y "flujo_a" (ids de una flecha que exista, o vacíos) y "viajero" (ícono que viaja, o vacío).
- "capas": una pila de capas. El PRIMER elemento de "capas" es la base, lo de más abajo (el equipo o el sistema operativo), y el ÚLTIMO es lo de más arriba (la aplicación o tus contenedores). Usa de 3 a 5 capas y en los pasos "mostrar" con los números de capa que aparecen, empezando por la base.
- "piezas": varias cosas que se instalan o se juntan. Usa "items" (de 2 a 6), "destino" y en los pasos "mostrar" o "instalar": true.
"despues_de" es el número del paso detrás del cual va la animación. Cada animación lleva de 2 a 4 pasos, cada uno con su "texto" (la narración). Lo que no uses va vacío o como lista vacía."""


def cierre(titulo: str, cubierto: list[str]) -> str:
    lista = "\n".join(f"- {c}" for c in cubierto)
    return f"""Se acaba el video sobre «{titulo}». La guía cubrió:
{lista or '(sin lista)'}

Escribe "texto" (una o dos narraciones de repaso en un solo texto), "puntos" (exactamente {len(cubierto)} resúmenes de 3 a 5 palabras, en orden), "reto" (un reto corto y concreto para practicar) y "despedida" (una frase corta)."""


def lineas_codigo(archivo: str, numerado: str, resumen_traza: str) -> str:
    return f"""Archivo: {archivo}. Fragmento con números de línea:
{numerado}

{resumen_traza}

Escribe:
- "titulo": nombre corto de lo que hace el fragmento (por ejemplo "Dijkstra en Python").
- "intro": una narración que presente el fragmento.
- "lineas": recorre lo más importante línea por línea. Cada elemento cubre una línea o un grupo pequeño ("desde" y "hasta" son números de línea del fragmento) con su "texto" (una o dos frases). En orden, sin saltar la idea central.
- "estado": hasta 4 nombres de variables que convenga mostrar en la tabla de estado (solo de las que aparecen en la traza; lista vacía si no hay traza).
- "resultado": una narración sobre qué devuelve o qué deja listo al final."""


def llamada(archivo: str, funcion: str, numerado: str, globales: list[str], error: str | None) -> str:
    extra = f"\nEl intento anterior falló así: {error}\nCorrígelo." if error else ""
    return f"""Archivo: {archivo}. Quiero ejecutar la función «{funcion}» con un ejemplo pequeño para mostrar sus variables.
{numerado}

Nombres definidos a nivel de módulo que puedes usar: {', '.join(globales) or '(ninguno)'}

Escribe "llamada": una expresión de Python que llame a {funcion} con datos pequeños y claros (por ejemplo {funcion}(...)), usando literales o esos nombres. Nada de leer archivos, red ni entrada del usuario. "explicacion": qué ejemplo elegiste.{extra}"""


def elegir(inventario: str, muestras: str) -> str:
    return f"""Este es un proyecto de código. Archivos:
{inventario}

Primeras líneas de los archivos principales:
{muestras}

Escribe "tema" (de qué trata el proyecto, en una frase) y "fragmentos": de 1 a 3 trozos de código que mejor expliquen cómo funciona (la lógica central, no configuración). Cada uno con "archivo" (ruta exacta de la lista), "desde" y "hasta" (máximo 22 líneas por trozo) y "por_que"."""
