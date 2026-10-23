"""Composición de la API y del build local de React."""

from __future__ import annotations

import hashlib
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as ErrorHTTP
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse
from videocodigo import config, proyecto

from . import guiones, medios, preparacion, proyectos, sistema, trabajos
from .archivos import archivo_seguro
from .procesos import GestorTrabajos
from .recursos import ControlRecursos
from .seguridad import FronteraLocal, JSONSegura


def identidad_app():
    raiz = os.path.normcase(str(Path(config.RAIZ).resolve()))
    return {"aplicacion": "videocodigo-web", "raiz": hashlib.sha256(raiz.encode("utf-8")).hexdigest()}


def crear_app(desarrollo=False, gestor=None, puerto=8765):
    if isinstance(puerto, bool) or not isinstance(puerto, int) or not 1024 <= puerto <= 65535 or puerto in {3900, 11434}:
        raise ValueError("El puerto debe estar entre 1024 y 65535 y no puede ser el de Ollama ni VoiceStudio.")
    config.cargar_entorno()
    docker = os.environ.get("FILMCODE_DOCKER") == "1"
    control = ControlRecursos(config.RAIZ) if gestor is None and not docker else None
    gestor = gestor if gestor is not None else GestorTrabajos(config.RAIZ)
    gestor.control_recursos = control

    @asynccontextmanager
    async def vida(app):
        detener = threading.Event()

        def vigilar_recursos():
            try:
                while not detener.is_set():
                    try:
                        control.actualizar(gestor.listar())
                        app.state.error_recursos = False
                    except Exception:
                        app.state.error_recursos = True
                    detener.wait(1)
            finally:
                control.cerrar()

        hilo = None
        if control is not None:
            hilo = threading.Thread(target=vigilar_recursos, daemon=True, name="filmcode-recursos")
            hilo.start()
        try:
            yield
        finally:
            detener.set()
            if hilo is not None:
                hilo.join(timeout=5)
            app.state.gestor.cerrar()

    app = FastAPI(title="FilmCode", docs_url=None, redoc_url=None, openapi_url=None,
                  default_response_class=JSONSegura, lifespan=vida,
                  telemetry={"tracing": False, "metrics": False, "logs": False,
                             "operation_spans": False, "auto_configure": False})
    app.state.gestor = gestor
    app.state.desarrollo = desarrollo
    app.state.puerto = puerto
    app.state.control_recursos = control
    app.state.error_recursos = True
    if desarrollo:
        app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                           allow_methods=["GET", "POST", "PUT"],
                           allow_headers=["X-VideoCodigo", "Content-Type", "Range"])
    app.add_middleware(FronteraLocal, desarrollo=desarrollo, puerto=puerto)

    @app.get("/api/identidad")
    def identidad():
        return identidad_app()

    @app.get("/api/recursos")
    def recursos():
        controlador = app.state.control_recursos
        if controlador is None:
            if docker:
                return {"activo": bool(gestor.ocupado()), "perfil": None, "limite_cpu": None,
                        "aplicado": False, "ram_libre_gib": None, "reserva_ram_gib": None,
                        "proteccion_ram": False, "pausado": False, "servicios": [], "errores": [],
                        "mensaje": "Docker administra los límites fijos de FilmCode. "
                                   "El contenedor no ajusta los recursos de Ollama ni VoiceStudio del equipo."}
            raise HTTPException(503, "El control de recursos no está disponible en esta instancia.")
        datos = controlador.estado()
        if app.state.error_recursos:
            datos["aplicado"] = False
            datos["mensaje"] = "No se pudo confirmar el control de recursos. Se volverá a comprobar."
        return datos

    @app.exception_handler(ErrorHTTP)
    async def error_http(request, error):
        datos = error.detail if isinstance(error.detail, dict) else {"error": str(error.detail)}
        if "error" not in datos:
            datos = {"error": str(error.detail)}
        return JSONSegura(datos, status_code=error.status_code, headers=error.headers)

    @app.exception_handler(RequestValidationError)
    async def error_validacion(request, error):
        detalles = [f"{' / '.join(map(str, e['loc']))}: valor inválido ({e['type']})" for e in error.errors()]
        return JSONSegura({"error": "Revisa los datos enviados.", "errores": detalles}, status_code=422)

    @app.exception_handler(proyecto.ErrorProyecto)
    async def error_proyecto(request, error):
        return JSONSegura({"error": str(error)}, status_code=400)

    @app.exception_handler(Exception)
    async def error_interno(request, error):
        return JSONSegura({"error": "No se pudo completar la operación local. Revisa los archivos y vuelve a intentarlo."},
                          status_code=500)

    for modulo in (sistema, preparacion, proyectos, medios, guiones):
        app.include_router(modulo.router, prefix="/api")
    app.include_router(trabajos.router)

    @app.get("/{ruta:path}", include_in_schema=False)
    def interfaz(ruta: str):
        if ruta == "api" or ruta.startswith("api/"):
            raise HTTPException(404, "La ruta de API no existe.")
        try:
            dist = archivo_seguro(Path(config.RAIZ), "frontend/dist")
            archivo = archivo_seguro(dist, ruta or "index.html")
            indice = archivo_seguro(dist, "index.html")
        except HTTPException:
            raise HTTPException(404, "El archivo no existe.")
        if archivo.is_file():
            return FileResponse(archivo)
        if ruta.startswith("assets/") or Path(ruta).suffix:
            raise HTTPException(404, "El recurso no existe.")
        if not indice.is_file():
            raise HTTPException(503, "Falta compilar la interfaz: ejecuta npm run build dentro de frontend.")
        return FileResponse(indice, headers={"Cache-Control": "no-cache"})

    return app
