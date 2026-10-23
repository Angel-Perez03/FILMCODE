"""Captura real de comandos: al hacer un video, ejecuta en este equipo los comandos que solo verifican
algo y guarda lo que de verdad imprimen, para mostrarlo en la terminal del video.

Reglas:
- Solo se ejecuta lo que está en la lista de permitidos y no toca nada de la lista prohibida.
- Nada que instale, borre, cambie configuración o pida privilegios. Sin redirecciones ni cadenas.
- `docker run` va con --pull=never (no descarga imágenes), salvo hello-world, que pesa unos KB.
- La salida se anonimiza: usuario, nombre del equipo y carpeta personal no salen en el video.
"""

from __future__ import annotations

import getpass
import os
import platform
import re
import shlex
import socket
import subprocess
import time
from pathlib import Path

PROHIBIDO = re.compile(
    r"(^|\s)(sudo|rm|rmdir|del|erase|format|shutdown|reboot|kill|taskkill|reg|regedit|apt|apt-get|dnf|yum|"
    r"pacman|snap|brew|choco|winget|scoop|pip|npm|yarn|pnpm|curl|wget|usermod|groupadd|useradd|newgrp|passwd|"
    r"chmod|chown|tee|dd|mkfs|mount|umount|systemctl\s+(start|stop|restart|enable|disable))\b"
    r"|--install|--update|--set-default|--unregister|--shutdown|--terminate|--import|--export|uninstall|"
    r"\b(Remove|Set|New|Stop|Start|Restart|Install|Uninstall|Clear|Disable|Enable)-[A-Z]\w+|"
    r"docker\s+(rm|rmi|stop|kill|system|volume|network|image\s+rm|container\s+rm|login|logout|push|build|pull)\b|"
    r"[;&|`]|>|<|\$\(", re.IGNORECASE)

PERMITIDO = [
    re.compile(r"^docker\s+(version|--version|-v)$"),
    re.compile(r"^docker\s+compose\s+version$"),
    re.compile(r"^docker\s+run\s+(--rm\s+)?hello-world$"),
    re.compile(r"^docker\s+run\s+[\w\s.:=-]*\bpython:[\w.-]+\s+python3?\s+-c\s+\"[^\"]*\"$"),
    re.compile(r"^wsl\s+(--status|--version|-l\s+-v|--list\s+--verbose|-l|--list)$"),
    re.compile(r"^[\w.-]+\s+(--version|-V|version)$"),
]


def _sin_sudo(comando: str) -> str:
    return re.sub(r"^\s*sudo\s+", "", comando).strip()


def ejecutable(comando: str) -> tuple[bool, str]:
    """¿Se puede ejecutar este comando de forma segura en este equipo? Devuelve (sí/no, motivo)."""
    limpio = _sin_sudo(comando)
    if "\n" in limpio:
        return False, "comando de varias líneas"
    prueba = limpio
    for m in re.finditer(r"\"[^\"]*\"", limpio):  # el programa entre comillas de python -c no cuenta como cadena de shell
        prueba = prueba.replace(m.group(), '""')
    if PROHIBIDO.search(prueba):
        return False, "modifica el sistema o encadena comandos"
    if not any(p.match(limpio) for p in PERMITIDO):
        return False, "no está en la lista de comandos de verificación"
    return True, "verificación segura"


def _preparar(comando: str) -> str:
    """Ajustes para ejecutar sin terminal interactiva y sin descargas."""
    limpio = _sin_sudo(comando)
    if limpio.startswith("docker run"):
        limpio = re.sub(r"\s-it\b|\s-ti\b", " -i", limpio)
        limpio = re.sub(r"\s-t\b", "", limpio)
        if "hello-world" in limpio:
            if "--rm" not in limpio:
                limpio = limpio.replace("docker run", "docker run --rm", 1)
        elif "--pull" not in limpio:
            limpio = limpio.replace("docker run", "docker run --pull=never", 1)
    return limpio


def anonimizar(texto: str) -> str:
    reemplazos = []
    for valor, nuevo in ((str(Path.home()), r"C:\Users\usuario"), (getpass.getuser(), "usuario"),
                         (os.environ.get("USERNAME", ""), "usuario"), (socket.gethostname(), "equipo"),
                         (os.environ.get("COMPUTERNAME", ""), "equipo")):
        if valor and len(valor) >= 3:
            reemplazos.append((valor, nuevo))
    for valor, nuevo in reemplazos:
        texto = re.sub(re.escape(valor), nuevo.replace("\\", "\\\\"), texto, flags=re.IGNORECASE)
    return texto


def _limpiar(texto: str) -> list[str]:
    texto = texto.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    texto = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", texto)
    lineas = [l.rstrip() for l in anonimizar(texto).split("\n")]
    while lineas and not lineas[-1]:
        lineas.pop()
    while lineas and not lineas[0]:
        lineas.pop(0)
    return lineas


def capturar(comando: str, shell: str = "powershell", timeout: int = 120) -> dict:
    """Ejecuta un comando permitido y devuelve su salida real (o el motivo por el que no se ejecutó)."""
    permitido, motivo = ejecutable(comando)
    resultado = {"comando": comando, "ejecutado": False, "motivo": motivo, "salida": [], "codigo": None,
                 "segundos": 0.0, "equipo": f"{platform.system()} {platform.release()}"}
    if not permitido:
        return resultado
    real = _preparar(comando)
    entorno = {**os.environ, "WSL_UTF8": "1", "PYTHONIOENCODING": "utf-8", "DOCKER_CLI_HINTS": "false"}
    if platform.system() == "Windows":
        orden = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + real]
    else:
        orden = shlex.split(real)
    inicio = time.time()
    try:
        # stderr junto a stdout, en el orden en que salen (Docker escribe el progreso de la descarga en stderr)
        proceso = subprocess.run(orden, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, env=entorno,
                                 stdin=subprocess.DEVNULL)
        texto = proceso.stdout.decode("utf-8", errors="replace")
        resultado.update(ejecutado=True, codigo=proceso.returncode, salida=_limpiar(texto),
                         motivo="salida real" if proceso.returncode == 0 else "el comando terminó con error")
    except (OSError, subprocess.SubprocessError) as error:
        resultado.update(motivo=f"no se pudo ejecutar ({type(error).__name__})")
    resultado["segundos"] = round(time.time() - inicio, 2)
    return resultado


RUIDO = re.compile(r":\s+(Pulling fs layer|Waiting|Verifying Checksum|Download complete|Downloading|Extracting)\b")


def recortar(lineas: list[str], maximo: int = 12) -> list[str]:
    """Deja la salida en `maximo` líneas: el principio y el final, con '…' en medio.

    Antes de cortar quita el ruido de las descargas de Docker (una línea por capa y estado), para que quepan
    el 'Pull complete' y lo que imprime el contenedor.
    """
    if len(lineas) <= maximo:
        return lineas
    utiles = [l for l in lineas if not RUIDO.search(l)]
    if len(utiles) <= maximo:
        return utiles
    return utiles[: maximo - 3] + ["…"] + utiles[-2:]
