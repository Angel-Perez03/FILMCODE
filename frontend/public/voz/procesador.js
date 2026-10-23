/* Se ejecuta en el hilo de audio. La salida se mantiene en silencio: no hay monitorización. */
class GrabadorMono extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bloque = new Float32Array(2048);
    this.indice = 0;
    this.total = 0;
    this.pico = 0;
    this.terminado = false;
    this.limite = Math.round(sampleRate * 30);
    this.port.onmessage = ({ data }) => {
      if (data?.tipo === 'parar') this.finalizar('usuario');
    };
  }

  enviar() {
    if (!this.indice) return;
    const muestras = this.bloque.slice(0, this.indice);
    this.port.postMessage({ tipo: 'muestras', muestras, pico: this.pico }, [muestras.buffer]);
    this.indice = 0;
    this.pico = 0;
  }

  finalizar(motivo) {
    if (this.terminado) return;
    this.terminado = true;
    this.enviar();
    this.port.postMessage({ tipo: 'fin', motivo });
  }

  process(entradas, salidas) {
    for (const salida of salidas) for (const canal of salida) canal.fill(0);
    if (this.terminado) return true;
    const canales = entradas[0];
    if (!canales?.length || !canales[0]?.length) return true;
    for (let i = 0; i < canales[0].length; i += 1) {
      let muestra = 0;
      for (const canal of canales) muestra += canal[i];
      muestra /= canales.length;
      this.bloque[this.indice++] = muestra;
      this.pico = Math.max(this.pico, Math.abs(muestra));
      this.total += 1;
      if (this.indice === this.bloque.length) this.enviar();
      if (this.total >= this.limite) {
        this.finalizar('limite');
        break;
      }
    }
    return true;
  }
}

registerProcessor('grabador-mono', GrabadorMono);
