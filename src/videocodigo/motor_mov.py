"""Escenas con más movimiento: terminal con cámara que se acerca, tablas, pilas de capas y piezas
que se instalan. Mezcla para VideoGuion (usa self.narrar, self.tocar y self.camera)."""

from __future__ import annotations

from manim import DOWN, ORIGIN, UL, UP, FadeIn, Indicate, config

from . import estilo as e
from .componentes import Tabla, Terminal, nota, texto
from .componentes.movimiento import Capas, Piezas, Tarjeta
from .motor_traza import _encajar


def _indices(valor) -> list[int]:
    if valor is None or valor == "":
        return []
    return [int(v) for v in (valor if isinstance(valor, list) else [valor])]


class EscenasMovimiento:
    # Cámara
    def _enfocar(self, objetivo, ancho_relativo: float = 0.8, limite=None):
        """Acerca la cámara a `objetivo`. Con `limite` (la ventana de la terminal), el borde izquierdo del cuadro
        no pasa del borde izquierdo de la ventana: así siempre se ve el inicio de las líneas."""
        ancho = config.frame_width * ancho_relativo
        centro = objetivo.get_center().copy()
        if limite is not None:
            derecha = limite.get_right()[0] + 0.25
            if centro[0] + ancho / 2 > derecha:
                centro[0] = derecha - ancho / 2
            izquierda = limite.get_left()[0] - 0.25
            if centro[0] - ancho / 2 < izquierda:
                centro[0] = izquierda + ancho / 2
        return self.camera.frame.animate.set_width(ancho).move_to(centro)

    def _soltar(self):
        return self.camera.frame.animate.set_width(config.frame_width).move_to(ORIGIN)

    def _titulo_escena(self, esc: dict):
        return texto(esc["titulo"], 40, e.TEXTO_SUAVE).to_edge(UP, buff=0.6) if esc.get("titulo") else None

    # Terminal
    def _escena_terminal(self, esc: dict) -> None:
        terminal = Terminal(esc.get("titulo") or "Ventana de terminal", esc.get("shell", "bash")).move_to(UP * 0.35)
        cabecera = nota(esc["nota"], 30).to_corner(UL, buff=0.45) if esc.get("nota") else None
        entrada = [FadeIn(terminal, shift=UP * 0.15, scale=0.97)] + ([FadeIn(cabecera)] if cabecera else [])
        if esc.get("intro"):
            with self.narrar(esc["intro"]) as n:
                self.tocar(*entrada, run_time=min(0.9, n.resto()))
                if esc.get("nota"):
                    # Mientras se cuenta para qué sirve el paso, se escribe como comentario (la terminal no queda vacía)
                    comentario = f"# {esc['nota']}"
                    self.tocar(terminal.escribir(comentario, color=e.SINTAXIS["comentario"]),
                               run_time=min(max(len(comentario) * 0.03, 0.5), max(n.restante() * 0.6, 0.3)))
        else:
            self.tocar(*entrada, run_time=0.8)
        for cmd in esc["comandos"]:
            self._comando(terminal, cmd)

    def _comando(self, terminal: Terminal, cmd: dict) -> None:
        if cmd.get("limpiar"):
            self.tocar(terminal.limpiar(), run_time=0.4)
        primera = len(terminal.comandos)
        lineas = cmd["comando"].split("\n")
        with self.narrar(cmd["texto"]) as n:
            fin_heredoc = None
            for k, linea in enumerate(lineas):
                prompt = ">" if fin_heredoc is not None else None
                if fin_heredoc is not None and linea.strip() == fin_heredoc:
                    fin_heredoc = None
                elif "<<" in linea and fin_heredoc is None:
                    fin_heredoc = linea.split("<<", 1)[1].strip().strip("'\"-") or None
                tiempo = min(max(len(linea) * 0.035, 0.4), max(n.restante() / (len(lineas) - k), 0.3))
                self.tocar(terminal.escribir(linea, prompt), run_time=tiempo)
        partes = [p for p in cmd.get("partes", []) or []
                  if any(p.get("fragmento") and p["fragmento"] in terminal.comandos[i]["texto"]
                         for i in range(primera, len(terminal.comandos)))]
        for parte in partes:
            indice = next(i for i in range(primera, len(terminal.comandos))
                          if parte["fragmento"] in terminal.comandos[i]["texto"])
            with self.narrar(parte["texto"]) as n:
                self.tocar(terminal.quitar_subrayados(), run_time=0.2)
                subrayado = terminal.subrayar(parte["fragmento"], parte.get("nota"), comando=indice)
                self.tocar(subrayado, self._enfocar(terminal.foco, limite=terminal.marco), run_time=min(0.8, n.resto()))
        if partes:
            self.tocar(terminal.quitar_subrayados(), self._soltar(), run_time=0.6)
        if cmd.get("salida"):
            real = bool(cmd.get("salida_real"))
            # Que el comando siga a la vista: la salida se recorta a las filas que quedan libres debajo de él
            filas_comando = sum(len(terminal.comandos[i]["trozos"]) for i in range(primera, len(terminal.comandos)))
            libres = max(terminal.max_filas - filas_comando, 3)
            salida = cmd["salida"]
            if len(salida) > libres:
                salida = salida[: libres - 2] + ["…"] + salida[-1:]
            if cmd.get("texto_salida"):
                with self.narrar(cmd["texto_salida"]) as n:
                    self.tocar(terminal.salida(salida), terminal.insignia(real), run_time=min(1.4, n.resto()))
            else:
                self.tocar(terminal.salida(salida), terminal.insignia(real), run_time=1.2)
                self.silencio(1.2)

    # Tabla
    def _escena_tabla(self, esc: dict) -> None:
        tabla = _encajar(Tabla(esc["encabezados"], esc["filas"]), e.ANCHO_UTIL, e.ALTO_UTIL - 1.4)
        titulo = self._titulo_escena(esc)
        if titulo:
            tabla.next_to(titulo, DOWN, buff=0.5)
        else:
            tabla.move_to(ORIGIN)
        for k, bloque in enumerate(esc["bloques"]):
            with self.narrar(bloque["texto"]) as n:
                if k == 0:
                    self.tocar(tabla.aparecer(), *([FadeIn(titulo)] if titulo else []), run_time=min(1.4, n.resto()))
                indices = _indices(bloque.get("resaltar"))
                if indices:
                    self.tocar(tabla.resaltar(*indices), run_time=min(0.6, n.resto()))
                elif k:
                    self.tocar(tabla.normal(), run_time=min(0.4, n.resto()))

    # Pila de capas
    def _escena_capas(self, esc: dict) -> None:
        capas = _encajar(Capas(esc["capas"]), 11.5, 5.6)
        titulo = self._titulo_escena(esc)
        capas.move_to(DOWN * 0.35 if titulo else ORIGIN)
        progresivo = any("mostrar" in b for b in esc["bloques"])
        mostradas: set[int] = set()
        for k, bloque in enumerate(esc["bloques"]):
            with self.narrar(bloque["texto"]) as n:
                if k == 0:
                    self.tocar(*([FadeIn(titulo)] if titulo else []), *([] if progresivo else [capas.construir()]),
                               run_time=min(2.0, n.resto()))
                    if not progresivo:
                        mostradas = set(range(len(capas.capas)))
                nuevas = [i for i in _indices(bloque.get("mostrar")) if 0 <= i < len(capas.capas) and i not in mostradas]
                if nuevas:
                    self.tocar(*[capas.mostrar(i) for i in nuevas], run_time=min(0.9, n.resto()))
                    mostradas.update(nuevas)
                resaltar = [i for i in _indices(bloque.get("resaltar")) if 0 <= i < len(capas.capas)]
                if resaltar:
                    self.tocar(capas.resaltar(resaltar[0]), run_time=min(0.6, n.resto()))
        faltan = [i for i in range(len(capas.capas)) if i not in mostradas]
        if faltan:
            self.tocar(*[capas.mostrar(i) for i in faltan], run_time=0.6)

    # Piezas que se instalan
    def _escena_piezas(self, esc: dict) -> None:
        piezas = _encajar(Piezas(esc["items"]), e.ANCHO_UTIL, 3.6)
        titulo = self._titulo_escena(esc)
        piezas.move_to(UP * 0.7)
        destino = None
        if esc.get("destino"):
            d = esc["destino"]
            destino = Tarjeta(d.get("titulo", ""), d.get("icono"), d.get("detalle"), ancho=3.2).move_to(DOWN * 2.3)
        mostradas: set[int] = set()
        for k, bloque in enumerate(esc["bloques"]):
            with self.narrar(bloque["texto"]) as n:
                if k == 0 and titulo:
                    self.tocar(FadeIn(titulo), run_time=0.4)
                indices = _indices(bloque.get("mostrar"))
                if k == 0 and not any("mostrar" in b for b in esc["bloques"]):
                    indices = list(range(len(piezas.tarjetas)))
                nuevas = [i for i in indices if 0 <= i < len(piezas.tarjetas) and i not in mostradas]
                if nuevas:
                    self.tocar(*[piezas.mostrar(i) for i in nuevas], run_time=min(1.0, n.resto()))
                    mostradas.update(nuevas)
                if bloque.get("instalar") and destino is not None:
                    faltan = [piezas.mostrar(i) for i in range(len(piezas.tarjetas)) if i not in mostradas]
                    if faltan:
                        self.tocar(*faltan, run_time=0.5)
                        mostradas = set(range(len(piezas.tarjetas)))
                    self.tocar(FadeIn(destino, scale=0.9), run_time=0.5)
                    self.tocar(piezas.instalar(destino), run_time=min(1.4, max(n.restante() - 0.6, 0.6)))
                    self.tocar(Indicate(destino, color=e.VERDE, scale_factor=1.08), run_time=0.6)
