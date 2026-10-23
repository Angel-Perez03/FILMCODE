"""Lectura de la fuente: documentos Markdown (guías, laboratorios), archivos de código y carpetas."""

from __future__ import annotations

import ast
import re
from pathlib import Path

IGNORAR = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".idea", ".vscode",
           ".pytest_cache", ".mypy_cache", "target", "bin", "obj", ".next", "coverage"}
EXT_DOCUMENTO = {".md", ".markdown", ".txt"}
EXT_CODIGO = {".py": "python", ".js": "javascript", ".ts": "typescript", ".jsx": "jsx", ".tsx": "tsx",
              ".java": "java", ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".cs": "csharp", ".go": "go",
              ".rs": "rust", ".rb": "ruby", ".php": "php", ".kt": "kotlin", ".swift": "swift", ".sh": "bash",
              ".ps1": "powershell", ".sql": "sql", ".html": "html", ".css": "css", ".yml": "yaml", ".yaml": "yaml",
              ".json": "json", ".dockerfile": "docker"}
MAX_ARCHIVOS = 400
MAX_BYTES = 400_000


def lenguaje_de(ruta: Path) -> str | None:
    if ruta.name.lower() == "dockerfile":
        return "docker"
    return EXT_CODIGO.get(ruta.suffix.lower())


def tipo_fuente(ruta: Path) -> str:
    if ruta.is_dir():
        return "carpeta"
    if ruta.suffix.lower() in EXT_DOCUMENTO:
        return "documento"
    return "codigo"


def archivos(carpeta: Path) -> list[Path]:
    """Archivos de texto útiles de una carpeta, sin dependencias ni compilados."""
    salida = []
    for ruta in sorted(carpeta.rglob("*")):
        if any(parte in IGNORAR for parte in ruta.relative_to(carpeta).parts):
            continue
        if ruta.is_file() and (lenguaje_de(ruta) or ruta.suffix.lower() in EXT_DOCUMENTO):
            if ruta.stat().st_size <= MAX_BYTES:
                salida.append(ruta)
        if len(salida) >= MAX_ARCHIVOS:
            break
    return salida


def inventario(raiz: Path) -> list[dict]:
    rutas = archivos(raiz) if raiz.is_dir() else [raiz]
    base = raiz if raiz.is_dir() else raiz.parent
    salida = []
    for ruta in rutas:
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        salida.append({"ruta": ruta.relative_to(base).as_posix(), "lenguaje": lenguaje_de(ruta) or "texto",
                       "lineas": texto.count("\n") + 1, "bytes": len(texto.encode("utf-8"))})
    return salida


# Documentos Markdown

TITULO = re.compile(r"^(#{1,6})\s+(.*)$")
FILA_TABLA = re.compile(r"^\s*\|(.+)\|\s*$")
ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")


def documento(ruta: Path) -> dict:
    """Estructura de un Markdown: título, introducción y secciones con párrafos, código, tablas y listas."""
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    doc = {"titulo": "", "intro": [], "secciones": []}
    actual = None
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        m = TITULO.match(linea)
        if m:
            nivel, titulo = len(m.group(1)), m.group(2).strip()
            if nivel == 1 and not doc["titulo"]:
                doc["titulo"] = titulo
            else:
                actual = {"nivel": nivel, "titulo": titulo, "bloques": []}
                doc["secciones"].append(actual)
            i += 1
            continue
        destino = actual["bloques"] if actual else None
        if linea.strip().startswith("```"):
            lenguaje = linea.strip()[3:].strip() or "text"
            codigo = []
            i += 1
            while i < len(lineas) and not lineas[i].strip().startswith("```"):
                codigo.append(lineas[i])
                i += 1
            bloque = {"tipo": "codigo", "lenguaje": lenguaje, "texto": "\n".join(codigo)}
            (destino if destino is not None else doc["intro"]).append(bloque)
            i += 1
            continue
        if FILA_TABLA.match(linea):
            filas = []
            while i < len(lineas) and FILA_TABLA.match(lineas[i]):
                celdas = [c.strip() for c in FILA_TABLA.match(lineas[i]).group(1).split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in celdas):
                    filas.append(celdas)
                i += 1
            if filas:
                bloque = {"tipo": "tabla", "encabezados": filas[0], "filas": filas[1:]}
                (destino if destino is not None else doc["intro"]).append(bloque)
            continue
        if ITEM.match(linea):
            items, ordenada = [], bool(re.match(r"^\s*\d", linea))
            while i < len(lineas) and ITEM.match(lineas[i]):
                items.append(ITEM.match(lineas[i]).group(1).strip())
                i += 1
            bloque = {"tipo": "lista", "ordenada": ordenada, "items": items}
            (destino if destino is not None else doc["intro"]).append(bloque)
            continue
        if linea.strip():
            parrafo = [linea.strip()]
            i += 1
            while i < len(lineas) and lineas[i].strip() and not (
                    TITULO.match(lineas[i]) or FILA_TABLA.match(lineas[i]) or ITEM.match(lineas[i])
                    or lineas[i].strip().startswith("```")):
                parrafo.append(lineas[i].strip())
                i += 1
            bloque = {"tipo": "parrafo", "texto": " ".join(parrafo)}
            (destino if destino is not None else doc["intro"]).append(bloque)
            continue
        i += 1
    return doc


def comandos_de(bloque_codigo: dict) -> list[str]:
    """Parte un bloque de terminal en comandos; un heredoc (<<EOF … EOF) queda como un solo comando."""
    salida, actual, fin = [], [], None
    for linea in bloque_codigo["texto"].splitlines():
        if fin is not None:
            actual.append(linea)
            if linea.strip() == fin:
                salida.append("\n".join(actual))
                actual, fin = [], None
            continue
        if not linea.strip() or linea.strip().startswith("#"):
            continue
        if "<<" in linea:
            fin = linea.split("<<", 1)[1].strip().strip("'\"-") or None
            actual = [linea]
            if fin is None:
                salida.append(linea)
            continue
        salida.append(linea)
    if actual:
        salida.append("\n".join(actual))
    return salida


# Código Python

def funciones_python(ruta: Path) -> list[dict]:
    """Funciones y métodos de un archivo Python con sus líneas, argumentos y docstring."""
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    salida = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            salida.append({"nombre": nodo.name, "desde": nodo.lineno, "hasta": nodo.end_lineno,
                           "argumentos": [a.arg for a in nodo.args.args],
                           "doc": (ast.get_docstring(nodo) or "")[:200]})
    return sorted(salida, key=lambda f: f["desde"])


def numerado(texto: str, desde: int = 1) -> str:
    """Código con número de línea al inicio, para que el modelo cite líneas exactas."""
    return "\n".join(f"{desde + i:>4}| {l}" for i, l in enumerate(texto.splitlines()))
