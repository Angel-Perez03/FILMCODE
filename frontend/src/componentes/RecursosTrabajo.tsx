import { useDatos } from '../api';
import { numero } from '../logica';
import type { EstadoRecursos } from '../tipos';
import { Insignia, Mensaje } from './Comun';

export function RecursosTrabajo({ activo }: {activo: boolean}) {
  const consulta = useDatos<EstadoRecursos>('/recursos', 2000, activo);
  if (!activo) return null;
  if (consulta.isPending) return <p className="vc-nota" role="status">Verificando el control de CPU y memoria…</p>;
  if (consulta.error || !consulta.data) return <Mensaje tono="aviso">No se pudo consultar el control de recursos. La capacidad de CPU asignada no está confirmada.</Mensaje>;

  const datos = consulta.data;
  const cpuConfirmada = datos.activo && datos.aplicado && datos.limite_cpu != null
    && Number.isFinite(datos.limite_cpu) && datos.limite_cpu > 0 && datos.limite_cpu <= 100;
  const ramLibre = Number.isFinite(datos.ram_libre_gib) ? `${numero(datos.ram_libre_gib, 2)} GiB` : 'sin datos';
  const reserva = Number.isFinite(datos.reserva_ram_gib) ? `${numero(datos.reserva_ram_gib, 2)} GiB` : 'sin datos';

  return <section className="vc-campo" aria-label="Control de recursos del trabajo">
    <div className="vc-fila-botones">
      <span className="vc-campo__etiqueta">Recursos del equipo</span>
      <Insignia texto={cpuConfirmada ? `Capacidad de CPU asignada: ${numero(datos.limite_cpu!, 2)} %` : 'Capacidad de CPU no confirmada'} color={cpuConfirmada ? 'verde' : 'amarillo'}/>
      {datos.proteccion_ram && <Insignia texto="Protección de memoria activa" color="amarillo"/>}
      {datos.pausado && <Insignia texto="Pausa confirmada por el servidor" color="amarillo"/>}
    </div>
    <p className="vc-nota">El porcentaje corresponde a los procesadores lógicos habilitados para el trabajo y los servicios incluidos.</p>
    <p className="vc-nota">RAM libre: {ramLibre} · Margen de RAM objetivo: {reserva}</p>
    {datos.mensaje && <p className="vc-nota" role="status">{datos.mensaje}</p>}
    {datos.servicios.length > 0 && <p className="vc-nota">Servicios incluidos: {datos.servicios.join(', ')}.</p>}
    {datos.errores.map((error, i) => <Mensaje key={`${i}-${error}`} tono="aviso">{error}</Mensaje>)}
  </section>;
}
