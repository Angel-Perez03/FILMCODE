"""Validación defensiva y edición versionada del contrato original de guion."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Request
from videocodigo import guion, proyecto, voz
from videocodigo.duracion import estimar_segundos

from .archivos import MAX_JSON, archivo_seguro, carpeta_proyecto, escribir_json, invalidar_estado, leer_json
from .seguridad import JSONSegura

router = APIRouter()


def errores_guion(datos, carpeta: Path) -> list[str]:
    if not isinstance(datos, dict):
        return ["El guion debe ser un objeto JSON."]
    if len(json.dumps(datos, ensure_ascii=False, indent=2).encode("utf-8")) > MAX_JSON:
        return ["El guion supera el límite de 8 MB."]
    errores = []
    fragmentos = datos.get("fragmentos") or {}
    if not isinstance(fragmentos, dict):
        return ["'fragmentos' debe ser un objeto JSON."]
    for clave, frag in fragmentos.items():
        if not isinstance(frag, dict):
            errores.append(f"Fragmento {clave}: debe ser un objeto JSON.")
            continue
        for campo, prefijo in (("archivo", "codigo"), ("traza", "trazas")):
            if campo == "traza" and not frag.get(campo):
                continue
            try:
                valor = frag.get(campo)
                if not isinstance(valor, str):
                    raise ValueError()
                ruta = archivo_seguro(carpeta, valor)
                raiz = archivo_seguro(carpeta, prefijo)
                if not ruta.is_relative_to(raiz) or ruta == raiz:
                    raise ValueError()
                if ruta.is_file() and ruta.stat().st_size > 8_000_000:
                    raise ValueError()
            except (HTTPException, ValueError, OSError):
                errores.append(f"Fragmento {clave}: '{campo}' debe estar dentro de {prefijo}/ y ser un archivo permitido.")
        for campo in ("desde", "hasta"):
            if campo in frag and (not isinstance(frag[campo], int) or isinstance(frag[campo], bool)):
                errores.append(f"Fragmento {clave}: '{campo}' debe ser un número entero.")
    escenas = datos.get("escenas")
    if not isinstance(escenas, list):
        return errores + ["'escenas' debe ser una lista."]
    if len(escenas) > guion.MAX_ESCENAS:
        errores.append(f"Hay {len(escenas)} escenas; el máximo es {guion.MAX_ESCENAS}.")
    for numero, escena in enumerate(escenas, 1):
        if not isinstance(escena, dict):
            errores.append(f"Escena {numero}: debe ser un objeto JSON.")
            continue
        for campo in ("narracion", "bloques", "items", "lineas", "comandos"):
            contenido = escena.get(campo)
            if contenido is not None and (not isinstance(contenido, list) or
                    any(not isinstance(x, (str, dict)) for x in contenido)):
                errores.append(f"Escena {numero}: '{campo}' debe ser una lista de textos u objetos.")
        try:
            textos = guion.textos({"escenas": [escena]})
            for texto in textos:
                if not isinstance(texto, str):
                    raise TypeError()
                voz.extraer_marcas(texto)
        except (ValueError, TypeError, AttributeError, KeyError) as error:
            mensaje = str(error) if isinstance(error, ValueError) else "Comprueba los tipos de las narraciones y sus listas."
            errores.append(f"Escena {numero}: {mensaje}")
    if errores:
        return errores
    try:
        return guion.validar(datos, carpeta)
    except (ValueError, TypeError, AttributeError, KeyError, IndexError, OSError, UnicodeError):
        return ["El guion contiene campos con tipos o referencias inválidos; revisa su estructura JSON."]


@router.get("/proyectos/{nombre}/guion")
def obtener(nombre: str):
    carpeta = carpeta_proyecto(nombre)
    archivo = archivo_seguro(carpeta, "guion.json")
    origen = "guion"
    if not archivo.is_file():
        archivo = archivo_seguro(carpeta, "guion_con_errores.json")
        origen = "con_errores"
    if not archivo.is_file():
        raise HTTPException(404, "El proyecto todavía no tiene guion.")
    datos = leer_json(archivo)
    return {"guion": datos, "errores": errores_guion(datos, carpeta), "origen": origen}


@router.post("/proyectos/{nombre}/guion/validar")
def validar(nombre: str, datos=Body(...)):
    return {"errores": errores_guion(datos, carpeta_proyecto(nombre))}


@router.put("/proyectos/{nombre}/guion")
def guardar(nombre: str, request: Request, datos=Body(...)):
    gestor = request.app.state.gestor
    with gestor.bloqueo:
        carpeta = carpeta_proyecto(nombre)
        if gestor.ocupado(nombre):
            raise HTTPException(409, "Espera a que termine el trabajo de este proyecto antes de guardar.")
        errores = errores_guion(datos, carpeta)
        if errores:
            return JSONSegura({"error": "El guion contiene errores.", "errores": errores}, status_code=422)
        destino = archivo_seguro(carpeta, "guion.json")
        estado = leer_json(archivo_seguro(carpeta, "estado.json"))
        if not isinstance(estado, dict):
            raise HTTPException(422, "El estado del proyecto no es válido; no se guardó el guion.")
        archivo_seguro(carpeta, "estado.tmp")
        if destino.is_file():
            sello = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            copia = archivo_seguro(carpeta, f"guion_versiones/guion_{sello}.json")
            copia.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destino, copia)
        caracteres = sum(len(voz.extraer_marcas(t)[0]) for t in guion.textos(datos))
        duracion = datos.get("duracion") if isinstance(datos.get("duracion"), dict) else {}
        datos["duracion"] = {**duracion, "duracion_estimada_segundos": estimar_segundos(caracteres)}
        resumen = estado.get("guion") if isinstance(estado.get("guion"), dict) else {}
        resumen = {**resumen, "escenas": len(datos["escenas"]), "caracteres": caracteres,
                   "duracion_estimada_segundos": estimar_segundos(caracteres)}
        escribir_json(destino, datos)
        proyecto.actualizar_estado(nombre, etapa="guion", mensaje="guion editado a mano", progreso=100, guion=resumen)
        invalidar_estado(nombre)
        return {"guion": datos, "errores": [], "origen": "guion"}
