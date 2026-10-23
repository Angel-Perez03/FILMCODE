import { useQuery } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import type { Salud } from './tipos';

export class ErrorAPI extends Error {
  constructor(mensaje: string, public codigo: number, public errores: string[] = []) { super(mensaje); }
}
export async function peticion<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const cabeceras = new Headers(opciones.headers);
  if (opciones.method && opciones.method !== 'GET') cabeceras.set('X-VideoCodigo', '1');
  if (opciones.body && !(opciones.body instanceof FormData)) cabeceras.set('Content-Type', 'application/json');
  let respuesta: Response;
  try { respuesta = await fetch(`/api${ruta}`, { ...opciones, headers: cabeceras }); }
  catch { throw new ErrorAPI('No hay conexión con la API local. ¿Está corriendo python -m videocodigo_web?', 0); }
  if (!respuesta.ok) {
    const datos = await respuesta.json().catch(() => ({})) as {error?: string; errores?: string[]};
    throw new ErrorAPI(datos.error ?? `La petición falló (${respuesta.status}).`, respuesta.status, datos.errores);
  }
  return await respuesta.json() as T;
}
export const enviar = <T,>(ruta: string, datos: unknown, metodo = 'POST') => peticion<T>(ruta, { method: metodo, body: JSON.stringify(datos) });
export const baseProyecto = (nombre: string) => `/proyectos/${encodeURIComponent(nombre)}`;
export async function refrescarSalud(cliente: QueryClient) {
  const salud = await peticion<Salud>('/salud?forzar=true');
  cliente.setQueryData(['/salud'], salud);
}
export function useDatos<T>(ruta: string, intervalo?: number, habilitado = true) {
  return useQuery({ queryKey: [ruta], queryFn: () => peticion<T>(ruta), refetchInterval: intervalo, enabled: habilitado, retry: 1 });
}
