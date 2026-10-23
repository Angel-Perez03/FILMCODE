"""El director: lee la fuente, le pide al modelo las piezas del guion una por una, captura la salida real
de los comandos que se pueden verificar y arma un guion.json válido.

Documentos (guías, laboratorios) se resuelven aquí; el código fuente, en director_codigo.py.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

from . import capturas, ingesta
from . import guion as g
from . import prompts as P
from .duracion import PresupuestoNarracion
from .llm import ClienteLLM

Progreso = Callable[[str, float], None]
SELLOS = {"NOTA", "IMPORTANTE", "ADVERTENCIA", "SUGERENCIA"}


def _parrafos(bloques: list[dict]) -> list[str]:
    return [b["texto"] for b in bloques if b["tipo"] == "parrafo"]


def plan_documento(doc: dict) -> dict:
    """Agrupa las secciones del Markdown en objetivos, partes con pasos y lo cubierto (sin modelo)."""
    plan = {"titulo": doc["titulo"], "intro": _parrafos(doc["intro"]), "objetivos": [], "cubierto": [], "partes": []}
    actual, saltar = None, False
    for s in doc["secciones"]:
        titulo, bloques = s["titulo"], s["bloques"]
        listas = [b for b in bloques if b["tipo"] == "lista"]
        if s["nivel"] <= 2:
            saltar = bool(re.search(r"referencia|bibliograf|fuentes", titulo, re.I))
            if listas and re.search(r"aprender|objetivo", titulo, re.I):
                plan["objetivos"] = listas[0]["items"]
                continue
            if listas and re.search(r"cubri|resumen|conclusi|repaso", titulo, re.I):
                plan["cubierto"] = listas[0]["items"]
                continue
            if saltar:
                continue
            actual = {"titulo": titulo, "parrafos": _parrafos(bloques), "pasos": []}
            plan["partes"].append(actual)
            if any(b["tipo"] in ("codigo", "tabla", "lista") for b in bloques):
                actual["pasos"].append({"titulo": titulo, "bloques": bloques})
                actual["parrafos"] = []
            continue
        if saltar:
            continue
        if actual is None:
            actual = {"titulo": plan["titulo"], "parrafos": [], "pasos": []}
            plan["partes"].append(actual)
        actual["pasos"].append({"titulo": titulo, "bloques": bloques})
    return plan


class Director:
    def __init__(self, proyecto: Path, cliente: ClienteLLM, progreso: Progreso | None = None,
                 capturar_reales: bool = True, duracion_objetivo_minutos: float | None = None):
        self.proyecto, self.cliente = Path(proyecto), cliente
        self.progreso = progreso or (lambda mensaje, fraccion: None)
        self.capturar_reales = capturar_reales
        self.capturas: dict[str, dict] = {}
        self.duracion = PresupuestoNarracion(duracion_objetivo_minutos)

    def pedir(self, usuario: str, esquema: dict, validar=None, etiqueta: str = "") -> dict:
        narrada = etiqueta != "elegir" and not etiqueta.startswith("llamada")
        respuesta = self.cliente.json(P.SISTEMA, usuario + self.duracion.instruccion(narrada), esquema,
                                      validar=validar, etiqueta=etiqueta)
        if narrada:
            self.duracion.registrar(respuesta)
        return respuesta

    # Documento completo
    def documento(self, ruta: Path) -> dict:
        plan = plan_documento(ingesta.documento(ruta))
        solicitudes = 2  # apertura y cierre
        for parte in plan["partes"]:
            solicitudes += 1 + bool(parte["pasos"])  # presentación de parte y visuales
            for paso in parte["pasos"]:
                bloques = paso["bloques"]
                tablas = sum(b["tipo"] == "tabla" for b in bloques)
                codigo = any(b["tipo"] == "codigo" for b in bloques)
                lista = any(b["tipo"] == "lista" for b in bloques) and not codigo
                solicitudes += (tablas + codigo + lista) or bool(_parrafos(bloques))
        self.duracion.repartir(solicitudes)
        total = 2 + sum(len(p["pasos"]) + 2 for p in plan["partes"])
        hechos = [0]

        def avanzar(mensaje: str) -> None:
            hechos[0] += 1
            self.progreso(mensaje, min(hechos[0] / total, 0.99))

        escenas = self._apertura(plan)
        avanzar("apertura")
        for numero, parte in enumerate(plan["partes"], 1):
            escenas += self._parte(numero, parte, avanzar)
        escenas.append(self._cierre(plan))
        avanzar("cierre")
        guion = {"version": 1, "titulo": plan["titulo"], "fragmentos": {}, "escenas": escenas}
        self._guardar_capturas()
        return guion

    def _apertura(self, plan: dict) -> list[dict]:
        objetivos = plan["objetivos"]

        def validar(d: dict) -> list[str]:
            errores = []
            if len(d.get("gancho", [])) < 1:
                errores.append("'gancho' necesita al menos una narración.")
            if len(d.get("objetivos", [])) != len(objetivos):
                errores.append(f"'objetivos' debe tener exactamente {len(objetivos)} elementos.")
            return errores

        esquema = P.con_cantidad(P.ESQUEMA_INTRO, "objetivos", len(objetivos))
        r = self.pedir(P.intro(plan["titulo"], plan["intro"], objetivos), esquema, validar, "apertura")
        antetitulo, _, titulo = plan["titulo"].partition(" - ")
        if not titulo:
            antetitulo, titulo = "", plan["titulo"]
        escenas = [{"tipo": "portada", "antetitulo": antetitulo, "titulo": titulo, "icono": r.get("icono") or None,
                    "narracion": r["gancho"][:1]}]
        if len(r["gancho"]) > 1:
            escenas.append({"tipo": "idea", "bloques": [{"texto": " ".join(r["gancho"][1:]),
                                                         "pantalla": r.get("pantalla_gancho") or None}]})
        if objetivos:
            escenas.append({"tipo": "lista", "estilo": "check", "titulo": "Lo que vas a aprender",
                            "items": [{"texto": o["texto"], "punto": o["punto"] or objetivos[k]}
                                      for k, o in enumerate(r["objetivos"])]})
        return escenas

    def _parte(self, numero: int, parte: dict, avanzar) -> list[dict]:
        nombres = [p["titulo"] for p in parte["pasos"]]
        r = self.pedir(P.parte(parte["titulo"], parte["parrafos"], nombres), P.ESQUEMA_PARTE,
                       lambda d: [] if d.get("narracion") else ["'narracion' no puede estar vacía."], "parte")
        escenas = [{"tipo": "portada", "antetitulo": f"Parte {numero}", "titulo": parte["titulo"],
                    "icono": r.get("icono") or None, "narracion": r["narracion"][:2]}]
        avanzar(f"parte {numero}")
        por_paso, resumenes = [], []
        for paso in parte["pasos"]:
            por_paso.append(self._paso(paso))
            primero = next(iter(_parrafos(paso["bloques"])), "")
            resumenes.append((paso["titulo"], primero[:160]))
            avanzar(paso["titulo"])
        visuales = self._visuales(parte["titulo"], resumenes) if resumenes else {}
        avanzar(f"animaciones de la parte {numero}")
        for k, lista in enumerate(por_paso):
            escenas += lista + visuales.get(k, [])
        return escenas

    # Cada paso de la guía
    def _paso(self, paso: dict) -> list[dict]:
        bloques, titulo = paso["bloques"], paso["titulo"]
        parrafos = _parrafos(bloques)
        escenas = []
        for tabla in [b for b in bloques if b["tipo"] == "tabla"]:
            escenas.append(self._tabla(titulo, parrafos, tabla))
        codigos = [b for b in bloques if b["tipo"] == "codigo"]
        if codigos:
            escenas += self._terminal(titulo, parrafos, codigos)
        listas = [b for b in bloques if b["tipo"] == "lista"]
        if listas and not codigos:
            escenas.append(self._pasos(titulo, parrafos, listas[0]["items"]))
        if not escenas and parrafos:
            escenas.append(self._ideas(titulo, parrafos))
        return escenas

    def _tabla(self, titulo: str, parrafos: list[str], tabla: dict) -> dict:
        filas = tabla["filas"]

        def validar(d: dict) -> list[str]:
            fuera = [i for b in d.get("bloques", []) for i in b.get("resaltar", []) if not 0 <= i < len(filas)]
            return [f"Filas fuera de rango: {fuera}. Van de 0 a {len(filas) - 1}."] if fuera else (
                [] if d.get("bloques") else ["'bloques' no puede estar vacío."])

        r = self.pedir(P.tabla(titulo, parrafos, tabla["encabezados"], filas), P.ESQUEMA_TABLA, validar, "tabla")
        return {"tipo": "tabla", "titulo": titulo, "encabezados": tabla["encabezados"], "filas": filas,
                "bloques": [{"texto": b["texto"], "resaltar": b.get("resaltar") or None} for b in r["bloques"][:3]]}

    def _terminal(self, titulo: str, parrafos: list[str], codigos: list[dict]) -> list[dict]:
        shell = "powershell" if any(c["lenguaje"].lower() in ("powershell", "ps1", "pwsh") for c in codigos) else "bash"
        comandos = [c for b in codigos for c in ingesta.comandos_de(b)]

        def validar(d: dict) -> list[str]:
            errores = []
            if len(d.get("comandos", [])) != len(comandos):
                return [f"'comandos' debe tener exactamente {len(comandos)} elementos, uno por comando."]
            for k, (c, cmd) in enumerate(zip(d["comandos"], comandos)):
                if not c.get("texto"):
                    errores.append(f"El comando [{k}] no tiene 'texto'.")
                for p in c.get("partes", []):
                    if p.get("fragmento") and p["fragmento"] not in cmd:
                        errores.append(f"En el comando [{k}], el fragmento {p['fragmento']!r} no aparece tal cual en: {cmd}")
            return errores

        esquema = P.con_cantidad(P.ESQUEMA_TERMINAL, "comandos", len(comandos))
        r = self.pedir(P.terminal(titulo, parrafos, comandos, shell), esquema, validar, "terminal")
        entradas = []
        for cmd, c in zip(comandos, r["comandos"]):
            partes = [p for p in c.get("partes", []) if p.get("fragmento") and p["fragmento"] in cmd and p.get("texto")]
            entrada = {"comando": cmd, "texto": c["texto"], "partes": partes[:3]}
            salida, real = self._salida(cmd, c.get("salida") or [])
            if salida:
                entrada.update(salida=salida, salida_real=real, texto_salida=c.get("texto_salida") or None)
            entradas.append(entrada)
        escenas = [{"tipo": "terminal", "shell": shell, "nota": titulo, "intro": r.get("intro") or None,
                    "comandos": entradas}]
        aviso = r.get("aviso") or {}
        if aviso.get("sello") in SELLOS and aviso.get("texto"):
            escenas.append({"tipo": "idea", "bloques": [{"texto": aviso["texto"], "sello": aviso["sello"],
                                                         "pantalla": aviso.get("pantalla") or None}]})
        return escenas

    def _salida(self, comando: str, ejemplo: list[str]) -> tuple[list[str], bool]:
        """Salida real si el comando se puede verificar en este equipo; si no, la de ejemplo del modelo."""
        if self.capturar_reales and capturas.ejecutable(comando)[0]:
            if comando not in self.capturas:
                self.capturas[comando] = capturas.capturar(comando)
            res = self.capturas[comando]
            if res["ejecutado"] and res["codigo"] == 0 and res["salida"]:
                return capturas.recortar(res["salida"], 10), True
        return [l for l in ejemplo if l.strip()][:8], False

    def _pasos(self, titulo: str, parrafos: list[str], items: list[str]) -> dict:
        def validar(d: dict) -> list[str]:
            return [] if len(d.get("items", [])) == len(items) else [f"'items' debe tener {len(items)} elementos."]

        r = self.pedir(P.pasos(titulo, parrafos, items), P.con_cantidad(P.ESQUEMA_PASOS, "items", len(items)), validar, "pasos")
        return {"tipo": "lista", "estilo": "check", "titulo": titulo, "intro": r.get("intro") or None,
                "items": [{"texto": i["texto"], "punto": i["punto"] or items[k][:60]} for k, i in enumerate(r["items"])]}

    def _ideas(self, titulo: str, parrafos: list[str]) -> dict:
        r = self.pedir(P.ideas(titulo, parrafos), P.ESQUEMA_IDEA,
                       lambda d: [] if d.get("bloques") else ["'bloques' no puede estar vacío."], "ideas")
        bloques = []
        for b in r["bloques"][:3]:
            bloque = {"texto": b["texto"], "pantalla": b.get("pantalla") or None, "icono": b.get("icono") or None}
            if b.get("sello", "").upper() in SELLOS:
                bloque["sello"] = b["sello"].upper()
            bloques.append(bloque)
        return {"tipo": "idea", "bloques": bloques}

    # Animaciones del concepto
    def _visuales(self, titulo: str, resumenes: list[tuple[str, str]]) -> dict[int, list[dict]]:
        def validar(d: dict) -> list[str]:
            errores = []
            for k, v in enumerate(d.get("visuales", [])):
                escena = visual_a_escena(v)
                if not 0 <= v.get("despues_de", -1) < len(resumenes):
                    errores.append(f"Animación {k}: 'despues_de' debe ir de 0 a {len(resumenes) - 1}.")
                errores += [f"Animación {k}: {e}" for e in g.validar({"fragmentos": {}, "escenas": [escena]}, self.proyecto)]
            return errores

        try:
            r = self.pedir(P.visuales(titulo, resumenes), P.ESQUEMA_VISUALES, validar, "visuales")
        except Exception as error:  # una animación que no sale no debe tumbar el video entero
            self.progreso(f"sin animación para «{titulo}» ({error})", -1)
            return {}
        salida: dict[int, list[dict]] = {}
        for v in r.get("visuales", [])[:2]:
            salida.setdefault(v["despues_de"], []).append(visual_a_escena(v))
        return salida

    def _cierre(self, plan: dict) -> dict:
        cubierto = plan["cubierto"] or plan["objetivos"]
        r = self.pedir(P.cierre(plan["titulo"], cubierto), P.con_cantidad(P.ESQUEMA_CIERRE, "puntos", len(cubierto)),
                       lambda d: [] if d.get("texto") else ["'texto' no puede estar vacío."], "cierre")
        puntos = r.get("puntos") or []
        if len(puntos) != len(cubierto):
            puntos = [c[:40] for c in cubierto]
        reto = " ".join(t for t in (r.get("reto"), r.get("despedida")) if t)
        escena = {"tipo": "cierre", "bloques": [{"texto": r["texto"]}], "reto": reto or None}
        if puntos:
            escena["resumen"] = puntos
        return escena

    def _guardar_capturas(self) -> None:
        if self.capturas:
            (self.proyecto / "capturas.json").write_text(
                json.dumps(list(self.capturas.values()), ensure_ascii=False, indent=2), encoding="utf-8")


def visual_a_escena(v: dict) -> dict:
    """Pasa una animación propuesta por el modelo al formato de escena del guion."""
    tipo = v.get("tipo")
    if tipo == "diagrama":
        cajas = {c["id"]: {"titulo": c["titulo"], "detalle": c.get("detalle") or None, "icono": c.get("icono") or None}
                 for c in v.get("cajas", []) if c.get("id")}
        bloques = []
        for p in v.get("pasos", []):
            b = {"texto": p.get("texto", "")}
            if p.get("resaltar"):
                b["resaltar"] = p["resaltar"]
            if p.get("flujo_de") and p.get("flujo_a"):
                b["flujo"] = [p["flujo_de"], p["flujo_a"]]
                if p.get("viajero"):
                    b["viajero"] = p["viajero"]
            bloques.append(b)
        return {"tipo": "diagrama", "titulo": v.get("titulo") or None, "cajas": cajas,
                "flechas": [[f["de"], f["a"], f.get("etiqueta") or ""] for f in v.get("flechas", [])],
                "bloques": bloques}
    if tipo == "capas":
        return {"tipo": "capas", "titulo": v.get("titulo") or None,
                "capas": [{"titulo": c["titulo"], "detalle": c.get("detalle") or None, "icono": c.get("icono") or None}
                          for c in v.get("capas", [])],
                "bloques": [{"texto": p.get("texto", ""), "mostrar": p.get("mostrar") or None} for p in v.get("pasos", [])]}
    destino = v.get("destino") or {}
    return {"tipo": "piezas", "titulo": v.get("titulo") or None,
            "items": [{"titulo": i["titulo"], "detalle": i.get("detalle") or None, "icono": i.get("icono") or None}
                      for i in v.get("items", [])],
            "destino": {"titulo": destino["titulo"], "icono": destino.get("icono") or None} if destino.get("titulo") else None,
            "bloques": [{"texto": p.get("texto", ""), "mostrar": p.get("mostrar") or None,
                         "instalar": bool(p.get("instalar"))} for p in v.get("pasos", [])]}
