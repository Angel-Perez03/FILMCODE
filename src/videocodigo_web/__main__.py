"""Arranque local con reserva de puerto y reutilización de la misma instancia."""

import argparse
import errno
import http.client
import json
import os
import socket
import threading
import time
import webbrowser

import uvicorn

from .aplicacion import crear_app, identidad_app


def consultar_identidad(puerto):
    """Consulta directa a loopback, sin proxies ni redirecciones."""
    conexion = http.client.HTTPConnection("127.0.0.1", puerto, timeout=0.4)
    try:
        conexion.request("GET", "/api/identidad", headers={"Connection": "close"})
        respuesta = conexion.getresponse()
        cuerpo = respuesta.read(2049)
        if respuesta.status != 200 or len(cuerpo) > 2048:
            return {}
        datos = json.loads(cuerpo)
        return datos if isinstance(datos, dict) else {}
    except (OSError, http.client.HTTPException):
        return None
    except (ValueError, UnicodeError):
        return {}
    finally:
        conexion.close()


def reservar_puerto(puerto):
    escucha = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == "nt":
            escucha.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            escucha.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        escucha.bind(("127.0.0.1", puerto))
        escucha.setblocking(False)
        return escucha
    except OSError:
        escucha.close()
        raise


def abrir_cuando_listo(servidor, puerto, identidad, detener):
    for _ in range(120):
        if detener.is_set():
            return
        if servidor.started and consultar_identidad(puerto) == identidad:
            webbrowser.open(f"http://127.0.0.1:{puerto}")
            return
        detener.wait(0.25)


def puerto_valido(texto):
    try:
        puerto = int(texto)
    except ValueError as error:
        raise argparse.ArgumentTypeError("El puerto debe ser un número entero.") from error
    if not 1024 <= puerto <= 65535 or puerto in {3900, 11434}:
        raise argparse.ArgumentTypeError("Usa un puerto entre 1024 y 65535 distinto del de Ollama o VoiceStudio.")
    return puerto


def reutilizar(puerto, abrir):
    direccion = f"http://127.0.0.1:{puerto}"
    print(f"FilmCode ya está abierto en {direccion}. Se reutiliza esa instancia.")
    if abrir:
        webbrowser.open(direccion)
    return 0


def esperar_instancia(puerto, identidad):
    for _ in range(12):
        respuesta = consultar_identidad(puerto)
        if respuesta is not None:
            return respuesta == identidad
        time.sleep(0.1)
    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Interfaz local de FilmCode")
    parser.add_argument("--abrir", action="store_true", help="Abrir la interfaz en el navegador")
    parser.add_argument("--desarrollo", action="store_true", help="Permitir Vite en localhost:5173")
    parser.add_argument("--puerto", type=puerto_valido,
                        help="Puerto explícito; por defecto intenta 8765 y después 8766")
    argumentos = parser.parse_args(argv)
    candidatos = [argumentos.puerto] if argumentos.puerto is not None else [8765, 8766]
    identidad = identidad_app()
    for puerto in candidatos:
        if consultar_identidad(puerto) == identidad:
            return reutilizar(puerto, argumentos.abrir)
    escucha = None
    for puerto in candidatos:
        try:
            escucha = reservar_puerto(puerto)
            break
        except OSError as error:
            ocupado = error.errno in {errno.EADDRINUSE, errno.EACCES, 10013, 10048}
            if ocupado and esperar_instancia(puerto, identidad):
                return reutilizar(puerto, argumentos.abrir)
            print(f"El puerto {puerto} está ocupado o no está disponible. No se detendrá el servicio que lo usa.")
    if escucha is None:
        print("No se pudo abrir FilmCode. Elige un puerto libre con --puerto NUMERO.")
        return 1
    if argumentos.puerto is None and puerto != 8765:
        print(f"FilmCode usará el puerto alternativo {puerto}.")
    detener = threading.Event()
    try:
        app = crear_app(desarrollo=argumentos.desarrollo, puerto=puerto)
        servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=puerto,
                                               access_log=False, log_level="warning"))
        if argumentos.abrir:
            threading.Thread(target=abrir_cuando_listo,
                             args=(servidor, puerto, identidad, detener), daemon=True).start()
        print(f"FilmCode: http://127.0.0.1:{puerto}")
        servidor.run(sockets=[escucha])
        return 0 if servidor.started else 1
    finally:
        detener.set()
        escucha.close()


if __name__ == "__main__":
    raise SystemExit(main())
