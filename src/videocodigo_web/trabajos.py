"""Rutas de trabajos y eventos SSE agrupados."""

from __future__ import annotations

import asyncio
import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from videocodigo import proyecto

router = APIRouter(prefix="/api")


class OpcionesTrabajo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tipo: Literal["guion", "render", "continuar", "fotogramas"]
    calidad: str | None = Field(default=None, max_length=40)
    modelo: str | None = Field(default=None, max_length=190)
    capturar: bool | None = None
    voz: Literal["voicestudio", "edge", "silencio"] | None = None  # None = la voz que trae la calidad
    voz_edge: str | None = Field(default=None, max_length=200)
    voz_voicestudio: str | None = Field(default=None, max_length=200)
    prioridad_baja: bool | None = None
    duracion_objetivo_minutos: float | None = Field(default=None, ge=1, le=120, allow_inf_nan=False)
    velocidad_voz: float | None = Field(default=None, ge=0.75, le=1.5, allow_inf_nan=False)
    velocidad_animaciones: float | None = Field(default=None, ge=0.5, le=2, allow_inf_nan=False)
    voz_fluida: bool | None = None

    @field_validator("calidad")
    @classmethod
    def calidad_conocida(cls, valor):
        if valor is not None and valor not in proyecto.CALIDADES:
            raise ValueError(f"Calidad desconocida. Usa: {', '.join(proyecto.CALIDADES)}")
        return valor


class Cancelacion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirmar_externo: bool = False


class Prioridad(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    prioridad_baja: bool


class Duracion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    duracion_objetivo_minutos: float | None = Field(ge=1, le=120, allow_inf_nan=False)


class Velocidades(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    velocidad_voz: float = Field(ge=0.75, le=1.5, allow_inf_nan=False)
    velocidad_animaciones: float = Field(ge=0.5, le=2, allow_inf_nan=False)
    voz_fluida: bool = True


@router.post("/proyectos/{nombre}/trabajos", status_code=202)
def iniciar(nombre: str, opciones: OpcionesTrabajo, request: Request):
    return request.app.state.gestor.iniciar(nombre, opciones.model_dump(exclude_none=True))


@router.post("/proyectos/{nombre}/prioridad")
def preferir_prioridad(nombre: str, opciones: Prioridad, request: Request):
    return request.app.state.gestor.preferir_prioridad(nombre, opciones.prioridad_baja)


@router.get("/trabajos")
def listar(request: Request):
    return request.app.state.gestor.listar()


@router.post("/proyectos/{nombre}/duracion")
def preferir_duracion(nombre: str, opciones: Duracion, request: Request):
    return request.app.state.gestor.preferir_duracion(nombre, opciones.duracion_objetivo_minutos)


@router.post("/proyectos/{nombre}/velocidades")
def preferir_velocidades(nombre: str, opciones: Velocidades, request: Request):
    return request.app.state.gestor.preferir_velocidades(nombre, opciones.velocidad_voz,
                                                        opciones.velocidad_animaciones, opciones.voz_fluida)


@router.get("/trabajos/{identificador}")
def obtener(identificador: str, request: Request):
    return request.app.state.gestor.obtener(identificador)


@router.post("/trabajos/{identificador}/prioridad")
def cambiar_prioridad(identificador: str, opciones: Prioridad, request: Request):
    return request.app.state.gestor.cambiar_prioridad(identificador, opciones.prioridad_baja)


@router.post("/trabajos/{identificador}/cancelar")
def cancelar(identificador: str, request: Request, opciones: Cancelacion | None = None):
    return request.app.state.gestor.cancelar(identificador, opciones.confirmar_externo if opciones else False)


def _evento(tipo: str, datos: dict) -> str:
    return f"event: {tipo}\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n"


@router.get("/trabajos/{identificador}/eventos")
async def eventos(identificador: str, request: Request):
    gestor = request.app.state.gestor
    gestor.obtener(identificador)

    async def transmitir():
        ultimo_progreso = None
        vistas = 0
        latidos = 0
        while not await request.is_disconnected():
            try:
                trabajo = await asyncio.to_thread(gestor.obtener, identificador)
            except HTTPException:
                yield _evento("fin", {"estado": "interrumpido", "error": "El proceso externo ya no está activo."})
                break
            paquete = ""
            progreso = {"progreso": trabajo["progreso"], "mensaje": trabajo["mensaje"],
                        "prioridad_baja": trabajo.get("prioridad_baja")}
            if progreso != ultimo_progreso:
                paquete += _evento("progreso", progreso)
                ultimo_progreso = progreso
            cantidad = trabajo.get("lineas_total", len(trabajo["lineas"]))
            nuevas = max(0, cantidad - vistas)
            if nuevas:
                paquete += _evento("linea", {"texto": "\n".join(trabajo["lineas"][-nuevas:])})
                vistas = cantidad
            if trabajo["estado"] != "corriendo":
                paquete += _evento("fin", {"estado": trabajo["estado"], "resultado": trabajo.get("resultado"), "error": trabajo.get("error")})
                yield paquete
                break
            if paquete:
                yield paquete
                latidos = 0
            elif latidos >= 60:
                yield ": conectado\n\n"
                latidos = 0
            latidos += 1
            await asyncio.sleep(0.25)

    return StreamingResponse(transmitir(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
