"""Frontera local, límites de peticiones y protección de secretos."""

from __future__ import annotations

import json
import os
import re
import tempfile
from urllib.parse import urlsplit

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

CLAVES = ("OPENAI_API_KEY", "OMNIVOICE_API_KEY")
MAX_CUERPO = 21_000_000
MAX_VIDEO_REFERENCIA = 200 * 1024 * 1024
MAX_CUERPO_REFERENCIA = MAX_CUERPO + MAX_VIDEO_REFERENCIA


def sanitizar(valor):
    if isinstance(valor, dict):
        return {sanitizar(k): ("[oculto]" if re.search(r"api.?key|authorization|(?:^|_)clave$", str(k), re.I)
                    and not isinstance(v, bool) else sanitizar(v)) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [sanitizar(v) for v in valor]
    if isinstance(valor, str):
        for nombre in CLAVES:
            secreto = os.environ.get(nombre, "")
            if secreto:
                valor = valor.replace(secreto, "[oculto]")
        valor = re.sub(r"(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[oculto]@", valor)
        valor = re.sub(r"(?i)(Bearer\s+)[\w.\-]+", r"\1[oculto]", valor)
    return valor


class JSONSegura(JSONResponse):
    def render(self, content) -> bytes:
        return super().render(sanitizar(content))


def url_local(url: str) -> str:
    try:
        partes = urlsplit(url)
        valido = (partes.scheme == "http" and partes.hostname in {"127.0.0.1", "localhost", "::1"}
                  and not partes.username and not partes.password and not partes.query and not partes.fragment)
        partes.port
    except ValueError:
        valido = False
    if not valido:
        raise HTTPException(400, "El servicio debe usar una URL HTTP local, sin credenciales en la dirección.")
    return url.rstrip("/")


class FronteraLocal:
    def __init__(self, app, desarrollo=False, puerto=8765):
        self.app = app
        self.desarrollo = desarrollo
        self.hosts = {f"127.0.0.1:{puerto}", f"localhost:{puerto}"}
        self.origenes = {f"http://{host}" for host in self.hosts}
        if desarrollo:
            self.origenes.add("http://localhost:5173")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        cabeceras = {k.decode("latin1").lower(): v.decode("latin1") for k, v in scope["headers"]}

        async def rechazar(codigo, mensaje):
            await JSONSegura({"error": mensaje}, status_code=codigo)(scope, receive, send)

        if cabeceras.get("host", "").lower() not in self.hosts:
            return await rechazar(400, "Host no permitido: usa la dirección local de FilmCode.")
        mutacion = scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}
        if mutacion and (cabeceras.get("x-videocodigo") != "1"
                         or cabeceras.get("origin") not in self.origenes):
            return await rechazar(403, "La petición debe originarse en FilmCode y llevar su cabecera de seguridad.")
        subida_referencia = (scope["method"] == "POST" and scope["path"] == "/api/proyectos/con-referencia"
                             and cabeceras.get("content-type", "").startswith("multipart/form-data"))
        if subida_referencia:
            # El límite grande solo se aplica a esta ruta y se guarda en disco,
            # sin retener el video completo en la memoria de la API.
            longitud = cabeceras.get("content-length", "")
            if longitud.isdecimal() and (len(longitud) > 10 or int(longitud) > MAX_CUERPO_REFERENCIA):
                return await rechazar(413, "El video de referencia puede pesar hasta 200 MiB.")
            try:
                with tempfile.TemporaryFile() as archivo:
                    total = 0
                    while True:
                        mensaje = await receive()
                        if mensaje["type"] == "http.disconnect":
                            return
                        datos = mensaje.get("body", b"")
                        total += len(datos)
                        if total > MAX_CUERPO_REFERENCIA:
                            return await rechazar(413, "El video de referencia puede pesar hasta 200 MiB.")
                        await run_in_threadpool(archivo.write, datos)
                        if not mensaje.get("more_body", False):
                            break
                    await run_in_threadpool(archivo.seek, 0)
                    pendiente = True

                    async def desde_disco():
                        nonlocal total, pendiente
                        if not pendiente:
                            return await receive()
                        datos = await run_in_threadpool(archivo.read, 1024 * 1024)
                        total -= len(datos)
                        pendiente = total > 0
                        return {"type": "http.request", "body": datos, "more_body": pendiente}

                    return await self._despachar(scope, desde_disco, send)
            except OSError:
                return await rechazar(507, "No hay espacio o permiso para guardar la subida temporal.")
        receptor = receive
        if mutacion:
            trozos, total = [], 0
            while True:
                mensaje = await receive()
                if mensaje["type"] == "http.disconnect":
                    return
                total += len(mensaje.get("body", b""))
                if total > MAX_CUERPO:
                    return await rechazar(413, "La petición supera el límite de subida de 20 MB.")
                trozos.append(mensaje)
                if not mensaje.get("more_body", False):
                    break

            async def receptor():
                return trozos.pop(0) if trozos else await receive()

        return await self._despachar(scope, receptor, send)

    async def _despachar(self, scope, receptor, send):
        iniciada = False

        async def enviar(mensaje):
            nonlocal iniciada
            if mensaje["type"] == "http.response.start":
                iniciada = True
                conexiones = "'self'" + (" http://localhost:5173 ws://localhost:5173" if self.desarrollo else "")
                politica = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                            "img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self'; "
                            f"connect-src {conexiones}; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
                mensaje["headers"] = list(mensaje.get("headers", [])) + [
                    (b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer"),
                    (b"content-security-policy", politica.encode()),
                ]
            await send(mensaje)

        try:
            await self.app(scope, receptor, enviar)
        except Exception:
            if iniciada:
                raise RuntimeError("La transmisión local se interrumpió.") from None
            await JSONSegura({"error": "No se pudo completar la operación local. Revisa los archivos y vuelve a intentarlo."},
                             status_code=500)(scope, receptor, enviar)
