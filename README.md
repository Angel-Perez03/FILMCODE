<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="frontend/public/marca/filmcode-oscuro.svg">
    <img src="frontend/public/marca/filmcode.svg" alt="FilmCode" width="340">
  </picture>

  <h1>Tu código, explicado en video.</h1>

  <p>Convierte código o una guía Markdown en un video con narración y escenas animadas.<br>
  Trabaja desde el navegador, con modelos que se ejecutan en tu propio equipo.</p>

  <p><strong>React + Python · Manim · Ollama · Tu propia voz</strong></p>

  <p>
    <a href="#instalar">Instalar en Windows</a> ·
    <a href="#primer-video">Crear tu primer video</a> ·
    <a href="#problemas">Resolver problemas</a> ·
    <a href="https://hub.docker.com/r/angelitow/filmcode">Imagen en Docker Hub</a>
  </p>
</div>

---

```text
Código o guía  →  Guion  →  Narración  →  Escenas animadas  →  Video
```

| Tú eliges | FilmCode prepara | Tú conservas |
| --- | --- | --- |
| Los archivos, la explicación y la duración | El guion, la voz y las animaciones | El proyecto, sus archivos y el video final |

Puedes importar archivos o un ZIP, ajustar la duración y el formato, consultar el
guion y seguir el progreso de cada etapa. Cada proyecto conserva sus resultados
para poder retomarlo.

> [!TIP]
> **La forma más sencilla de empezar es usar la imagen ya preparada.**
> Con Docker, Python, Node, Manim y FFmpeg vienen resueltos: no tienes que
> instalarlos en Windows ni compilar el proyecto.

<a id="instalar"></a>

## Instalar en Windows

Esta guía usa **Windows x64**, **Docker Desktop con contenedores Linux** y la
imagen **`angelitow/filmcode:0.2.0`**. También hay instrucciones para Linux
[al final](#avanzado). La imagen publicada es para **Linux amd64**.

### Qué necesitas

Son tres piezas que trabajan juntas:

| Pieza | Qué hace | Cómo se prepara |
| --- | --- | --- |
| **FilmCode en Docker** | La web, la API y las animaciones | Descargar la imagen y abrirla, siguiendo esta guía |
| **Ollama + Gemma 4 12B** | Generar el guion | El asistente de Windows comprueba lo instalado y ofrece las descargas que falten |
| **VoiceStudio + CosyVoice 3 + transcripción** | Narrar con tu voz y sincronizar las palabras | El asistente instala VoiceStudio; sus motores y tu perfil se preparan dentro de esa aplicación |

**Docker Desktop se instala por separado.** Las descargas iniciales necesitan
internet. Después, la generación con Ollama y VoiceStudio es local. La voz
alternativa Edge necesita internet.

### 1. Descarga y extrae el proyecto

En GitHub, pulsa **Code → Download ZIP**. También puedes usar el ZIP de una
versión publicada. Haz clic derecho sobre el archivo y elige **Extraer todo**.

Abre la carpeta extraída. Debes ver estos archivos:

```text
FilmCode/
├── Instalar-FilmCode.cmd
├── configuracion.example
├── compose.publicado.yaml
├── README.md
└── frontend/
```

**Trabaja dentro de esa carpeta, con los archivos ya extraídos.**
La instalación usa la carpeta que contiene `compose.publicado.yaml`.

### 2. Prepara Docker Desktop

1. [Instala Docker Desktop para Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
   y sigue sus indicaciones sobre WSL y virtualización si las muestra.
2. Abre Docker Desktop y espera a que su motor esté en funcionamiento.
3. Usa **contenedores Linux**.
4. En Docker Desktop, inicia sesión y abre
   **Settings → Resources → Network → Enable host networking**.
5. Activa esa opción y pulsa **Apply and restart**. Hazlo cuando no tengas
   trabajos activos en otros contenedores.

**¿Para qué sirve esa opción?** Permite que FilmCode, dentro de Docker, se
comunique con Ollama y VoiceStudio usando las direcciones locales del mismo PC.
Se activa una vez; el instalador de FilmCode no cambia ese ajuste.

La red host requiere Docker Desktop **4.34 o posterior** y no es compatible con
**Enhanced Container Isolation**. Consulta la
[documentación de Docker](https://docs.docker.com/engine/network/drivers/host/)
si no aparece la opción. Revisa también las condiciones de uso de Docker Desktop
para tu caso.

### 3. Abre el asistente de FilmCode

Haz doble clic en **`Instalar-FilmCode.cmd`**.

El asistente comprueba Docker, Ollama, Gemma y VoiceStudio. Distingue entre
**«ya instalado»** y **«servicio cerrado»**. Revisa el diagnóstico y usa los
botones de instalación solo para lo que falte.

Antes de cada descarga muestra **qué descargará, desde dónde y cuánto ocupa**.
Cada componente necesita tu confirmación:

| Componente del asistente | Tamaño aproximado | Qué sucede si aceptas |
| --- | --- | --- |
| Ollama 0.40.8 | 1,66 GB | Descarga el instalador oficial y abre su asistente |
| Gemma `gemma4:12b` | 8 GB | Descarga el modelo en tu instalación de Ollama |
| VoiceStudio 0.5.6 | 214 MB | Descarga el instalador oficial y abre su asistente |

Si ya tienes un programa, ábrelo y pulsa **Volver a comprobar**. Ollama debe estar
abierto para consultar sus modelos y descargar Gemma. No hace falta volver a
descargar `gemma4:12b` si el asistente ya lo reconoce.

> [!IMPORTANT]
> **El asistente prepara los programas; FilmCode se abre con Docker en el paso 6.**
> CosyVoice 3, Whisper y el entorno que necesite VoiceStudio se preparan dentro
> de VoiceStudio. No están incluidos en el instalador ni en la imagen de FilmCode.

El asistente comprueba las descargas antes de abrir los instaladores. VoiceStudio
publica este EXE sin firma de editor; el asistente lo indica y verifica su SHA-256.
Windows puede pedir permisos adicionales o mostrar SmartScreen. No desactives sus
protecciones para continuar sin comprobar el origen.

[Más información sobre el asistente](frontend/public/instalador/README.md).

### 4. Prepara tu voz en VoiceStudio

Abre **VoiceStudio** y prepara lo siguiente en sus opciones de modelos o motores:

- **CosyVoice 3**, para generar la narración.
- **Faster-Whisper u otro ASR compatible con tiempos por palabra**, para
  transcribir y sincronizar el audio.
- **Un perfil con tu propia voz**, usando una grabación limpia y su transcripción
  exacta. Instalar CosyVoice no crea ese perfil por ti.

Revisa y desactiva las analíticas opcionales de VoiceStudio si quieres mantener
el uso sin telemetría. Autoriza sus descargas dentro de esa aplicación cuando
hayas revisado los tamaños y requisitos.

Deja **Ollama y VoiceStudio abiertos**. Las direcciones previstas son:

| Servicio | Dirección local |
| --- | --- |
| Ollama | `http://localhost:11434` |
| VoiceStudio | `http://localhost:3900` |
| FilmCode, después del paso 6 | `http://127.0.0.1:8765` |

Usa [VoiceStudio del proyecto enlazado](https://github.com/debpalash/VoiceStudio):
FilmCode necesita su API de voces y transcripción, no solo una aplicación con un
nombre parecido. Consulta también su
[guía de CosyVoice](https://github.com/debpalash/VoiceStudio/blob/main/docs/engines/cosyvoice.md).

### 5. Crea tu configuración

Dentro de la carpeta del proyecto, haz clic en la barra de direcciones del
Explorador, escribe **`powershell`** y pulsa **Enter**.

Copia este comando y ejecútalo **solo la primera vez**:

```powershell
Copy-Item -LiteralPath configuracion.example -Destination configuracion.local
```

Abre el archivo que acabas de crear:

```powershell
notepad configuracion.local
```

Para empezar, conserva las direcciones y el modelo propuestos. Son estos:

```ini
OLLAMA_URL=http://localhost:11434
VIDEOCODIGO_MODELO=ollama:gemma4:12b
VOICESTUDIO_URL=http://localhost:3900
VOICESTUDIO_MODELO=cosyvoice
VOICESTUDIO_VOZ=
```

**Puedes dejar `VOICESTUDIO_VOZ` vacío y elegir tu perfil por nombre al crear cada
video.** Si prefieres una voz predeterminada, sigue la
[ayuda para configurarla](#voz-predeterminada) después de abrir FilmCode.

Guarda el archivo. Solo si tu VoiceStudio exige una clave, añade tu clave local
en `OMNIVOICE_API_KEY`; en los demás casos, deja ese campo vacío.
`configuracion.local` es privado y no se sube al repositorio.

### 6. Descarga FilmCode y ábrelo

En la misma ventana de PowerShell, descarga la imagen preparada:

```powershell
docker compose --env-file configuracion.local --file compose.publicado.yaml pull
```

La primera descarga puede tardar. Cuando termine, abre FilmCode:

```powershell
docker compose --env-file configuracion.local --file compose.publicado.yaml up -d --no-build --pull never
```

Entra en **[http://127.0.0.1:8765](http://127.0.0.1:8765)**.

Abre **Ajustes → Prepara tu equipo → Volver a comprobar**. Deberías poder confirmar
la API y las herramientas incluidas, Ollama con Gemma y tu conexión a VoiceStudio.

**CosyVoice y Whisper pueden aparecer como «Sin confirmar».** Es deliberado:
consultar la instalación no inicia esos motores ni genera audio para probarlos.
Su preparación se revisa dentro de VoiceStudio. Un contenedor «healthy» confirma
la API de FilmCode, no todos los modelos de IA.

Si dejaste `VOICESTUDIO_VOZ` vacío, **«Tu perfil de voz» aparecerá pendiente**.
Puedes elegir tu perfil por nombre al crear cada video o configurar su ID con
la ayuda para la voz predeterminada. Ese aviso no impide consultar la interfaz.

<a id="primer-video"></a>

## Crea tu primer video

1. Pulsa **Crear video** e importa tu código o guía.
2. Define la explicación y la duración.
3. En voz, **selecciona por nombre el perfil que creaste en VoiceStudio**.
   Si dejaste el ID vacío en la configuración, elige ese perfil concreto en lugar
   de la opción genérica **Tu voz**.
4. Para empezar, elige un proyecto breve y **480p o 720p a 30 FPS**.
5. Pulsa **Hacer video** cuando quieras iniciar la generación.

Ese botón inicia el trabajo de guion y render. Puedes seguir el avance de la
narración, las animaciones y el video final desde el proyecto. No hay una pausa
automática obligatoria para aprobar el guion.

**«Volver a comprobar» solo consulta; «Probar voz» sí genera audio.**
La instalación se puede revisar sin generar un video.

## Abrir, cerrar y actualizar

Ejecuta los comandos desde la misma carpeta del proyecto.

| Quiero… | Qué hacer |
| --- | --- |
| Volver a abrir FilmCode | Abre Docker Desktop, Ollama y VoiceStudio, ejecuta el comando de inicio y entra en el navegador |
| Consultar si FilmCode está abierto | Ejecuta el comando de estado |
| Cerrar FilmCode | Espera a que terminen tus trabajos y ejecuta el comando de cierre |
| Aplicar un cambio de configuración | Guarda `configuracion.local` y repite el comando de inicio sin trabajos activos |

**Inicio:**

```powershell
docker compose --env-file configuracion.local --file compose.publicado.yaml up -d --no-build --pull never
```

**Estado:**

```powershell
docker compose --env-file configuracion.local --file compose.publicado.yaml ps
```

**Cierre, conservando proyectos:**

```powershell
docker compose --env-file configuracion.local --file compose.publicado.yaml down
```

Los proyectos se guardan en volúmenes de Docker y sobreviven al cierre y a la
recreación del contenedor. **`down -v` elimina esos volúmenes y sus datos**;
no lo uses para un cierre normal. Detener FilmCode interrumpe los trabajos activos.

<details>
<summary><strong>Actualizar a otra versión</strong></summary>

Cambia `FILMCODE_IMAGEN` en `configuracion.local` por la etiqueta concreta que
quieras usar de [Docker Hub](https://hub.docker.com/r/angelitow/filmcode).
Después, sin trabajos activos, repite los comandos de descarga e inicio del paso 6.
El archivo de ejemplo usa `angelitow/filmcode:0.2.0`.

La configuración tiene una versión concreta para que puedas elegir cuándo cambiar.
El comando de inicio no descarga una actualización por su cuenta.

</details>

<a id="problemas"></a>

## Si algo no funciona

| Lo que ves | Qué revisar |
| --- | --- |
| PowerShell no reconoce `docker` | Instala Docker Desktop, termina su configuración y vuelve a abrir PowerShell |
| Docker no puede conectarse a su motor | Abre Docker Desktop y espera a que termine de arrancar |
| No se encuentra `configuracion.local` | Completa el paso 5 y ejecuta los comandos en la carpeta que contiene los archivos Compose |
| FilmCode abre, pero Ollama o VoiceStudio no responden | Abre esas aplicaciones y revisa la red host del paso 2 y los puertos del paso 4 |
| El asistente dice que está instalado, pero cerrado | Abre el programa y vuelve a comprobar; ese estado no pide reinstalarlo |
| Falta `gemma4:12b` | Confirma su descarga en el asistente, o configura otro modelo local que ya tengas, como se explica abajo |
| La voz no aparece o el perfil no existe | Crea tu perfil en VoiceStudio, vuelve a consultar las voces y selecciónalo por nombre al crear el video |
| CosyVoice o Whisper dicen «Sin confirmar» | Compruébalos dentro de VoiceStudio; el diagnóstico no los ejecuta |
| El puerto 8765 está ocupado | Cierra tu instancia anterior de FilmCode antes de abrir la versión Docker; esta distribución usa el puerto 8765 |
| Hay poca memoria o el render termina por falta de RAM | Empieza con menos escenas y menor resolución. Revisa la memoria de Docker y la de los modelos por separado |

Si necesitas revisar un error, puedes consultar los registros de FilmCode:

```powershell
docker compose --env-file configuracion.local --file compose.publicado.yaml logs --tail 80 filmcode
```

Revisa y oculta cualquier dato personal antes de compartir registros.
Evita compartir `configuracion.local`, salidas de `docker inspect` o de
`docker compose config`: pueden contener configuración privada.

<a id="voz-predeterminada"></a>

<details>
<summary><strong>Cómo dejar mi voz como predeterminada</strong></summary>

Con FilmCode y VoiceStudio abiertos, consulta desde PowerShell:

```powershell
(Invoke-RestMethod http://127.0.0.1:8765/api/voces).voicestudio | Select-Object nombre,id
```

La consulta solo lista tus perfiles; no genera audio. También puedes abrir
[la lista local de voces](http://127.0.0.1:8765/api/voces) en el navegador.
Busca tu perfil y copia su `id`, que puede ser distinto de su nombre visible.

Pégalo después de `VOICESTUDIO_VOZ=` en tu archivo privado
`configuracion.local`, guarda y repite el comando de inicio.
Hazlo sin trabajos activos, porque aplicar el cambio puede recrear FilmCode.

El selector de **Ajustes → Prueba de voz** sirve para una prueba concreta:
no guarda la voz predeterminada.

</details>

<details>
<summary><strong>Ya tengo otro modelo en Ollama</strong></summary>

Consulta lo que tienes con `ollama list`. No genera texto ni descarga modelos.

Si quieres utilizar otro modelo local, escribe su nombre exacto con el prefijo
`ollama:` en `VIDEOCODIGO_MODELO` y repite el comando de inicio.
La calidad del guion y los recursos necesarios dependen del modelo elegido.

La comprobación específica de Gemma seguirá señalando que falta si no tienes
`gemma4:12b`, aunque hayas decidido usar otro modelo.

</details>

## Espacio, memoria y privacidad

| Contenido | Espacio en disco orientativo |
| --- | --- |
| Imagen de FilmCode 0.2.0 | Docker informa de 1,54 GB; la transferencia puede ocupar menos por compresión |
| Gemma `gemma4:12b` | Aproximadamente 8 GB, según revisión |
| CosyVoice 3 preparado por VoiceStudio | Aproximadamente 5,4 GB de pesos, más su entorno y dependencias |
| Whisper, VoiceStudio y sus dependencias | Variable según los componentes elegidos |
| Tus proyectos, audios y videos | Crece con lo que generes |

**El tamaño en disco no equivale a la RAM o VRAM necesaria.**
Deja espacio adicional para Docker, las descargas y tus proyectos. Los requisitos
de los modelos dependen del equipo y de cómo los ejecute cada herramienta.

El contenedor de FilmCode tiene límites iniciales de **4 CPU y 4 GiB de RAM**.
Puedes ajustarlos con `FILMCODE_CPU` y `FILMCODE_RAM` en tu configuración y
repetir el inicio cuando no haya trabajos activos.

**Estos límites no limitan Ollama ni VoiceStudio**, que se ejecutan fuera de
Docker. Tampoco garantizan que un render grande quepa en memoria. La prioridad
dinámica de procesos de Windows de la versión nativa no controla esos servicios
desde el contenedor Linux.

La distribución contiene código e instalador, sin voces, audios de referencia,
claves ni proyectos personales del autor. Cada persona prepara su propio perfil.
La interfaz carga sus recursos desde FilmCode y no usa CDNs. Para mantener la
narración local, elige VoiceStudio; Edge es una alternativa por internet.

<a id="avanzado"></a>

## Información avanzada

<details>
<summary><strong>Linux amd64</strong></summary>

Usa Docker Engine con Compose **2.24 o posterior**. La red host está disponible
directamente en Linux. Prepara Ollama y VoiceStudio con los motores necesarios
siguiendo sus instrucciones para tu sistema; el asistente CMD es solo para Windows.

Crea tu configuración desde la raíz del proyecto:

```sh
cp configuracion.example configuracion.local
```

Ajusta ese archivo, prepara tu voz y ejecuta los mismos comandos `pull` y `up`
del paso 6. La imagen publicada es Linux amd64; no se ha verificado una imagen
ARM64 ni una instalación en macOS.

</details>

<details>
<summary><strong>Qué hay dentro de Docker y dónde están mis datos</strong></summary>

La imagen incluye la web React compilada, la API Python, Manim, FFmpeg/ffprobe,
Cairo, Pango y fuentes libres. Python 3.12 está en un entorno virtual; Node 24
solo se usa durante la compilación y no hace falta en tu PC para esta vía.

Dos volúmenes conservan los datos:

- **`proyectos` → `/app/videos`**: fuentes importadas, guiones, caché de voz y videos.
- **`estado` → `/app/.web`**: seguimiento de trabajos y archivos auxiliares.

Una copia del repositorio no es una copia de seguridad de esos volúmenes.
Conserva también una copia de tus datos si vas a mover o borrar Docker.

Importa archivos o ZIP desde la interfaz: una ruta de Windows como `C:\...`
no existe dentro del contenedor Linux. Las capturas de comandos y ejemplos se
ejecutan dentro de ese Linux. Las fuentes libres pueden verse distintas de las
de Windows. La imagen no incluye TeX Live ni CUDA.

La configuración usa `network_mode: host` y FilmCode escucha en
`127.0.0.1:8765`. No necesita publicar puertos adicionales, montar todo tu disco
ni acceder al socket de Docker. No cambies los servicios a `0.0.0.0` para resolver
un problema de conexión. Esta integración conserva una frontera de servicios
locales; sustituir las URL por `host.docker.internal` no es compatible con ella.

VoiceStudio debe ofrecer `/health`, `/v1/audio/voices`, `/v1/audio/speech` y
`/v1/audio/transcriptions`. La transcripción usa `model=whisper-1`,
`response_format=verbose_json` y tiempos por palabra; ese alias debe resolver
a un motor ASR local compatible. FilmCode envía `cosyvoice` como identificador
de síntesis; el motor CosyVoice 3 se prepara en VoiceStudio.

</details>

<details>
<summary><strong>Construir la imagen desde el código, opcional</strong></summary>

Para empezar con FilmCode usa la imagen de Docker Hub del paso 6.
La construcción desde el código es una alternativa para desarrollar o adaptar
la aplicación y descarga dependencias de software.

Desde esta copia pública, con tu configuración creada:

```sh
docker compose --env-file configuracion.local build
docker compose --env-file configuracion.local up -d --no-build --pull never
```

Este flujo usa `compose.yaml`, que construye `filmcode:local`.
El flujo de Docker Hub usa `compose.publicado.yaml`.
**Elige uno de los dos; no ejecutes ambos a la vez.**

Los límites de CPU y RAM del servicio no limitan la construcción. Para un builder
dedicado con **1536 MiB, 2 CPU y sin swap adicional**, puedes usar:

```sh
docker buildx create --name filmcode-compilacion --driver docker-container --driver-opt memory=1536m,memory-swap=1536m,cpu-period=100000,cpu-quota=200000,restart-policy=no --buildkitd-config ./buildkitd.toml
docker buildx build --builder filmcode-compilacion --load --tag filmcode:local .
docker buildx stop filmcode-compilacion
```

Ejecuta el último comando también si la construcción falla. Una construcción
puede necesitar más memoria que ese límite. Buildx puede descargar su imagen
auxiliar `moby/buildkit`; no es un modelo de IA. Las bases y la caché de compilación
pueden ocupar varios GB adicionales. Las dependencias Python tienen restricciones,
pero no un lock completo de todas las versiones transitivas.

[Driver de Buildx](https://docs.docker.com/build/builders/drivers/docker-container/)
y [paralelismo de BuildKit](https://docs.docker.com/build/buildkit/configure/#max-parallelism).

</details>

<details>
<summary><strong>Qué se verificó en esta entrega</strong></summary>

La versión **0.2.0** se construyó para Linux amd64 el **22 de octubre de 2026**.
Se comprobó su arranque en un contenedor temporal sin red, sin carpetas personales
montadas y sin privilegios. Respondieron la API, la página principal, recursos
compilados y el ZIP del asistente; el estado terminó en `healthy`.

El asistente se verificó con pruebas aisladas de confirmaciones, cancelación,
integridad y manejo de errores; pasaron 53 pruebas. Estas comprobaciones no
descargaron modelos ni ejecutaron instalaciones reales en un PC limpio.

**No se verificó una generación completa ni la conexión de los modelos a través
de la red host.** La comprobación de arranque no sustituye una prueba con tu propio
equipo, modelos y voz. CosyVoice y Whisper no se iniciaron durante esas consultas.

</details>

---

**Documentación de los componentes:** [Docker](https://docs.docker.com/engine/network/drivers/host/) ·
[Ollama](https://ollama.com/download) · [Gemma 4 12B](https://ollama.com/library/gemma4:12b) ·
[VoiceStudio](https://github.com/debpalash/VoiceStudio) ·
[CosyVoice](https://github.com/FunAudioLLM/CosyVoice) ·
[Manim](https://docs.manim.community/)
