import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { peticion, useDatos } from '../api';
import type { Proyecto, Trabajo } from '../tipos';
import { avisar } from './Comun';

export interface Activo { proyecto: string; texto: string; progreso: number | null; externo: boolean }

// Solo dice si algo corre, sin avisos ni SSE: lee la misma caché que consulta la barra superior.
export function useHayTrabajo() {
  const trabajos = useQuery({ queryKey: ['/trabajos'], queryFn: () => peticion<Trabajo[]>('/trabajos'), retry: 1 });
  const proyectos = useDatos<Proyecto[]>('/proyectos');
  return Boolean(trabajos.data?.some(t => t.estado === 'corriendo') || proyectos.data?.some(p => p.situacion.startsWith('en_curso')));
}

// El trabajo que está corriendo, sea de la app (SSE) o de una terminal aparte (se ve en estado.json).
export function useTrabajoActivo(): Activo | null {
  const cliente = useQueryClient();
  const navegar = useNavigate();
  const [sse, setSse] = useState(false);
  const anteriores = useRef(new Map<string, string>());
  const trabajos = useQuery({ queryKey: ['/trabajos'], queryFn: () => peticion<Trabajo[]>('/trabajos'), refetchInterval: sse ? false : 2000, retry: 1 });
  const proyectos = useDatos<Proyecto[]>('/proyectos', 10000);
  const activo = trabajos.data?.find(t => t.estado === 'corriendo');
  const externo = activo ? undefined : proyectos.data?.find(p => p.situacion === 'en_curso_externo' || p.situacion === 'en_curso');

  useEffect(() => {
    for (const trabajo of trabajos.data ?? []) {
      if (anteriores.current.get(trabajo.id) === 'corriendo' && trabajo.estado !== 'corriendo') {
        const listo = trabajo.estado === 'terminado';
        const texto = listo ? `${trabajo.tipo === 'render' ? `Video ${trabajo.calidad ?? ''} listo` : trabajo.tipo === 'guion' ? 'Guion listo' : 'Trabajo terminado'} · ${trabajo.proyecto}` : trabajo.error || `${trabajo.proyecto}: trabajo ${trabajo.estado}.`;
        avisar(texto, { error: trabajo.estado === 'error', accion: { texto: 'Ver', ir: () => navegar(`/proyectos/${trabajo.proyecto}${listo && trabajo.tipo === 'render' ? '?vista=video' : ''}`) } });
        if ('Notification' in window && Notification.permission === 'granted') new Notification('FilmCode', { body: texto, icon: '/apple-touch-icon.png' });
      }
      anteriores.current.set(trabajo.id, trabajo.estado);
    }
  }, [trabajos.data, navegar]);

  useEffect(() => {
    if (!activo) return;
    const id = activo.id;
    const eventos = new EventSource(`/api/trabajos/${encodeURIComponent(id)}/eventos`);
    eventos.onopen = () => setSse(true);
    eventos.onerror = () => { eventos.close(); setSse(false); };
    eventos.addEventListener('progreso', e => {
      const datos = JSON.parse((e as MessageEvent<string>).data) as Pick<Trabajo, 'progreso' | 'mensaje' | 'prioridad_baja'>;
      cliente.setQueryData<Trabajo[]>(['/trabajos'], prev => prev?.map(t => t.id === id ? { ...t, ...datos } : t));
    });
    eventos.addEventListener('linea', e => {
      const { texto } = JSON.parse((e as MessageEvent<string>).data) as { texto: string };
      cliente.setQueryData<Trabajo[]>(['/trabajos'], prev => prev?.map(t => t.id === id ? { ...t, lineas: [...t.lineas, ...texto.split('\n')].slice(-200) } : t));
    });
    eventos.addEventListener('fin', () => { eventos.close(); setSse(false); void cliente.invalidateQueries(); });
    return () => { eventos.close(); setSse(false); };
    // La conexión pertenece al trabajo, no a cada actualización de su progreso.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activo?.id, cliente]);

  // Un 0 % mientras se generan voces no dice nada: se muestra como progreso sin fracción.
  const etapa = activo && proyectos.data?.find(p => p.nombre === activo.proyecto)?.etapa;
  const resultado: Activo | null = activo
    ? { proyecto: activo.proyecto, texto: activo.calidad ? `${activo.tipo} ${activo.calidad}` : etapa ?? activo.tipo, progreso: activo.progreso || null, externo: Boolean(activo.externo) }
    : externo ? { proyecto: externo.nombre, texto: externo.etapa, progreso: externo.progreso || null, externo: externo.situacion === 'en_curso_externo' } : null;

  useEffect(() => {
    document.title = resultado ? `(${resultado.progreso == null ? '…' : `${Math.round(resultado.progreso)} %`}) FilmCode` : 'FilmCode';
  }, [resultado?.progreso, resultado == null]);

  return resultado;
}
