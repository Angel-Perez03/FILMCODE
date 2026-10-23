import { createContext, useCallback, useContext, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Dialog } from '@base-ui/react/dialog';
import { Select } from '@base-ui/react/select';
import { Switch } from '@base-ui/react/switch';
import { Check, ChevronDown } from 'lucide-react';

export interface Opcion { valor: string; texto: string; detalle?: string; deshabilitada?: boolean }
export function Selector({ etiqueta, valor, opciones, cambiar, ancho, deshabilitado = false }: {etiqueta: string; valor: string; opciones: Opcion[]; cambiar: (valor: string) => void; ancho?: string; deshabilitado?: boolean}) {
  const texto = (v: unknown) => opciones.find(o => o.valor === v)?.texto ?? 'Elige una opción';
  return <Select.Root value={valor} disabled={deshabilitado} onValueChange={v => { if (typeof v === 'string') cambiar(v); }}>
    <Select.Trigger className="vc-boton" aria-label={etiqueta} style={{ minWidth: ancho, maxWidth: '100%', justifyContent: 'space-between' }}>
      <Select.Value>{texto}</Select.Value>
      <Select.Icon className="flex"><ChevronDown aria-hidden="true"/></Select.Icon>
    </Select.Trigger>
    <Select.Portal>
      <Select.Positioner alignItemWithTrigger={false} sideOffset={8} align="start" className="z-50">
        <Select.Popup className="vc-menu">
          <Select.List>
            {opciones.map(o => <Select.Item key={o.valor} value={o.valor} disabled={o.deshabilitada} className="vc-menu__item">
              <span className="vc-menu__marca">{valor === o.valor && <Check aria-hidden="true"/>}</span>
              <Select.ItemText>{o.texto}</Select.ItemText>
              {o.detalle && <small>{o.detalle}</small>}
            </Select.Item>)}
          </Select.List>
        </Select.Popup>
      </Select.Positioner>
    </Select.Portal>
  </Select.Root>;
}

export function Interruptor({ marcado, cambiar, children, ayuda }: {marcado: boolean; cambiar: (valor: boolean) => void; children: ReactNode; ayuda?: string}) {
  return <div className="grid gap-1">
    <label className="vc-interruptor">
      <Switch.Root checked={marcado} onCheckedChange={cambiar} className="vc-interruptor__pista">
        <Switch.Thumb className="vc-interruptor__mando"/>
      </Switch.Root>
      <span>{children}</span>
    </label>
    {ayuda && <p className="vc-nota" style={{ marginLeft: 52 }}>{ayuda}</p>}
  </div>;
}

export interface Confirmacion { titulo: string; texto: ReactNode; aceptar: string; cancelar?: string; peligro?: boolean; detalle?: ReactNode }
const Contexto = createContext<(opciones: Confirmacion) => Promise<boolean>>(() => Promise.resolve(false));
export function ConfirmarProvider({ children }: {children: ReactNode}) {
  const [actual, setActual] = useState<Confirmacion | null>(null);
  const [abierto, setAbierto] = useState(false);
  const resolver = useRef<(valor: boolean) => void>(() => {});
  const confirmar = useCallback((opciones: Confirmacion) => new Promise<boolean>(resolve => {
    resolver.current = resolve; setActual(opciones); setAbierto(true);
  }), []);
  function cerrar(valor: boolean) { resolver.current(valor); setAbierto(false); }
  return <Contexto.Provider value={confirmar}>
    {children}
    <Dialog.Root open={abierto} onOpenChange={abre => { if (!abre) cerrar(false); }}>
      <Dialog.Portal>
        <Dialog.Backdrop className="vc-velo"/>
        <Dialog.Popup className="vc-dialogo">
          {actual && <>
            <Dialog.Title className="titulo">{actual.titulo}</Dialog.Title>
            <Dialog.Description render={<div/>} style={{ marginTop: 16 }}>{actual.texto}</Dialog.Description>
            {actual.detalle && <div style={{ marginTop: 24 }}>{actual.detalle}</div>}
            <div className="vc-dialogo__acciones">
              <button className="vc-boton" onClick={() => cerrar(false)}>{actual.cancelar ?? 'Ahora no'}</button>
              <button className={`vc-boton ${actual.peligro ? 'vc-boton--peligro' : 'vc-boton--principal'}`} onClick={() => cerrar(true)}>{actual.aceptar}</button>
            </div>
          </>}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  </Contexto.Provider>;
}
export const useConfirmar = () => useContext(Contexto);
