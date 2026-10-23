"""Cliente para el modelo que escribe el guion: Ollama (local) o un servidor compatible con OpenAI
(LM Studio, vLLM, llama.cpp, OpenRouter…). Siempre pide JSON con esquema y lo valida.

Cada respuesta válida se guarda en caché por huella del pedido: si el proceso se corta, al
volver a correrlo no se repiten las llamadas que ya salieron bien.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable
from pathlib import Path

import requests

from .config import AjustesLLM, ajustes_llm


class ErrorLLM(RuntimeError):
    """El modelo no respondió o no logró un JSON válido. `transitorio`: vale la pena reintentar."""

    def __init__(self, mensaje: str, transitorio: bool = False):
        super().__init__(mensaje)
        self.transitorio = transitorio


TIPOS = {"string": str, "integer": int, "boolean": bool, "object": dict, "array": list, "number": (int, float)}


def forma(esquema: dict, enums: dict | None = None) -> str:
    """Ejemplo compacto del JSON que pide el esquema, para ponerlo en el prompt (modo sin gramática)."""
    def ejemplo(nodo):
        tipo = nodo.get("type")
        if tipo == "object":
            return {k: ejemplo(v) for k, v in nodo.get("properties", {}).items()}
        if tipo == "array":
            return [ejemplo(nodo["items"])]
        if "enum" in nodo:
            opciones = [o for o in nodo["enum"] if o]
            if len(opciones) > 8 and enums is not None:
                enums["íconos"] = opciones
                return "<ícono o vacío>"
            return "<" + " | ".join(opciones) + (" | vacío>" if "" in nodo["enum"] else ">")
        return {"string": "…", "integer": 0, "boolean": False, "number": 0}.get(tipo, "…")

    return json.dumps(ejemplo(esquema), ensure_ascii=False)


def validar_esquema(datos, esquema: dict, ruta: str = "respuesta") -> list[str]:
    """Revisa tipos, campos requeridos, enums y límites de listas (el subconjunto de JSON Schema que usamos)."""
    tipo = esquema.get("type")
    esperado = TIPOS.get(tipo)
    if esperado and (not isinstance(datos, esperado) or (tipo == "integer" and isinstance(datos, bool))):
        return [f"{ruta} debe ser {tipo}."]
    errores = []
    if "enum" in esquema and datos not in esquema["enum"]:
        validos = [o for o in esquema["enum"] if o]
        errores.append(f"{ruta} = {datos!r} no es válido; usa uno de: {', '.join(validos)} (o vacío).")
    if tipo == "object":
        for campo in esquema.get("required", []):
            if campo not in datos:
                errores.append(f"Falta el campo {ruta}.{campo}.")
        for campo, sub in esquema.get("properties", {}).items():
            if campo in datos:
                errores += validar_esquema(datos[campo], sub, f"{ruta}.{campo}")
    elif tipo == "array":
        if len(datos) < esquema.get("minItems", 0):
            errores.append(f"{ruta} necesita al menos {esquema['minItems']} elementos (tiene {len(datos)}).")
        if "maxItems" in esquema and len(datos) > esquema["maxItems"]:
            errores.append(f"{ruta} admite como máximo {esquema['maxItems']} elementos (tiene {len(datos)}).")
        for k, item in enumerate(datos[:20]):
            errores += validar_esquema(item, esquema["items"], f"{ruta}[{k}]")
    return errores[:20]


def _parsear(texto: str):
    texto = texto.strip()
    bloque = re.search(r"```(?:json)?\s*(.*?)```", texto, re.S)
    if bloque:
        texto = bloque.group(1).strip()
    inicio = min([i for i in (texto.find("{"), texto.find("[")) if i >= 0], default=-1)
    if inicio > 0:
        texto = texto[inicio:]
    return json.loads(texto)


class ClienteLLM:
    def __init__(self, ajustes: AjustesLLM | None = None, cache: Path | None = None, registro: Path | None = None):
        self.a = ajustes or ajustes_llm()
        self.cache, self.registro = cache, registro
        self._sin_think = False
        self.espera_reintento = 15.0  # segundos; se duplica en cada intento

    @property
    def nombre(self) -> str:
        return f"{self.a.proveedor}:{self.a.modelo}"

    def disponible(self) -> tuple[bool, str]:
        """¿Responde el servidor y tiene el modelo? Devuelve (ok, mensaje para el usuario)."""
        try:
            if self.a.proveedor == "ollama":
                r = requests.get(f"{self.a.url}/api/tags", timeout=10)
                r.raise_for_status()
                modelos = [m["name"] for m in r.json().get("models", [])]
                base = self.a.modelo if ":" in self.a.modelo else f"{self.a.modelo}:latest"
                if self.a.modelo not in modelos and base not in modelos:
                    return False, f"Ollama no tiene {self.a.modelo}. Descárgalo con: ollama pull {self.a.modelo}"
                return True, f"Ollama listo con {self.a.modelo}"
            r = requests.get(f"{self.a.url}/models", headers=self._cabeceras(), timeout=10)
            r.raise_for_status()
            return True, f"Servidor OpenAI-compatible listo en {self.a.url}"
        except requests.RequestException as error:
            return False, f"No hay servidor de modelo en {self.a.url} ({error}). ¿Está abierto Ollama?"

    def _cabeceras(self) -> dict:
        return {"Authorization": f"Bearer {self.a.clave}"} if self.a.clave else {}

    def _chat(self, mensajes: list[dict], esquema: dict, temperatura: float) -> tuple[str, dict]:
        if self.a.proveedor == "ollama":
            # num_predict pone techo a la respuesta: con salida forzada a JSON, un modelo pequeño puede quedarse
            # repitiendo elementos de una lista hasta llenar el contexto.
            cuerpo = {"model": self.a.modelo, "messages": mensajes, "stream": False,
                      "options": {"temperature": temperatura, "num_ctx": self.a.contexto,
                                  "num_predict": self.a.max_tokens, "repeat_penalty": 1.08}}
            # La gramática del esquema es exacta pero lenta con vocabularios grandes (Gemma: 262 mil tokens).
            # En modo "libre" el modelo escribe sin gramática y validar_esquema revisa la forma después.
            if self.a.formato == "esquema":
                cuerpo["format"] = esquema
            elif self.a.formato == "json":
                cuerpo["format"] = "json"
            if not self._sin_think:
                cuerpo["think"] = False
            r = requests.post(f"{self.a.url}/api/chat", json=cuerpo, timeout=1800)
            if r.status_code == 400 and "think" in r.text.lower() and not self._sin_think:
                self._sin_think = True
                return self._chat(mensajes, esquema, temperatura)
            if not r.ok:
                raise ErrorLLM(f"Ollama respondió {r.status_code}: {r.text[:300]}", transitorio=r.status_code >= 500)
            datos = r.json()
            uso = {"entrada": datos.get("prompt_eval_count"), "salida": datos.get("eval_count")}
            return datos["message"]["content"], uso
        cuerpo = {"model": self.a.modelo, "messages": mensajes, "temperature": temperatura, "max_tokens": self.a.max_tokens}
        if self.a.formato == "esquema":
            cuerpo["response_format"] = {"type": "json_schema",
                                         "json_schema": {"name": "respuesta", "schema": esquema, "strict": False}}
        elif self.a.formato == "json":
            cuerpo["response_format"] = {"type": "json_object"}
        r = requests.post(f"{self.a.url}/chat/completions", json=cuerpo, headers=self._cabeceras(), timeout=1800)
        if not r.ok:
            raise ErrorLLM(f"El servidor respondió {r.status_code}: {r.text[:300]}", transitorio=r.status_code >= 500)
        datos = r.json()
        uso = datos.get("usage", {})
        return datos["choices"][0]["message"]["content"], {"entrada": uso.get("prompt_tokens"),
                                                          "salida": uso.get("completion_tokens")}

    def json(self, sistema: str, usuario: str, esquema: dict, validar: Callable[[dict], list[str]] | None = None,
             intentos: int = 3, temperatura: float | None = None, etiqueta: str = "") -> dict:
        """Pide un JSON que cumpla `esquema`; si `validar` devuelve errores, se los manda al modelo para que corrija."""
        temperatura = self.a.temperatura if temperatura is None else temperatura
        huella = hashlib.sha256(json.dumps([self.nombre, self.a.formato, sistema, usuario, esquema], ensure_ascii=False)
                                .encode("utf-8")).hexdigest()[:20]
        archivo = self.cache / f"{huella}.json" if self.cache else None
        if archivo and archivo.exists():
            return json.loads(archivo.read_text(encoding="utf-8"))
        if self.a.formato != "esquema":
            enums: dict = {}
            molde = forma(esquema, enums)
            usuario += ("\n\nResponde SOLO con un objeto JSON válido, sin texto antes ni después, con esta forma:\n"
                        + molde)
            if enums.get("íconos"):
                usuario += "\nÍconos válidos: " + ", ".join(enums["íconos"]) + "."
        mensajes = [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]
        errores: list[str] = []
        for intento in range(1, intentos + 1):
            inicio = time.time()
            texto, uso = self._chat_con_reintentos(mensajes, esquema, temperatura)
            try:
                datos = _parsear(texto)
                errores = validar_esquema(datos, esquema)
                if not errores and validar:
                    errores = validar(datos)
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                datos, errores = None, [f"La respuesta no es un JSON válido ({error})."]
            self._anotar(etiqueta, intento, time.time() - inicio, uso, errores)
            if not errores:
                if archivo:
                    archivo.parent.mkdir(parents=True, exist_ok=True)
                    archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
                return datos
            mensajes += [{"role": "assistant", "content": texto},
                         {"role": "user", "content": "Corrige estos problemas y responde de nuevo solo con el JSON "
                                                     "completo:\n- " + "\n- ".join(errores[:12])}]
        raise ErrorLLM(f"{etiqueta or 'El modelo'} no logró una respuesta válida tras {intentos} intentos: "
                       + "; ".join(errores[:5]))

    def _chat_con_reintentos(self, mensajes: list[dict], esquema: dict, temperatura: float,
                             intentos: int = 4) -> tuple[str, dict]:
        """Reintenta cuando el servidor del modelo se cae a mitad de camino (Ollama relanza el modelo solo)."""
        falla: Exception | None = None
        for k in range(intentos):
            try:
                return self._chat(mensajes, esquema, temperatura)
            except (requests.ConnectionError, requests.Timeout) as error:
                falla = error
            except requests.RequestException as error:
                raise ErrorLLM(f"No se pudo hablar con el modelo: {error}") from error
            except ErrorLLM as error:
                if not error.transitorio:
                    raise
                falla = error
            if k < intentos - 1:
                time.sleep(self.espera_reintento * 2 ** k)
        raise ErrorLLM(f"El modelo falló {intentos} veces seguidas; revisa que Ollama siga abierto. Último error: {falla}")

    def _anotar(self, etiqueta: str, intento: int, segundos: float, uso: dict, errores: list[str]) -> None:
        if not self.registro:
            return
        self.registro.parent.mkdir(parents=True, exist_ok=True)
        linea = {"etiqueta": etiqueta, "modelo": self.nombre, "intento": intento, "segundos": round(segundos, 1),
                 "tokens": uso, "errores": errores[:5], "fecha": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with self.registro.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
