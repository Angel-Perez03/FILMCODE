"""Prepara un guion más breve para la exportación con duración fija."""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from videocodigo import guion
from videocodigo.duracion import CARACTERES_POR_SEGUNDO
from videocodigo.velocidades import validar_velocidades
from videocodigo.voz import extraer_marcas

from .archivos import archivo_seguro, escribir_json, leer_json
from .guiones import errores_guion


class ErrorAjusteGuion(ValueError):
    """El guion no puede reducirse al presupuesto de forma segura."""


@dataclass(frozen=True)
class ResultadoAjuste:
    guion: dict
    segundos_originales: float
    segundos_estimados: float
    escenas_eliminadas: int
    modificado: bool


_FIN_FRASE = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÁÉÍÓÚÜÑ¿¡])")
_ABREVIATURA = re.compile(r"(?:\b[A-Za-zÁÉÍÓÚÜÑ]|\b(?:sr|sra|dr|dra|prof|ing|etc|ej|pág|núm|ud|uds))\.$", re.I)
_EXPLICACION = {"codigo", "terminal", "tabla", "diagrama", "grafo", "arbol", "pila", "arreglo", "capas", "piezas"}


def _quitar_ultima_frase(texto: str) -> str | None:
    # Las marcas de sincronía y los literales delimitados pueden depender de toda la frase.
    if "[[" in texto or "`" in texto:
        return None
    for limite in reversed(list(_FIN_FRASE.finditer(texto))):
        prefijo = texto[:limite.start()].rstrip()
        if _ABREVIATURA.search(prefijo):
            continue
        if any(prefijo.count(a) != prefijo.count(b) for a, b in (("(", ")"), ("[", "]"), ("«", "»"), ("“", "”"))):
            continue
        if prefijo.count('"') % 2 == 0:
            return prefijo
    return None


def _sustituir(objeto, ruta: tuple, valor):
    """Copia solo la rama modificada; la copia completa se hace al devolver el guion."""
    if not ruta:
        return valor
    copia = objeto.copy()
    copia[ruta[0]] = _sustituir(objeto[ruta[0]], ruta[1:], valor)
    return copia


def _rutas_texto(escena: dict) -> Iterator[tuple[tuple, str]]:
    for clave in ("intro", "cierre", "resultado", "reto"):
        if isinstance(escena.get(clave), str):
            yield (clave,), escena[clave]
    for clave in ("narracion", "bloques", "items", "lineas"):
        for i, bloque in enumerate(escena.get(clave) or []):
            if isinstance(bloque, str):
                yield (clave, i), bloque
            elif isinstance(bloque.get("texto"), str):
                yield (clave, i, "texto"), bloque["texto"]
    for i, comando in enumerate(escena.get("comandos") or []):
        for clave in ("texto", "texto_salida"):
            if isinstance(comando.get(clave), str):
                yield ("comandos", i, clave), comando[clave]
        for j, parte in enumerate(comando.get("partes") or []):
            yield ("comandos", i, "partes", j, "texto"), parte["texto"]


def _recortes(escena: dict, frases: bool) -> Iterator[dict]:
    # Una traza genera narración adicional en el motor. Quitar sus bloques
    # haría que reapareciera el texto automático para los pasos omitidos.
    if escena["tipo"].endswith("_traza"):
        return
    if frases:
        for ruta, texto in _rutas_texto(escena):
            corto = _quitar_ultima_frase(texto)
            if corto is not None:
                yield _sustituir(escena, ruta, corto)
        return
    if escena.get("reto"):
        yield {clave: valor for clave, valor in escena.items() if clave != "reto"}
    campos = ("narracion", "bloques", "lineas", "comandos")
    if escena["tipo"] == "lista":
        campos += ("items",)
    for clave in campos:
        lista = escena.get(clave) or []
        if clave == "bloques" and any(isinstance(b, dict) and b.get("acciones") for b in lista):
            # Una secuencia de operaciones puede depender de su estado final.
            continue
        if len(lista) > 1:
            # Retirar solo el final mantiene los índices y las acciones previas.
            yield {**escena, clave: lista[:-1]}
    for i, comando in enumerate(escena.get("comandos") or []):
        partes = comando.get("partes") or []
        if partes:
            yield _sustituir(escena, ("comandos", i, "partes"), partes[:-1])


def _limpios(escena: dict) -> list[str]:
    return [limpio for texto in guion.textos({"escenas": [escena]}) if (limpio := extraer_marcas(texto)[0])]


def _segundos_escena(escena: dict, voz: float, animaciones: float, pausa: float,
                      medidas: Mapping[str, float]) -> float:
    # Margen para la transición y el redondeo de los bloques a fotogramas.
    tipo = escena["tipo"]
    textos = _limpios(escena)
    animacion, silencio = 0.6, 0.0
    if tipo == "portada" and not textos:
        animacion += 1.4
        silencio += 1.2
    elif tipo == "codigo":
        animacion += 1.2 + (0.6 if escena.get("titulo") else 0)
        if escena.get("titulo") and not escena.get("intro"):
            animacion += 1.2
            silencio += 1.0
    elif tipo == "terminal":
        animacion += 0.8 if not escena.get("intro") else 0
        for cmd in escena.get("comandos", []):
            animacion += (0.6 if cmd.get("partes") else 0) + (0.4 if cmd.get("limpiar") else 0)
            if cmd.get("salida") and not cmd.get("texto_salida"):
                animacion += 1.2
                silencio += 1.2
    elif tipo in {"grafo", "arbol", "arreglo", "pila"}:
        animacion += {"grafo": 1.5, "arbol": 1.5, "arreglo": 0.8, "pila": 0.6}[tipo]
    elif tipo == "cierre" and escena.get("reto"):
        animacion += 0.6
    voz_segundos = sum(max(0.3, medidas.get(t, len(t) / (CARACTERES_POR_SEGUNDO * voz))) for t in textos)
    return animacion / animaciones + silencio + voz_segundos + len(textos) * (pausa + 0.04)


def ajustar_guion(datos: dict, segundos_objetivo: float, velocidad_voz: float = 1.15,
                  velocidad_animaciones: float = 1.0, voz_fluida: bool = True, *,
                  segundos_presupuesto: float | None = None,
                  duraciones: Mapping[str, float] | None = None) -> ResultadoAjuste:
    """Reduce un guion válido sin modificar la entrada, usando oraciones y bloques completos.

    Las duraciones medidas, si se conocen, están a la velocidad de voz solicitada.
    La estimación orienta el ajuste: la exportación comprueba la duración real.
    """
    limite = segundos_objetivo if segundos_presupuesto is None else segundos_presupuesto
    for valor in (segundos_objetivo, limite):
        if isinstance(valor, bool) or not isinstance(valor, (float, int)) or not math.isfinite(valor) or not 0 < valor <= 7200:
            raise ErrorAjusteGuion("El presupuesto debe ser un número de segundos positivo, hasta 120 minutos.")
    if not isinstance(voz_fluida, bool):
        raise ErrorAjusteGuion("La narración continua debe estar activada o desactivada.")
    voz, animaciones = validar_velocidades(velocidad_voz, velocidad_animaciones)
    pausa = 0.12 if voz_fluida else 0.35
    medidas = {t: v for t, v in (duraciones or {}).items()
               if not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) and v > 0}

    def costo(escena: dict) -> float:
        return _segundos_escena(escena, voz, animaciones, pausa, medidas)

    escenas = list(datos["escenas"])
    costos = [costo(e) for e in escenas]
    original = total = sum(costos) + 0.6  # Pausa final del motor.
    n_original = len(escenas)
    recortadas: list[tuple[int, dict, float]] = []
    # Primero conservar todas las escenas; luego, si hace falta, quitar unidades
    # completas. El máximo de intentos también limita el trabajo con guiones grandes.
    for frases in (True, False):
        for _ in range(120):
            if total <= limite:
                break
            mejor = None
            for i, escena in enumerate(escenas):
                for alternativa in _recortes(escena, frases):
                    nuevo = costo(alternativa)
                    ahorro = costos[i] - nuevo
                    if ahorro <= 0.001:
                        continue
                    # Prefiere conservar contenido si un recorte pequeño ya basta.
                    clave = (0, ahorro) if total - ahorro <= limite else (1, -ahorro)
                    if mejor is None or clave < mejor[0]:
                        mejor = (clave, i, alternativa, nuevo, ahorro)
            if mejor is None:
                break
            _, i, alternativa, nuevo, ahorro = mejor
            recortadas.append((i, escenas[i], costos[i]))
            escenas[i], costos[i] = alternativa, nuevo
            total -= ahorro

    vigentes = set(range(len(escenas)))
    if total > limite:
        portada = next((i for i, e in enumerate(escenas) if e["tipo"] == "portada"), None)
        cierre = next((i for i in range(len(escenas) - 1, -1, -1) if escenas[i]["tipo"] == "cierre"), None)
        protegidas = {i for i in (portada, cierre) if i is not None}
        cuerpo = [i for i, e in enumerate(escenas) if e["tipo"] not in {"portada", "cierre"} and _limpios(e)]
        if cuerpo:
            # Conserva una explicación; si una cuesta demasiado, elige una que quepa.
            restante = limite - sum(costos[i] for i in protegidas) - 0.6
            caben = [i for i in cuerpo if costos[i] <= restante]
            protegidas.add(min(caben or cuerpo, key=lambda i: (escenas[i]["tipo"] not in _EXPLICACION, costos[i])))
        if not protegidas:
            protegidas.add(0)
        while total > limite and (extras := vigentes - protegidas):
            i = min(extras, key=lambda i: (0, costos[i], i) if total - costos[i] <= limite
                    else (1, escenas[i]["tipo"] in _EXPLICACION, -costos[i], i))
            vigentes.remove(i)
            total -= costos[i]

    if total > limite + 0.001:
        raise ErrorAjusteGuion("El guion no cabe en la duración elegida conservando su explicación principal. "
                               "Acorta la fuente o elige una duración mayor.")
    # Si al omitir una escena quedó espacio, recupera frases completas en las demás.
    for i, anterior, costo_anterior in reversed(recortadas):
        if i in vigentes and total + costo_anterior - costos[i] <= limite:
            total += costo_anterior - costos[i]
            escenas[i], costos[i] = anterior, costo_anterior
    nuevo = deepcopy({**datos, "escenas": [e for i, e in enumerate(escenas) if i in vigentes]})
    return ResultadoAjuste(nuevo, round(original, 2), round(total, 2), n_original - len(vigentes),
                           nuevo["escenas"] != datos["escenas"])


def preparar_guion(carpeta: Path, segundos_objetivo: float, velocidad_voz: float = 1.15,
                   velocidad_animaciones: float = 1.0, voz_fluida: bool = True, *,
                   segundos_presupuesto: float | None = None,
                   duraciones: Mapping[str, float] | None = None,
                   guion_fuente: dict | None = None) -> ResultadoAjuste:
    """Valida y guarda el ajuste, preservando el guion original como una versión."""
    archivo = archivo_seguro(carpeta, "guion.json")
    datos = leer_json(archivo)
    fuente = datos if guion_fuente is None else guion_fuente
    if errores_guion(fuente, carpeta):
        raise ErrorAjusteGuion("El guion tiene errores; corrígelo antes de ajustar la duración.")
    ajuste = ajustar_guion(fuente, segundos_objetivo, velocidad_voz, velocidad_animaciones, voz_fluida,
                          segundos_presupuesto=segundos_presupuesto, duraciones=duraciones)
    if guion_fuente is not None:
        ajuste = replace(ajuste, modificado=ajuste.guion["escenas"] != datos["escenas"])
    if not ajuste.modificado:
        return ajuste
    if errores_guion(ajuste.guion, carpeta):
        raise ErrorAjusteGuion("No se pudo ajustar la duración sin romper el guion. Se conservó el guion original.")
    archivo_estado = archivo_seguro(carpeta, "estado.json")
    estado = leer_json(archivo_estado)
    if not isinstance(estado, dict):
        raise ErrorAjusteGuion("El estado del proyecto no es válido. Se conservó el guion original.")
    sello = datetime.now()
    copia = archivo_seguro(carpeta, f"guion_versiones/guion_{sello:%Y%m%d_%H%M%S_%f}_antes_de_ajustar.json")
    medidas = {"duracion_objetivo_minutos": segundos_objetivo / 60,
               "duracion_estimada_segundos": ajuste.segundos_estimados}
    duracion_anterior = datos.get("duracion") if isinstance(datos.get("duracion"), dict) else {}
    ajuste.guion["duracion"] = {**duracion_anterior, **medidas}
    resumen = estado.get("guion") if isinstance(estado.get("guion"), dict) else {}
    estado.update(guion={**resumen, **medidas, "escenas": len(ajuste.guion["escenas"]),
                         "caracteres": sum(len(t) for e in ajuste.guion["escenas"] for t in _limpios(e))},
                  etapa="guion", mensaje="Guion ajustado a la duración solicitada", progreso=100,
                  actualizado=sello.isoformat(timespec="seconds"))
    escribir_json(copia, datos)
    escribir_json(archivo, ajuste.guion)
    try:
        escribir_json(archivo_estado, estado)
    except OSError:
        escribir_json(archivo, datos)
        raise
    return ajuste
