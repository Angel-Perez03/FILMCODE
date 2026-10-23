"""El director para código fuente: elige los fragmentos clave, ejecuta los de Python con un ejemplo pequeño
para tener valores reales, detecta qué animar (grafo, arreglo, pila) y pide la explicación línea por línea."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from . import ingesta
from . import prompts as P
from .director import Director
from .estilo import MAX_LINEAS, letra
from .eventos import bloques_grafo, eventos_arreglo, eventos_lista, grafo_desde_valor, lineas_ejecutadas

PROHIBIDOS_EN_LLAMADA = {"open", "input", "exec", "eval", "compile", "__import__", "os", "sys", "subprocess",
                         "shutil", "socket", "requests", "urllib", "pathlib", "globals", "locals", "setattr", "delattr"}


def _seguro(llamada: str, funcion: str) -> list[str]:
    try:
        arbol = ast.parse(llamada, mode="eval")
    except SyntaxError as error:
        return [f"La llamada no es Python válido: {error}"]
    if not (isinstance(arbol.body, ast.Call) and isinstance(arbol.body.func, ast.Name) and arbol.body.func.id == funcion):
        return [f"La llamada debe ser exactamente {funcion}(...)."]
    usados = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    malos = sorted(usados & PROHIBIDOS_EN_LLAMADA)
    return [f"La llamada no puede usar: {', '.join(malos)}."] if malos else []


class DirectorCodigo(Director):
    def codigo(self, carpeta_codigo: Path) -> dict:
        """`carpeta_codigo` es la copia de la fuente dentro del proyecto (videos/<nombre>/codigo)."""
        archivos = ingesta.archivos(carpeta_codigo)
        if not archivos:
            raise ValueError("No encontré archivos de código en la fuente.")
        tema, fragmentos = self._elegir(carpeta_codigo, archivos)
        # Apertura, explicación de cada fragmento y cierre. La traza no añade narración del modelo.
        self.duracion.repartir(2 + len(fragmentos))
        self.progreso("fragmentos elegidos", 0.1)
        escenas, guion_frag, titulos = [], {}, []
        apertura = self._apertura({"titulo": tema, "intro": [tema] + [f["por_que"] for f in fragmentos if f.get("por_que")],
                                   "objetivos": []})
        escenas += apertura
        for k, frag in enumerate(fragmentos, 1):
            fid = f"f{k}"
            ruta = self.proyecto / frag["archivo"]
            traza_rel, traza = None, None
            if ruta.suffix == ".py":
                traza_rel, traza = self._trazar(fid, ruta, frag)
            guion_frag[fid] = {"archivo": frag["archivo"], "desde": frag["desde"], "hasta": frag["hasta"],
                               "lenguaje": ingesta.lenguaje_de(ruta) or "text", "traza": traza_rel}
            concepto, extra = self._concepto(fid, traza) if traza else (None, {})
            codigo = self._lineas(fid, ruta, frag, traza, extra)
            titulos.append(codigo.get("titulo") or ruta.name)
            if concepto:
                escenas.append(concepto)
            escenas.append(codigo)
            self.progreso(f"fragmento {k} listo", 0.1 + 0.8 * k / len(fragmentos))
        escenas.append(self._cierre({"titulo": tema, "cubierto": titulos, "objetivos": []}))
        return {"version": 1, "titulo": tema, "fragmentos": guion_frag, "escenas": escenas}

    # Qué explicar
    def _elegir(self, carpeta: Path, archivos: list[Path]) -> tuple[str, list[dict]]:
        relativos = {a.relative_to(self.proyecto).as_posix(): a for a in archivos}
        totales = {r: len(a.read_text(encoding="utf-8", errors="replace").splitlines()) for r, a in relativos.items()}
        if len(archivos) == 1 and totales[next(iter(relativos))] <= MAX_LINEAS:
            rel = next(iter(relativos))
            return Path(rel).stem, [{"archivo": rel, "desde": 1, "hasta": totales[rel], "por_que": ""}]
        inventario = "\n".join(f"- {r} ({totales[r]} líneas)" for r in relativos)
        principales = sorted(relativos, key=lambda r: -totales[r])[:10]
        muestras = []
        for r in principales:
            lineas = relativos[r].read_text(encoding="utf-8", errors="replace").splitlines()
            limite = 400 if len(archivos) == 1 else 40
            muestras.append(f"### {r}\n{ingesta.numerado(chr(10).join(lineas[:limite]))}")

        def validar(d: dict) -> list[str]:
            errores = []
            if not d.get("fragmentos"):
                return ["Elige al menos un fragmento."]
            for f in d["fragmentos"]:
                if f.get("archivo") not in relativos:
                    errores.append(f"El archivo {f.get('archivo')!r} no está en la lista.")
                    continue
                desde, hasta = f.get("desde", 0), f.get("hasta", 0)
                if not 1 <= desde <= hasta <= totales[f["archivo"]]:
                    errores.append(f"{f['archivo']}: líneas {desde}-{hasta} fuera del archivo (1-{totales[f['archivo']]}).")
                elif hasta - desde + 1 > MAX_LINEAS:
                    errores.append(f"{f['archivo']}: {hasta - desde + 1} líneas; máximo {MAX_LINEAS} por fragmento.")
            return errores

        r = self.pedir(P.elegir(inventario, "\n\n".join(muestras)), P.ESQUEMA_ELEGIR, validar, "elegir")
        return r["tema"], r["fragmentos"][:3]

    # Ejecutar con un ejemplo
    def _funcion_en(self, ruta: Path, desde: int, hasta: int) -> str | None:
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        except SyntaxError:
            return None
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and desde <= nodo.lineno <= hasta:
                return nodo.name
        return None

    def _trazar(self, fid: str, ruta: Path, frag: dict) -> tuple[str | None, dict | None]:
        funcion = self._funcion_en(ruta, frag["desde"], frag["hasta"])
        if not funcion:
            return None, None
        texto = ruta.read_text(encoding="utf-8")
        globales = sorted({n.id for n in ast.walk(ast.parse(texto)) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
                           and n.id.isupper()})
        numerado = ingesta.numerado("\n".join(texto.splitlines()[frag["desde"] - 1: frag["hasta"]]), frag["desde"])
        destino = self.proyecto / "trazas" / f"{fid}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        error = None
        for intento in range(3):
            r = self.pedir(P.llamada(frag["archivo"], funcion, numerado, globales, error), P.ESQUEMA_LLAMADA,
                           lambda d: _seguro(d.get("llamada", ""), funcion), f"llamada {intento + 1}")
            error = ejecutar_traza(ruta, r["llamada"], funcion, destino)
            if error is None:
                traza = json.loads(destino.read_text(encoding="utf-8"))
                if traza.get("error"):
                    error = traza["error"]
                elif lineas_ejecutadas(traza):
                    return destino.relative_to(self.proyecto).as_posix(), traza
        self.progreso(f"no pude ejecutar {funcion} ({error}); se explica sin valores", -1)
        destino.unlink(missing_ok=True)
        return None, None

    # Qué animar según lo que pasó al ejecutar
    def _concepto(self, fid: str, traza: dict) -> tuple[dict | None, dict]:
        pasos = lineas_ejecutadas(traza)
        iniciales = pasos[0]["vars"]
        finales = {**pasos[-1]["vars"], **pasos[-1].get("cambios", {})}
        for nombre, valor in iniciales.items():
            try:
                grafo = grafo_desde_valor(valor)
            except (ValueError, TypeError, KeyError):
                continue
            n = len(grafo["nodos"])
            if n < 3 or not grafo["aristas"]:
                continue
            valores = next((v for v, x in finales.items() if v != nombre and isinstance(x, list) and len(x) == n
                            and any(isinstance(y, (int, float)) for y in x) and not any(y is None for y in x)), None)
            actual = _nodo_actual(pasos, n)
            previo = next((v for v, x in finales.items() if v not in (nombre, valores) and isinstance(x, list)
                           and len(x) == n and any(y is None for y in x)), None)
            escena = {"tipo": "grafo_traza", "fragmento": fid, "argumento": nombre, "valores": valores, "actual": actual}
            if valores:
                escena["nota"] = "lo que va calculando el código"
            if previo and valores:
                numericos = [(x, i) for i, x in enumerate(finales[valores]) if isinstance(x, (int, float))]
                if numericos:
                    escena.update(previo=previo, destino=letra(max(numericos)[1]))
            try:
                bloques_grafo(traza, nombre, valores, actual)
            except Exception:  # noqa: BLE001 - si la heurística no encaja, se sigue sin animación
                continue
            extra = {"etiquetas_columnas": grafo["nodos"] if valores else [],
                     "variables_nodo": [v for v in (previo, actual) if v]}
            return escena, extra
        for nombre, valor in iniciales.items():
            if isinstance(valor, list) and 3 <= len(valor) <= 12 and all(isinstance(x, (int, float)) for x in valor):
                datos = eventos_arreglo(traza, nombre, [v for v in finales if isinstance(finales[v], int)][:2])
                if any(ev["tipo"] != "puntero" for ev in datos["eventos"]):
                    return {"tipo": "arreglo_traza", "fragmento": fid, "variable": nombre,
                            "punteros": [v for v in finales if isinstance(finales[v], int)][:2]}, {}
        for nombre, valor in finales.items():
            if isinstance(valor, list):
                try:
                    datos = eventos_lista(traza, nombre)
                except ValueError:
                    continue
                tipos = {ev["tipo"] for ev in datos["eventos"]}
                if "meter" in tipos and "sacar" in tipos:
                    estilo = "cola" if any(ev.get("indice") == 0 for ev in datos["eventos"]) else "pila"
                    return {"tipo": "lista_traza", "fragmento": fid, "variable": nombre, "estilo": estilo}, {}
        return None, {}

    # Explicación línea por línea
    def _lineas(self, fid: str, ruta: Path, frag: dict, traza: dict | None, extra: dict) -> dict:
        lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
        numerado = ingesta.numerado("\n".join(lineas[frag["desde"] - 1: frag["hasta"]]), frag["desde"])
        resumen, variables = "No se ejecutó: explica el código sin valores.", set()
        if traza:
            vistos, renglones = set(), []
            for p in lineas_ejecutadas(traza):
                variables |= set(p["vars"]) | set(p.get("cambios", {}))
                if p["linea"] in vistos or not p.get("cambios"):
                    continue
                vistos.add(p["linea"])
                cambios = ", ".join(f"{k} = {json.dumps(v, ensure_ascii=False)[:50]}" for k, v in p["cambios"].items())
                renglones.append(f"línea {p['linea']}: {cambios}")
            resumen = (f"Se ejecutó con: {traza['llamada']}. Primeros cambios de variables:\n"
                       + "\n".join(renglones[:25]) + f"\nResultado: {json.dumps(traza.get('resultado'), ensure_ascii=False)[:120]}")

        def validar(d: dict) -> list[str]:
            errores = [] if d.get("lineas") else ["'lineas' no puede estar vacío."]
            for item in d.get("lineas", []):
                if not frag["desde"] <= item.get("desde", 0) <= item.get("hasta", 0) <= frag["hasta"]:
                    errores.append(f"Líneas {item.get('desde')}-{item.get('hasta')} fuera del fragmento "
                                   f"({frag['desde']}-{frag['hasta']}) o al revés.")
            if traza:
                errores += [f"La variable {v!r} no aparece en la traza." for v in d.get("estado", []) if v not in variables]
            return errores

        r = self.pedir(P.lineas_codigo(frag["archivo"], numerado, resumen), P.ESQUEMA_LINEAS, validar, "líneas")
        escena = {"tipo": "codigo", "fragmento": fid, "titulo": r.get("titulo") or ruta.name, "antetitulo": "El código",
                  "intro": r.get("intro") or None, "lineas": r["lineas"], "resultado": r.get("resultado") or None}
        if traza and r.get("estado"):
            escena["estado"] = r["estado"][:4]
            if extra.get("etiquetas_columnas") and any(isinstance(traza["pasos"][-1]["vars"].get(v), list)
                                                       for v in escena["estado"]):
                escena["etiquetas_columnas"] = extra["etiquetas_columnas"]
            escena["variables_nodo"] = [v for v in extra.get("variables_nodo", []) if v in escena["estado"]]
        return escena


def _nodo_actual(pasos: list[dict], n: int) -> str | None:
    """La variable que hace de 'nodo que se está visitando': entera, siempre entre 0 y n-1, y la que menos
    cambia entre las candidatas (u cambia una vez por nodo; v, una vez por vecino)."""
    historia: dict[str, list] = {}
    for p in pasos:
        for nombre, valor in {**p["vars"], **p.get("cambios", {})}.items():
            historia.setdefault(nombre, []).append(valor)
    candidatas = []
    for nombre, valores in historia.items():
        if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v < n for v in valores):
            continue
        if len(set(valores)) < 3:
            continue
        cambios = sum(1 for a, b in zip(valores, valores[1:]) if a != b)
        candidatas.append((cambios, nombre))
    return min(candidatas)[1] if candidatas else None


def ejecutar_traza(archivo: Path, llamada: str, funcion: str, destino: Path, timeout: int = 30) -> str | None:
    """Corre el trazador en otro proceso. Devuelve None si salió bien o el error si no."""
    orden = [sys.executable, "-I", "-m", "videocodigo.trazador", str(archivo), llamada, "--funciones", funcion,
             "--salida", str(destino)]
    entorno_src = str(Path(__file__).resolve().parents[1])
    try:
        proceso = subprocess.run(orden, capture_output=True, text=True, timeout=timeout, cwd=archivo.parent,
                                 env={**_entorno(), "PYTHONPATH": entorno_src})
    except subprocess.TimeoutExpired:
        return f"tardó más de {timeout} s (¿bucle infinito o ejemplo muy grande?)"
    if proceso.returncode != 0:
        return (proceso.stderr or proceso.stdout).strip().splitlines()[-1][:300] if (proceso.stderr or proceso.stdout) else "falló"
    return None


def _entorno() -> dict:
    import os

    return {k: v for k, v in os.environ.items() if k not in ("OMNIVOICE_API_KEY", "OPENAI_API_KEY")}
