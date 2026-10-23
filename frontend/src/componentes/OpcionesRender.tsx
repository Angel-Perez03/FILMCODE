import { useId } from 'react';
import { configRenderInicial } from '../logica';
import { Selector } from './Controles';

const PRESETS = [
  { calidad: '720p30', nombre: 'Equilibrado', detalle: '720p · 30 FPS' },
  { calidad: '480p30', nombre: 'Rápido', detalle: '480p · 30 FPS' },
  { calidad: '720p60', nombre: 'Fluido', detalle: '720p · 60 FPS' },
  { calidad: '1080p30', nombre: 'Detalle', detalle: '1080p · 30 FPS' },
] as const;

export function OpcionesRender({ calidad, cambiar, deshabilitado = false }: {calidad: string; cambiar: (valor: string) => void; deshabilitado?: boolean}) {
  const grupo = useId();
  const actual = configRenderInicial(calidad);
  const separador = actual.indexOf('p');
  const resolucion = actual.slice(0, separador), fps = actual.slice(separador + 1);

  return <fieldset className="vc-opciones-render" disabled={deshabilitado}>
    <legend className="vc-campo__etiqueta">Formato del video</legend>
    <div className="vc-opciones-render__presets">
      {PRESETS.map(preset => <label key={preset.calidad} className="vc-opciones-render__preset" data-activo={actual === preset.calidad ? '' : undefined}>
        <input type="radio" name={grupo} value={preset.calidad} checked={actual === preset.calidad} onChange={() => cambiar(preset.calidad)}/>
        <span><strong>{preset.nombre}</strong><small>{preset.detalle}</small></span>
      </label>)}
    </div>
    <div className="vc-dos-columnas">
      <div className="vc-campo">
        <span className="vc-campo__etiqueta">Resolución</span>
        <Selector etiqueta="Resolución del video" valor={resolucion} cambiar={valor => cambiar(`${valor}p${fps}`)} deshabilitado={deshabilitado} opciones={['480', '720', '1080'].map(valor => ({ valor, texto: `${valor}p` }))}/>
      </div>
      <div className="vc-campo">
        <span className="vc-campo__etiqueta">Cuadros por segundo</span>
        <Selector etiqueta="Cuadros por segundo del video" valor={fps} cambiar={valor => cambiar(`${resolucion}p${valor}`)} deshabilitado={deshabilitado} opciones={[{ valor: '30', texto: '30 FPS' }, { valor: '60', texto: '60 FPS' }]}/>
      </div>
    </div>
    <p className="vc-campo__ayuda">Los presets eligen resolución y FPS. La voz y su ritmo se ajustan por separado.</p>
  </fieldset>;
}
