"""Escenas que salen de la traza: código línea por línea con su estado, y grafo, arreglo o pila animados
con lo que pasó de verdad al ejecutar el código."""

from __future__ import annotations

import json
from pathlib import Path

from manim import DOWN, LEFT, ORIGIN, RIGHT, UL, UP, UR, FadeIn, FadeOut, VGroup

from . import estilo as e
from .componentes import Arreglo, FilaCajas, Grafo, PanelCodigo, TablaEstado, TarjetaSeccion, cifra, nota
from .eventos import (
    bloques_grafo, estado_final, eventos_arreglo, eventos_lista, formatear, narrar_bloque_grafo,
    narrar_evento_arreglo, narrar_evento_lista,
)


def _encajar(objeto, ancho: float, alto: float):
    factor = min(1.0, ancho / max(objeto.width, 1e-6), alto / max(objeto.height, 1e-6))
    return objeto.scale(factor) if factor < 1 else objeto


def _texto_o(lista: list, k: int, respaldo: str) -> str:
    return lista[k] if k < len(lista) and isinstance(lista[k], str) and lista[k].strip() else respaldo


class EscenasTraza:
    """Mezcla para VideoGuion; usa self.base, self.guion, self.narrar y self.tocar."""

    def _traza(self, fid: str) -> dict:
        if not hasattr(self, "_trazas"):
            self._trazas = {}
        if fid not in self._trazas:
            ruta = self.base / self.guion["fragmentos"][fid]["traza"]
            self._trazas[fid] = json.loads(Path(ruta).read_text(encoding="utf-8"))
        return self._trazas[fid]

    def _tarjeta(self, titulo: str, antetitulo: str, narracion: str | None) -> None:
        tarjeta = TarjetaSeccion(titulo, antetitulo)
        if narracion:
            with self.narrar(narracion) as n:
                self.tocar(tarjeta.entrar(), run_time=min(1.4, n.resto()))
        else:
            self.tocar(tarjeta.entrar(), run_time=1.2)
            self.silencio(1.0)
        self.tocar(tarjeta.salir(), run_time=0.6)

    # Código línea por línea
    def _escena_codigo(self, esc: dict) -> None:
        fid = esc["fragmento"]
        frag = self.guion["fragmentos"][fid]
        if esc.get("titulo"):
            self._tarjeta(esc["titulo"], esc.get("antetitulo", "El código"), esc.get("intro"))
        panel = PanelCodigo.desde_archivo(self.base / frag["archivo"], frag.get("desde", 1), frag.get("hasta"),
                                          lenguaje=frag.get("lenguaje"))
        traza = self._traza(fid) if frag.get("traza") else None
        variables = [v for v in esc.get("estado", []) if v] if traza else []
        columnas = esc.get("etiquetas_columnas") or []
        pasos, final = self._valores_codigo(esc, traza, variables, columnas) if variables else ([], {})
        tabla = None
        if variables:
            largos = [len(s) for d in pasos + [final] if d for s in d.values()]
            filas = (["nodo"] if columnas else []) + variables
            tabla = TablaEstado(filas, reserva=max(largos + [4 * len(columnas), 1]))
            _encajar(panel, 7.6, 6.8).move_to(ORIGIN).to_edge(LEFT, buff=0.5)
            libre = 14.22 - 0.5 - panel.width - 0.5 - 0.5
            _encajar(tabla, libre, 6.0).next_to(panel, RIGHT, buff=0.5).align_to(panel, UP).shift(DOWN * 0.3)
        else:
            _encajar(panel, 12.6, 6.8).move_to(ORIGIN)
        self.tocar(panel.mostrar(), run_time=1.2)
        if tabla:
            self.tocar(FadeIn(tabla.encabezado), *[FadeIn(t) for t in tabla.etiquetas.values()], run_time=0.6)
            if columnas:
                self.tocar(tabla.actualizar({"nodo": "".join(c.ljust(4) for c in columnas).rstrip()}, resaltar=False),
                           run_time=0.4)
        for k, item in enumerate(esc["lineas"]):
            a, b = int(item["desde"]), int(item.get("hasta", item["desde"]))
            anims = [panel.resaltar(a, b)]
            if tabla and pasos[k]:
                anims.append(tabla.actualizar(pasos[k]))
            with self.narrar(item["texto"]) as n:
                self.tocar(*anims, run_time=min(0.8, n.resto()))
        if esc.get("resultado"):
            anims = [panel.quitar_resaltado()]
            if tabla and final:
                anims.append(tabla.actualizar(final))
            with self.narrar(esc["resultado"]) as n:
                self.tocar(*anims, run_time=min(1.0, n.resto()))

    def _valores_codigo(self, esc: dict, traza: dict, variables: list[str], columnas: list[str]):
        """Textos de la tabla para cada grupo de líneas y para el final, ya recortados."""
        como_nodo = set(esc.get("variables_nodo", []))
        ancho = 4 if columnas else None
        usar_original = any("linea_original" in p for p in traza["pasos"])

        def fmt(estado: dict) -> dict:
            return {v: _recortar(formatear(estado[v], v in como_nodo, ancho=ancho)) if v in estado else ""
                    for v in variables}

        pasos, ultimo = [], 0
        for item in esc["lineas"]:
            b = int(item.get("hasta", item["desde"]))
            hallado = self._estado_en(traza, b, ultimo, usar_original) or self._estado_en(traza, b, 0, usar_original)
            if hallado:
                ultimo, estado = hallado
                pasos.append(fmt(estado))
            else:
                pasos.append(None)
        final = estado_final(traza)
        return pasos, {k: v for k, v in fmt(final).items() if v}

    @staticmethod
    def _estado_en(traza: dict, linea: int, desde: int, usar_original: bool):
        clave = "linea_original" if usar_original else "linea"
        for p in traza["pasos"]:
            if p["paso"] >= desde and p["evento"] == "linea" and p.get(clave) == linea:
                return p["paso"], {**p["vars"], **p.get("cambios", {})}
        return None

    # Grafo animado desde la ejecución
    def _escena_grafo_traza(self, esc: dict) -> None:
        traza = self._traza(esc["fragmento"])
        datos = bloques_grafo(traza, esc["argumento"], esc.get("valores"), esc.get("actual"))
        gr, bloques = datos["grafo"], datos["bloques"]
        inicio = next((b["nodo"] for b in bloques if b["nodo"]), None)
        grafo = Grafo(gr["nodos"], gr["aristas"], dirigido=gr["dirigido"], inicio=inicio)
        _encajar(grafo, 11.5, 5.6).move_to(DOWN * 0.3)
        textos = esc.get("bloques") or []
        cabecera = nota(esc["nota"], 34).to_corner(UL, buff=e.MARGEN) if esc.get("nota") else None
        with self.narrar(_texto_o(textos, 0, esc.get("intro") or narrar_bloque_grafo(bloques[0]))) as n:
            self.tocar(grafo.aparecer(), *( [FadeIn(cabecera)] if cabecera else []), run_time=min(2.0, n.resto()))
            if esc.get("valores"):
                iniciales = dict(bloques[0].get("iniciales", {}))
                for c in bloques[0]["cambios"]:
                    iniciales[c["nodo"]] = c["despues"]
                self.tocar(*[grafo.valor(nodo, v) for nodo, v in iniciales.items()], run_time=min(1.0, n.resto()))
        for k, bloque in enumerate(bloques[1:], 1):
            respaldo = narrar_bloque_grafo(bloque) if esc.get("valores") else f"Visitamos el nodo {bloque['nodo']}."
            with self.narrar(_texto_o(textos, k, respaldo)) as n:
                self.tocar(grafo.cerrar(bloque["nodo"]), run_time=min(0.7, n.resto()))
                pasos = max(len(bloque["cambios"]), 1)
                for c in bloque["cambios"]:
                    tiempo = min(0.9, max(n.restante() / pasos, 0.3))
                    try:
                        arista = [grafo.resaltar_arista(bloque["nodo"], c["nodo"])]
                    except KeyError:
                        arista = []
                    self.tocar(*arista, grafo.valor(c["nodo"], c["despues"]), run_time=tiempo)
                    if arista:
                        self.tocar(grafo.atenuar_arista(bloque["nodo"], c["nodo"]), run_time=0.25)
        self._cerrar_camino(esc, traza, grafo, gr, datos)

    def _cerrar_camino(self, esc, traza, grafo, gr, datos) -> None:
        cierre = esc.get("cierre")
        variable, destino = esc.get("previo"), esc.get("destino")
        camino = []
        if variable and destino:
            previo = estado_final(traza).get(variable)
            nodo_a_clave = {v: k for k, v in gr["clave_a_nodo"].items()}
            actual, vistos = nodo_a_clave.get(str(destino)), set()
            while actual is not None and actual not in vistos:
                vistos.add(actual)
                camino.append(gr["clave_a_nodo"][actual])
                siguiente = previo.get(actual) if isinstance(previo, dict) else (
                    previo[int(actual)] if isinstance(previo, list) and actual.isdigit() and int(actual) < len(previo) else None)
                actual = None if siguiente in (None, -1, "-1") else str(siguiente)
            camino.reverse()
        if not cierre and len(camino) < 2:
            return
        total = datos["finales"].get(str(destino)) if destino else None
        if cierre is None:
            cierre = f"La ruta es {', '.join(camino)}" + (f", con un total de {e.valor_corto(total)}." if total is not None else ".")
        with self.narrar(cierre) as n:
            anims = [grafo.camino(camino)] if len(camino) >= 2 else []
            if total is not None and len(camino) >= 2:
                etiqueta = cifra(f"{destino} = {e.valor_corto(total)}", e.ROJO, 56).to_corner(UR, buff=e.MARGEN)
                anims.append(FadeIn(etiqueta, scale=1.3))
            self.tocar(*anims, run_time=min(2.0, n.resto()))

    # Arreglo animado desde la ejecución
    def _escena_arreglo_traza(self, esc: dict) -> None:
        datos = eventos_arreglo(self._traza(esc["fragmento"]), esc["variable"], esc.get("punteros", []))
        arreglo = _encajar(Arreglo(datos["inicial"], etiqueta=esc.get("etiqueta")), 12.0, 3.0).move_to(UP * 0.4)
        cabecera = nota(esc["nota"], 34).to_corner(UL, buff=e.MARGEN) if esc.get("nota") else None
        with self.narrar(esc.get("intro") or "Este es el arreglo con el que arranca el código.") as n:
            self.tocar(FadeIn(arreglo, shift=UP * 0.2), *([FadeIn(cabecera)] if cabecera else []),
                       run_time=min(1.2, n.resto()))
        textos, valores = esc.get("bloques") or [], list(datos["inicial"])
        for k, grupo in enumerate(_agrupar(datos["eventos"])):
            principal = grupo[-1]
            respaldo = narrar_evento_arreglo(principal, valores)
            with self.narrar(_texto_o(textos, k, respaldo)) as n:
                for ev in grupo:
                    tiempo = min(0.8, max(n.restante() / len(grupo), 0.3))
                    if ev["tipo"] == "puntero":
                        self.tocar(arreglo.puntero(ev["nombre"], ev["i"]), run_time=tiempo)
                    elif ev["tipo"] == "intercambio":
                        valores[ev["i"]], valores[ev["j"]] = valores[ev["j"]], valores[ev["i"]]
                        self.tocar(arreglo.intercambiar(ev["i"], ev["j"]), run_time=tiempo)
                    elif ev["tipo"] == "poner":
                        valores[ev["i"]] = ev["valor"]
                        self.tocar(arreglo.poner(ev["i"], ev["valor"]), run_time=tiempo)
                    else:
                        nuevo = _encajar(Arreglo(ev["valores"]), 12.0, 3.0).move_to(arreglo)
                        self.tocar(FadeOut(arreglo), FadeIn(nuevo), run_time=tiempo)
                        arreglo, valores = nuevo, list(ev["valores"])
        with self.narrar(esc.get("cierre") or "Y así queda el arreglo al terminar.") as n:
            self.tocar(arreglo.marcar_listo(*range(len(valores))), run_time=min(1.0, n.resto()))

    # Pila o cola animada desde la ejecución
    def _escena_lista_traza(self, esc: dict) -> None:
        datos = eventos_lista(self._traza(esc["fragmento"]), esc["variable"])
        es_pila = esc.get("estilo", "pila") == "pila"
        como_nodo = bool(esc.get("como_nodo"))
        fmt = lambda v: formatear(v, como_nodo)  # noqa: E731
        fila = FilaCajas(esc.get("etiqueta") or ("pila" if es_pila else "cola"), [fmt(v) for v in datos["inicial"]],
                         vertical=es_pila)
        fila.move_to(DOWN * 2.2 if es_pila else ORIGIN)
        if not es_pila:
            fila.to_edge(LEFT, buff=1.0)
        nombre = "la pila" if es_pila else "la cola"
        with self.narrar(esc.get("intro") or f"Miremos {nombre} mientras corre el código.") as n:
            self.tocar(FadeIn(fila), run_time=min(1.0, n.resto()))
        textos = esc.get("bloques") or []
        for k, ev in enumerate(datos["eventos"]):
            with self.narrar(_texto_o(textos, k, narrar_evento_lista(ev, nombre))) as n:
                if ev["tipo"] == "meter":
                    self.tocar(fila.meter(fmt(ev["valor"])), run_time=min(0.8, n.resto()))
                elif ev["tipo"] == "sacar":
                    self.tocar(fila.sacar(ev["indice"]), run_time=min(0.8, n.resto()))
                else:
                    self.tocar(fila.reemplazar([fmt(v) for v in ev["valores"]]), run_time=min(0.9, n.resto()))
        if esc.get("cierre"):
            with self.narrar(esc["cierre"]):
                pass


def _recortar(contenido: str, maximo: int = 30) -> str:
    return contenido if len(contenido) <= maximo else contenido[: maximo - 1] + "…"


def _agrupar(eventos: list[dict]) -> list[list[dict]]:
    """Junta los movimientos de punteros con el cambio que los sigue, para narrarlos juntos."""
    grupos, actual = [], []
    for ev in eventos:
        actual.append(ev)
        if ev["tipo"] != "puntero":
            grupos.append(actual)
            actual = []
    if actual:
        grupos.append(actual)
    return grupos
