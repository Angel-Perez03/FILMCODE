"""Motor: convierte un guion.json en un video de Manim, escena por escena.

Lee el guion de VIDEOCODIGO_GUION_ENTRADA y resuelve rutas desde VIDEOCODIGO_PROYECTO.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from manim import DOWN, LEFT, ORIGIN, UL, UP, AnimationGroup, FadeIn, FadeOut, VGroup, config

from . import estilo as e
from . import guion as g
from .componentes import (
    Arbol, Arreglo, Diagrama, FilaCajas, Grafo, ListaArchivos, ListaPuntos, Personaje, Sello, TarjetaSeccion, cifra,
    frase, nota, texto,
)
from .componentes.iconos import icono
from .componentes.movimiento import FraseCinetica, ListaCheck
from .motor_mov import EscenasMovimiento
from .motor_traza import EscenasTraza, _encajar
from .narracion import EscenaNarrada


def _vacia(anim) -> bool:
    return anim is None or (isinstance(anim, AnimationGroup) and not anim.animations)


class VideoGuion(EscenasMovimiento, EscenasTraza, EscenaNarrada):
    """Escena única que recorre todas las escenas del guion."""

    def construct(self) -> None:
        ruta = Path(os.environ.get("VIDEOCODIGO_GUION_ENTRADA", "guion.json")).resolve()
        self.base = Path(os.environ.get("VIDEOCODIGO_PROYECTO", ruta.parent))
        self.guion = g.cargar(ruta)
        errores = g.validar(self.guion, self.base)
        if errores:
            raise ValueError("Guion inválido:\n- " + "\n- ".join(errores))
        for escena in self.guion["escenas"]:
            getattr(self, f"_escena_{escena['tipo']}")(escena)
            self._limpiar()
        self.silencio(0.6)

    # Utilidades
    def tocar(self, *anims, run_time: float | None = None) -> None:
        """Reproduce las animaciones que no estén vacías; si no queda ninguna, no hace nada."""
        validas = [a for a in anims if not _vacia(a)]
        if validas:
            self.play(*validas, **({"run_time": run_time} if run_time else {}))

    def _limpiar(self, run_time: float = 0.6) -> None:
        """Saca todo de pantalla hacia la izquierda y devuelve la cámara a su lugar."""
        visibles = [m for m in self.mobjects if m is not self.camera.frame]
        anims = [FadeOut(m, shift=LEFT * 0.5) for m in visibles]
        marco = self.camera.frame
        if abs(marco.width - config.frame_width) > 1e-3 or np.linalg.norm(marco.get_center()) > 1e-3:
            anims.append(self._soltar())
        if anims:
            self.play(*anims, run_time=run_time)

    def _acciones(self, bloque: dict, ejecutar) -> None:
        """Narra el bloque y reparte sus acciones a lo largo del audio."""
        acciones = bloque.get("acciones", []) or []
        with self.narrar(bloque["texto"]) as n:
            for accion in acciones:
                tiempo = min(1.0, max(n.restante() / max(len(acciones), 1), 0.3))
                self.tocar(ejecutar(accion), run_time=tiempo)

    # Escenas de texto e ideas
    def _escena_portada(self, esc: dict) -> None:
        tarjeta = TarjetaSeccion(esc["titulo"], esc.get("antetitulo", ""))
        simbolo = icono(esc["icono"], e.AZUL, 1.7) if esc.get("icono") else None
        if simbolo:
            VGroup(simbolo, tarjeta).arrange(DOWN, buff=0.7).move_to(ORIGIN)
        entrada = [tarjeta.entrar()] + ([FadeIn(simbolo, scale=0.5, shift=UP * 0.3)] if simbolo else [])
        bloques = esc.get("narracion") or []
        if not bloques:
            self.tocar(*entrada, run_time=1.4)
            self.silencio(1.2)
        for i, contenido in enumerate(bloques):
            with self.narrar(contenido) as n:
                if i == 0:
                    self.tocar(*entrada, run_time=min(1.5, n.resto()))

    def _escena_idea(self, esc: dict) -> None:
        en_pantalla = VGroup()
        for bloque in esc["bloques"]:
            nuevos, centro, cinetica = VGroup(), VGroup(), None
            if bloque.get("personaje"):
                p = bloque["personaje"]
                nuevos.add(Personaje(p.get("nombre", ""), p.get("detalle", "")).esquina())
            if bloque.get("icono"):
                centro.add(icono(bloque["icono"], e.AZUL, 1.5))
            if bloque.get("sello"):
                centro.add(Sello(str(bloque["sello"])))
            if bloque.get("cifra"):
                centro.add(cifra(str(bloque["cifra"])))
            if bloque.get("pantalla"):
                cinetica = FraseCinetica(bloque["pantalla"])
                centro.add(cinetica)
            if bloque.get("nota"):
                centro.add(nota(bloque["nota"]))
            if len(centro):
                centro.arrange(DOWN, buff=0.45).move_to(ORIGIN)
                _encajar(centro, e.ANCHO_UTIL, e.ALTO_UTIL - 1.2)
                nuevos.add(centro)
            with self.narrar(bloque["texto"]) as n:
                if len(nuevos):
                    salen = [FadeOut(m, shift=UP * 0.2) for m in en_pantalla]
                    fijos = [m for m in nuevos if m is not centro] + [m for m in centro if m is not cinetica]
                    self.tocar(*salen, *[FadeIn(m, shift=UP * 0.15, scale=0.92) for m in fijos],
                               run_time=min(0.8, n.resto()))
                    if cinetica is not None:
                        lectura = min(max(0.3 * len(cinetica.palabras), 0.8), max(n.restante() * 0.8, 0.5))
                        self.tocar(cinetica.revelar(), run_time=lectura)
            if len(nuevos):
                en_pantalla = nuevos

    def _escena_lista(self, esc: dict) -> None:
        items = esc["items"]
        textos_items = [i.get("punto") or i["texto"][:70] for i in items]
        con_check = esc.get("estilo") == "check"
        lista = ListaCheck(textos_items) if con_check else ListaPuntos(textos_items)
        titulo = texto(esc["titulo"], 44, e.TEXTO_SUAVE) if esc.get("titulo") else None
        grupo = VGroup(*([titulo] if titulo else []), lista).arrange(DOWN, buff=0.6, aligned_edge=LEFT)
        _encajar(grupo, e.ANCHO_UTIL, e.ALTO_UTIL).move_to(ORIGIN)
        if titulo and esc.get("intro"):
            with self.narrar(esc["intro"]) as n:
                self.tocar(FadeIn(titulo, shift=UP * 0.15), run_time=min(0.8, n.resto()))
        elif titulo:
            self.tocar(FadeIn(titulo, shift=UP * 0.15), run_time=0.6)
        for k, item in enumerate(items):
            with self.narrar(item["texto"]) as n:
                self.tocar(lista.mostrar(k), run_time=min(0.6, n.resto()))
                if con_check:
                    self.tocar(lista.marcar(k), run_time=min(0.5, n.resto()))

    def _escena_archivos(self, esc: dict) -> None:
        arbol = _encajar(ListaArchivos(esc["rutas"]), 9.0, e.ALTO_UTIL).move_to(LEFT * 1.5)
        for k, bloque in enumerate(esc["bloques"]):
            with self.narrar(bloque["texto"]) as n:
                anims = [FadeIn(arbol, shift=UP * 0.1)] if k == 0 else []
                if bloque.get("resaltar"):
                    anims.append(arbol.resaltar(bloque["resaltar"]))
                self.tocar(*anims, run_time=min(1.0, n.resto()))

    def _escena_diagrama(self, esc: dict) -> None:
        flechas = [tuple(f) for f in esc.get("flechas", [])]
        cajas = {k: (v if isinstance(v, (str, dict)) else tuple(v)) for k, v in esc["cajas"].items()}
        titulo = self._titulo_escena(esc)
        diagrama = _encajar(Diagrama(cajas, flechas, ancho_caja=2.7), e.ANCHO_UTIL, e.ALTO_UTIL - (1.4 if titulo else 0.6))
        diagrama.move_to(DOWN * (0.45 if titulo else 0.2))
        for k, bloque in enumerate(esc["bloques"]):
            with self.narrar(bloque["texto"]) as n:
                if k == 0:
                    self.tocar(diagrama.aparecer(), *([FadeIn(titulo)] if titulo else []), run_time=min(2.0, n.resto()))
                if bloque.get("resaltar"):
                    self.tocar(diagrama.enfocar(bloque["resaltar"]), run_time=min(0.6, n.resto()))
                if bloque.get("flujo"):
                    origen, destino = bloque["flujo"][0], bloque["flujo"][1]
                    self.tocar(diagrama.flujo(origen, destino, viajero=bloque.get("viajero")),
                               run_time=min(1.6, max(n.restante(), 0.6)))

    def _escena_cierre(self, esc: dict) -> None:
        if esc.get("resumen"):
            lista = _encajar(ListaCheck(esc["resumen"]), e.ANCHO_UTIL, e.ALTO_UTIL).move_to(ORIGIN)
            primero, *resto = esc["bloques"]
            with self.narrar(primero["texto"]) as n:
                self.tocar(*[lista.mostrar(k) for k in range(len(lista.filas))], run_time=min(1.0, n.resto()))
                for k in range(len(lista.filas)):
                    self.tocar(lista.marcar(k), run_time=min(0.45, max(n.restante() / len(lista.filas), 0.25)))
            bloques = resto
            if bloques:
                self._limpiar()
        else:
            bloques = esc["bloques"]
        if bloques:
            self._escena_idea({"bloques": bloques})
        if esc.get("reto"):
            self._limpiar()
            reto = VGroup(icono("cohete", e.AZUL, 1.2), texto("Te dejo un reto", 30, e.AZUL), frase(esc["reto"], 38))
            reto.arrange(DOWN, buff=0.45)
            _encajar(reto, e.ANCHO_UTIL, e.ALTO_UTIL)
            with self.narrar(esc["reto"]) as n:
                self.tocar(FadeIn(reto, shift=UP * 0.15), run_time=min(1.0, n.resto()))

    # Escenas con acciones dictadas por el guion (sin traza)
    def _escena_grafo(self, esc: dict) -> None:
        aristas = [tuple(a) for a in esc["aristas"]]
        grafo = _encajar(Grafo([str(n) for n in esc["nodos"]], aristas, dirigido=bool(esc.get("dirigido")),
                               inicio=esc.get("inicio")), 11.5, 5.6).move_to(DOWN * 0.3)
        if esc.get("nota"):
            self.add(nota(esc["nota"], 34).to_corner(UL, buff=e.MARGEN))
        self.tocar(grafo.aparecer(), run_time=1.5)

        def ejecutar(a: dict):
            nombre = a["accion"]
            if nombre == "valor":
                return grafo.valor(str(a["nodo"]), a["valor"])
            if nombre in ("cerrar", "marcar", "abrir"):
                return getattr(grafo, nombre)(str(a["nodo"]))
            if nombre == "camino":
                return grafo.camino([str(x) for x in a["nodos"]])
            if nombre == "peso":
                return grafo.cambiar_peso(str(a["de"]), str(a["a"]), a["valor"])
            return getattr(grafo, nombre)(str(a["de"]), str(a["a"]))

        for bloque in esc["bloques"]:
            self._acciones(bloque, ejecutar)

    def _escena_arreglo(self, esc: dict) -> None:
        arreglo = _encajar(Arreglo(esc["valores"], etiqueta=esc.get("etiqueta")), 12.0, 3.0).move_to(UP * 0.4)
        self.tocar(FadeIn(arreglo, shift=UP * 0.2), run_time=0.8)

        def ejecutar(a: dict):
            nombre = a["accion"]
            if nombre in ("intercambiar", "comparar"):
                return getattr(arreglo, nombre)(a["i"], a["j"])
            if nombre == "poner":
                return arreglo.poner(a["i"], a["valor"])
            if nombre == "puntero":
                return arreglo.puntero(str(a["nombre"]), a["i"])
            if nombre == "resaltar":
                return arreglo.resaltar(*a["indices"])
            if nombre == "listo":
                return arreglo.marcar_listo(*a["indices"])
            return arreglo.normal()

        for bloque in esc["bloques"]:
            self._acciones(bloque, ejecutar)

    def _escena_arbol(self, esc: dict) -> None:
        arbol = _encajar(Arbol(_tupla(esc["raiz"])), 12.0, 5.8).move_to(DOWN * 0.2)
        self.tocar(arbol.aparecer(), run_time=1.5)

        def ejecutar(a: dict):
            if a["accion"] == "resaltar":
                return arbol.resaltar(str(a["nodo"]))
            if a["accion"] == "camino":
                return arbol.camino([str(x) for x in a["nodos"]])
            return arbol.normal()

        for bloque in esc["bloques"]:
            self._acciones(bloque, ejecutar)

    def _escena_pila(self, esc: dict) -> None:
        es_pila = esc.get("estilo", "pila") == "pila"
        fila = FilaCajas(esc.get("etiqueta") or ("pila" if es_pila else "cola"),
                         [str(v) for v in esc.get("valores", [])], vertical=es_pila)
        fila.move_to(DOWN * 2.2 if es_pila else ORIGIN)
        self.tocar(FadeIn(fila), run_time=0.6)

        def ejecutar(a: dict):
            if a["accion"] == "meter":
                return fila.meter(str(a["valor"]))
            if a["accion"] == "sacar":
                return fila.sacar(int(a.get("indice", -1 if es_pila else 0)))
            if a["accion"] == "tachar":
                return fila.tachar(int(a["indice"]))
            return fila.resaltar(int(a["indice"]))

        for bloque in esc["bloques"]:
            self._acciones(bloque, ejecutar)


def _tupla(nodo):
    """Convierte el árbol del JSON ([valor, [hijos]]) en tuplas para el componente Arbol."""
    if nodo is None or not isinstance(nodo, list):
        return nodo
    if len(nodo) == 2 and isinstance(nodo[1], list):
        return (nodo[0], [_tupla(h) for h in nodo[1]])
    return tuple([nodo[0]] + [_tupla(h) for h in nodo[1:]])
