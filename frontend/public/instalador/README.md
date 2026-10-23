# Preparar FilmCode en Windows

El asistente se ejecuta en el PC Windows anfitrión. Sirve también cuando FilmCode está en Docker: Ollama y VoiceStudio se instalan en Windows, fuera del contenedor.

## Empezar con doble clic

1. Descarga `instalador-windows.zip` desde **Ajustes → Prepara tu equipo** y extrae todo su contenido en una carpeta.
2. Abre `Instalar-FilmCode.cmd` con doble clic. No ejecutes los archivos directamente dentro del ZIP.
3. Revisa el diagnóstico: el asistente distingue entre un programa instalado, un servicio que responde y los modelos que puede confirmar.
4. Antes de cada descarga, revisa el componente, la fuente y el tamaño. Confirma solo lo que quieras instalar o descargar. Puedes rechazar un componente y continuar con los demás.
5. Prepara tu propio perfil de voz en VoiceStudio. Vuelve a FilmCode y pulsa **Volver a comprobar**.

Hace falta conexión a internet para descargar programas o modelos. La ejecución de FilmCode, Ollama y VoiceStudio es local; algunas voces opcionales, como Edge, requieren internet.

## Qué prepara

- **Ollama:** programa local que sirve el modelo de texto.
- **Gemma en Ollama:** modelo de texto usado por FilmCode. El asistente comprueba lo instalado antes de ofrecer la descarga.
- **VoiceStudio:** aplicación local para las voces. La preparación de sus motores y modelos se realiza mediante las opciones que se indiquen en el asistente y en la propia aplicación; instalar el programa no confirma por sí solo que CosyVoice y Whisper estén listos.

Los tamaños varían por versión y modelo. El asistente informa del tamaño disponible o de una estimación antes de pedir confirmación. Si no puede verificar una descarga, muestra el motivo y las instrucciones para continuar; no instala una alternativa silenciosamente.

## Tu voz y tu configuración

Este paquete no contiene voces, perfiles, audios de referencia, videos, claves ni configuración personal del autor. Cada persona crea y selecciona su propia voz en VoiceStudio.

La comprobación de la interfaz web es de solo lectura. El instalador descargado es un programa separado y solicita las confirmaciones en Windows. El navegador y el contenedor no reciben permisos para instalar programas en el anfitrión.

No hace falta generar un audio ni renderizar un video para comprobar la instalación. Si un servicio está cerrado, que la interfaz lo indique como no disponible no significa necesariamente que falte instalarlo.
