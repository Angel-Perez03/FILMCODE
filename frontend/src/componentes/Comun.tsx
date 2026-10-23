import type { CSSProperties, KeyboardEvent, ReactNode } from 'react';
import { toast } from 'sonner';
import { Check, CircleAlert, Info, TriangleAlert } from 'lucide-react';

interface OpcionesAviso { error?: boolean; accion?: { texto: string; ir: () => void } }
export function avisar(texto: string, opciones: OpcionesAviso | boolean = {}) {
  const { error = false, accion } = typeof opciones === 'boolean' ? { error: opciones } : opciones;
  const datos = { action: accion ? { label: accion.texto, onClick: accion.ir } : undefined, duration: error ? Infinity : 6000 };
  if (error) toast.error(texto, datos); else toast.success(texto, datos);
}
export const useAviso = () => avisar;

export function navegarPestanas(evento: KeyboardEvent<HTMLElement>) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(evento.key)) return;
  const botones = Array.from(evento.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]:not(:disabled)'));
  const indice = botones.indexOf(document.activeElement as HTMLButtonElement);
  if (indice < 0 || !botones.length) return;
  evento.preventDefault();
  const siguiente = evento.key === 'Home' ? 0 : evento.key === 'End' ? botones.length - 1 : (indice + (evento.key === 'ArrowRight' ? 1 : -1) + botones.length) % botones.length;
  botones[siguiente].focus(); botones[siguiente].click();
}

type Tono = 'error' | 'aviso' | 'info';
const iconosTono = { error: CircleAlert, aviso: TriangleAlert, info: Info };
export function Mensaje({ tono = 'info', children, accion }: {tono?: Tono; children: ReactNode; accion?: ReactNode}) {
  const IconoTono = iconosTono[tono];
  return <div className={`vc-mensaje vc-mensaje--${tono}`} role={tono === 'error' ? 'alert' : undefined}>
    <IconoTono aria-hidden="true"/>
    <p>{children}</p>
    {accion}
  </div>;
}
export function ErrorVista({ error, reintentar }: {error: Error | null; reintentar?: () => void}) {
  if (!error) return null;
  return <Mensaje tono="error" accion={reintentar && <button className="vc-boton vc-boton--chico" onClick={reintentar}>Reintentar</button>}>{error.message}</Mensaje>;
}
export function Vacio({ titulo, children }: {titulo: string; children?: ReactNode}) {
  return <div className="vc-vacio">
    <h2 className="entrada" style={{ margin: 0 }}>{titulo}</h2>
    {children}
  </div>;
}
export function Cargando() {
  return <div className="vc-esqueletos" role="status" aria-label="Cargando"><div/><div/><div/></div>;
}

export type ColorInsignia = 'verde' | 'amarillo' | 'rojo' | 'gris';
export function Insignia({ texto, color }: {texto: string; color?: ColorInsignia}) {
  return <span className={`vc-insignia${color ? ` vc-insignia--${color}` : ''}`}>{texto}</span>;
}

export function Progreso({ valor, mensaje, cifras, estado = 'curso', grande = false, etiqueta }: {valor: number | null; mensaje: ReactNode; cifras?: string; estado?: 'curso' | 'terminado' | 'error'; grande?: boolean; etiqueta?: string}) {
  const indeterminado = valor == null && estado === 'curso';
  const clases = ['vc-progreso', grande && 'vc-progreso--grande', indeterminado && 'vc-progreso--indeterminado', estado === 'terminado' && 'vc-progreso--terminado', estado === 'error' && 'vc-progreso--error'].filter(Boolean).join(' ');
  const fraccion = estado === 'terminado' ? 1 : Math.min(1, Math.max(0, (valor ?? 0) / 100));
  return <div className={clases} style={{ '--valor': fraccion } as CSSProperties} role="progressbar" aria-label={etiqueta ?? (typeof mensaje === 'string' ? mensaje : 'Progreso')} aria-valuemin={0} aria-valuemax={100} {...(valor == null ? {} : { 'aria-valuenow': Math.round(valor) })}>
    <span className="vc-progreso__avance"/>
    <span className="vc-progreso__mensaje">{mensaje}</span>
    {cifras && <span className="vc-progreso__cifras">{cifras}</span>}
  </div>;
}

export interface Paso { titulo: string; hecho: boolean; aviso?: {texto: string; color: ColorInsignia} }
export function Pasos({ pasos, actual }: {pasos: Paso[]; actual: number}) {
  return <ol className="vc-pasos" aria-label="Pasos del proyecto">
    {pasos.map((paso, i) => <li key={paso.titulo} className={`vc-paso${paso.hecho && i !== actual ? ' vc-paso--hecho' : ''}`} aria-current={i === actual ? 'step' : undefined}>
      {paso.hecho && i !== actual && <Check aria-hidden="true"/>}
      {paso.titulo}
      {paso.hecho && i !== actual && <span className="vc-oculto">, hecho</span>}
      {i === actual && paso.aviso && <Insignia texto={paso.aviso.texto} color={paso.aviso.color}/>}
    </li>)}
  </ol>;
}

export function Terminal({ titulo = 'Ventana de terminal', real, children }: {titulo?: string; real?: boolean; children: ReactNode}) {
  return <figure className="vc-terminal">
    <div className="vc-terminal__barra">
      <span className="vc-terminal__punto"/><span className="vc-terminal__punto"/><span className="vc-terminal__punto"/>
      <span className="vc-terminal__titulo">{titulo}</span>
      {real !== undefined && <Insignia texto={real ? 'salida real de este equipo' : 'salida de ejemplo'} color={real ? 'verde' : 'gris'}/>}
    </div>
    <pre className="vc-terminal__cuerpo codigo">{children}</pre>
  </figure>;
}
