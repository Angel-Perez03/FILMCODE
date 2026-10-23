import type { ReactNode } from 'react';

const PALABRAS = new Set('and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield const let var function new this typeof instanceof switch case default throw catch export extends interface type'.split(' '));
const PROPIAS = new Set('print len range float int str list dict set tuple min max sum abs sorted enumerate zip map filter open isinstance console Math JSON Object Array'.split(' '));

// Resaltado sencillo con la paleta del video; alcanza para muestras, pósters y la textura del 3D, no para editar.
export function tokens(linea: string): { texto: string; clase: string }[] {
  const salida: { texto: string; clase: string }[] = [];
  const patron = /(#.*$|\/\/.*$)|("(?:\\.|[^"])*"|'(?:\\.|[^'])*')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_]\w*)(?=\s*\()|([A-Za-z_]\w*)|([^\w\s]+)/g;
  let ultimo = 0;
  for (const m of linea.matchAll(patron)) {
    if (m.index > ultimo) salida.push({ texto: linea.slice(ultimo, m.index), clase: '' });
    const [texto, comentario, cadena, numero, llamada, nombre] = m;
    const clase = comentario ? 's-co' : cadena ? 's-ca' : numero ? 's-nu' : llamada ? (PALABRAS.has(llamada) ? 's-pc' : PROPIAS.has(llamada) ? 's-bi' : 's-fn')
      : nombre ? (PALABRAS.has(nombre) ? 's-pc' : 's-no') : 's-op';
    salida.push({ texto, clase });
    ultimo = m.index + texto.length;
  }
  if (ultimo < linea.length) salida.push({ texto: linea.slice(ultimo), clase: '' });
  return salida;
}
export function resaltar(linea: string): ReactNode[] {
  return tokens(linea).map((t, k) => t.clase ? <span key={k} className={t.clase}>{t.texto}</span> : t.texto);
}

export function PanelCodigo({ lineas, activa, desde = 1, video = false, etiqueta }: {lineas: string[]; activa?: number; desde?: number; video?: boolean; etiqueta?: string}) {
  return <figure className={`vc-panel-codigo codigo${video ? ' vc-panel-codigo--video' : ''}`} aria-label={etiqueta}>
    <ol>
      {lineas.map((linea, i) => <li key={i} aria-current={desde + i === activa ? 'true' : undefined}>
        <span>{desde + i}</span>
        <span>{resaltar(linea)}</span>
      </li>)}
    </ol>
  </figure>;
}
