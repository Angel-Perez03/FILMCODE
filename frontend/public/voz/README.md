# Grabador local de referencias de voz

Abrir `http://127.0.0.1:8766/voz/index.html` si la API está en 8766; sustituir el puerto por el de tu aplicación. Con Vite, abrir `/voz/index.html` en su dirección local. La carpeta es independiente de React y no requiere paquetes nuevos ni un build propio. El build normal de Vite copia `public/voz/` a `dist/voz/`.

1. Elegir una de las cinco lecturas. Cada texto tiene 40–55 palabras; los 15–25 segundos son una orientación, no una duración garantizada.
2. Pulsar **Grabar esta lectura** y conceder acceso al micrófono. No se solicita cámara ni se activa el micrófono al cargar la página.
3. Leer con voz natural y pulsar **Detener**. El límite es 30 segundos; no se recortan silencios ni se aplican filtros al audio.
4. Escuchar el WAV. Abrir **Revisar la transcripción** y corregir cualquier diferencia entre el texto y lo que realmente se dijo. Descargar **WAV** y **TXT**; sus nombres comparten identificador, fecha y número de toma.
5. Repetir cualquier lectura: las tomas anteriores permanecen. Se conservan hasta 20 tomas en memoria. **Descargar antes de cerrar o recargar la pestaña**; no hay almacenamiento persistente ni recuperación tras cerrar.

El aviso de salida se mantiene mientras se está grabando o falta pulsar la descarga de alguno de los dos archivos. El navegador no permite confirmar si el archivo llegó a guardarse en disco: comprueba tus descargas. Al salir se detienen las pistas y se cierra el contexto de audio. Si se cancela el aviso de salida durante una grabación, esa grabación se detiene.

El WAV contiene PCM16 mono a la frecuencia real del AudioContext. Se pide al navegador desactivar cancelación de eco, reducción de ruido y ganancia automática; el hardware puede aplicar sus propios ajustes. AudioWorklet está servido desde esta carpeta. No hay dependencias, CDNs, telemetría, WebSockets, llamadas a la API ni consultas a modelos.

Esto prepara material para elegir una referencia clara. **No entrena una voz, no importa audios a VoiceStudio ni combina automáticamente tomas.** Elegir una grabación natural, limpia y bien transcrita es más útil que acumular tomas con ruido. El uso posterior depende del modelo y del flujo que el usuario elija.

## Verificación

Sin micrófono: abrir la página, cambiar las cinco lecturas, navegar con Tab y revisar consola/red. Solo deben cargarse estos archivos locales, sin solicitudes de micrófono. `wav.js` exporta `crearWav(Float32Array, frecuencia)` y devuelve un ArrayBuffer, por lo que sus cabeceras RIFF/WAVE y muestras pueden validarse con Node sin navegador ni grabación real. `lecturas.js` también se puede importar para contar las palabras.

Prueba manual cuando el usuario decida grabar: denegar el permiso y comprobar el mensaje; permitirlo mediante otro clic; grabar, detener y confirmar que desaparece el indicador de micrófono. Reproducir y descargar ambos archivos. Repetir y comprobar que las tomas tienen nombres distintos. Editar un TXT sin alterar el audio. Comprobar el límite de 30 s, cancelar mientras se espera el permiso y salir durante una grabación. Una toma sin muestras o sin señal no ofrece archivos vacíos.

Archivos: `index.html`, `grabador.css`, `grabador.js`, `lecturas.js`, `procesador.js`, `wav.js` y este README. Todos son independientes del resto de la interfaz.
