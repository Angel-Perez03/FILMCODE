import type { CSSProperties } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { useDatos } from '../api';
import type { Salud } from '../tipos';
import { numero } from '../logica';
import { Insignia } from './Comun';
import { Marca } from './Marca';
import { useTrabajoActivo } from './TrabajosVivos';

const enlaces = [['/', 'Inicio'], ['/proyectos', 'Proyectos'], ['/ajustes', 'Ajustes']] as const;

export function BarraSuperior() {
  const salud = useDatos<Salud>('/salud', 10000);
  const activo = useTrabajoActivo();
  const servicio = (clave: 'ollama' | 'voicestudio', nombre: string) => {
    if (salud.error) return <Insignia texto={`${nombre} sin conexión`} color="gris"/>;
    const listo = salud.data?.[clave].listo;
    return <Insignia texto={`${nombre} ${salud.data ? (listo ? 'listo' : 'apagado') : '…'}`} color={listo ? 'verde' : 'gris'}/>;
  };
  return <>
    <nav className="vc-nav" aria-label="Principal">
      <Link to="/" className="vc-nav__marca" aria-label="FilmCode, inicio"><Marca/></Link>
      <ul className="vc-nav__items">
        {enlaces.map(([ruta, texto]) => <li key={ruta}>
          <NavLink to={ruta} end={ruta === '/'} className="vc-nav__item">{texto}</NavLink>
        </li>)}
      </ul>
      <div className="vc-nav__servicios">{servicio('ollama', 'Ollama')}{servicio('voicestudio', 'VoiceStudio')}</div>
      {activo && <Link className="vc-nav__trabajo" to={`/proyectos/${activo.proyecto}`} title={activo.externo ? 'Lanzado desde una terminal' : undefined}>
        <span>{activo.proyecto} · {activo.texto}</span>
        <span className="vc-cifras">{activo.progreso == null ? 'en curso' : `${numero(activo.progreso)} %`}</span>
      </Link>}
      <Link className="vc-boton vc-boton--principal" to="/nuevo">Crear video</Link>
    </nav>
    {activo && <Link to={`/proyectos/${activo.proyecto}`} className={`vc-hilo${activo.progreso == null ? ' vc-hilo--indeterminado' : ''}`} style={{ '--valor': (activo.progreso ?? 0) / 100 } as CSSProperties} aria-label={`Progreso de ${activo.proyecto}`}><i/></Link>}
  </>;
}

