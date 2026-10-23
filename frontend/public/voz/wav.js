/** Codifica muestras mono normalizadas como WAV PCM16, sin filtros ni recortes. */
export function crearWav(muestras, frecuencia) {
  if (!(muestras instanceof Float32Array) || muestras.length === 0) {
    throw new TypeError('La grabación debe contener muestras de audio.');
  }
  if (!Number.isInteger(frecuencia) || frecuencia < 8000 || frecuencia > 384000) {
    throw new RangeError('La frecuencia de audio no es válida.');
  }
  const bytesAudio = muestras.length * 2;
  if (bytesAudio > 0xffffffff - 36) throw new RangeError('El audio supera el tamaño del formato WAV.');
  const buffer = new ArrayBuffer(44 + bytesAudio);
  const vista = new DataView(buffer);
  const texto = (inicio, valor) => {
    for (let i = 0; i < valor.length; i += 1) vista.setUint8(inicio + i, valor.charCodeAt(i));
  };
  texto(0, 'RIFF');
  vista.setUint32(4, 36 + bytesAudio, true);
  texto(8, 'WAVE');
  texto(12, 'fmt ');
  vista.setUint32(16, 16, true);
  vista.setUint16(20, 1, true);
  vista.setUint16(22, 1, true);
  vista.setUint32(24, frecuencia, true);
  vista.setUint32(28, frecuencia * 2, true);
  vista.setUint16(32, 2, true);
  vista.setUint16(34, 16, true);
  texto(36, 'data');
  vista.setUint32(40, bytesAudio, true);
  for (let i = 0; i < muestras.length; i += 1) {
    const original = muestras[i];
    if (!Number.isFinite(original)) throw new TypeError('El audio contiene una muestra no válida.');
    const valor = Math.max(-1, Math.min(1, original));
    vista.setInt16(44 + i * 2, Math.round(valor < 0 ? valor * 32768 : valor * 32767), true);
  }
  return buffer;
}
