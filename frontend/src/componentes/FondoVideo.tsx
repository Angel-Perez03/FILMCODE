import { useId, useState } from 'react';

export const FONDO_PREDETERMINADO = 'predeterminado';
const FONDO_CLARO = '#F5F1E8';
const FONDO_OSCURO = '#161616';
const COLOR_VALIDO = /^#[0-9a-f]{6}$/i;

export function nombreFondoVideo(valor: string, tieneReferencia: boolean) {
  const color = valor.toUpperCase();
  if (color === FONDO_CLARO) return 'Claro';
  if (color === FONDO_OSCURO) return 'Oscuro neutro';
  if (COLOR_VALIDO.test(color)) return color;
  return tieneReferencia ? 'De la referencia' : 'Azul original';
}

export function FondoVideo({ valor, cambiar, tieneReferencia, deshabilitado = false }: {
  valor: string; cambiar: (valor: string) => void; tieneReferencia: boolean; deshabilitado?: boolean;
}) {
  const id = useId();
  const [editando, setEditando] = useState(false);
  const color = valor.toUpperCase();
  const colorValido = COLOR_VALIDO.test(color);
  const modo = !colorValido ? FONDO_PREDETERMINADO
    : !editando && (color === FONDO_CLARO || color === FONDO_OSCURO) ? color : 'personalizado';

  function elegir(modo: string) {
    setEditando(modo === 'personalizado');
    cambiar(modo === 'personalizado' ? (colorValido ? color : '#648576') : modo);
  }

  return <div className="vc-campo">
    <label className="vc-campo__etiqueta" htmlFor={id}>Fondo del video</label>
    <select id={id} className="vc-campo__entrada" value={modo} disabled={deshabilitado}
      aria-describedby={`${id}-ayuda`} onChange={e => elegir(e.target.value)}>
      <option value={FONDO_PREDETERMINADO}>{tieneReferencia ? 'Usar el fondo de la referencia' : 'Azul original'}</option>
      <option value={FONDO_CLARO}>Claro</option>
      <option value={FONDO_OSCURO}>Oscuro neutro</option>
      <option value="personalizado">Color personalizado</option>
    </select>
    {modo === 'personalizado' ? <label className="vc-fila-botones">
      <input type="color" className="vc-campo__entrada vc-fondo-video__color" value={color} disabled={deshabilitado}
        onChange={e => cambiar(e.target.value.toUpperCase())}/>
      <span>Elegir color ({color})</span>
    </label> : null}
    <span id={`${id}-ayuda`} className="vc-campo__ayuda">
      Se aplica al próximo render.{tieneReferencia ? ' Un color sólido sustituye solo el fondo de la referencia.' : ''}
    </span>
  </div>;
}
