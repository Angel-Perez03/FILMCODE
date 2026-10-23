import { Suspense, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Toaster } from 'sonner';
import { useDatos } from './api';
import type { Salud } from './tipos';
import { BarraSuperior } from './componentes/BarraSuperior';
import { Cargando, Mensaje } from './componentes/Comun';
import { ConfirmarProvider } from './componentes/Controles';

export function App() {
  const salud = useDatos<Salud>('/salud', 10000);
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return <ConfirmarProvider>
    <a className="vc-saltar vc-boton" href="#contenido">Saltar al contenido</a>
    <BarraSuperior/>
    <main id="contenido">
      {salud.error && <div className="vc-pagina" style={{ paddingBottom: 0 }}>
        <Mensaje tono="error" accion={<button className="vc-boton vc-boton--chico" onClick={() => void salud.refetch()}>Reintentar</button>}>
          No hay conexión con la API local. ¿Está corriendo <code>python -m videocodigo_web</code>?
        </Mensaje>
      </div>}
      <Suspense fallback={<div className="vc-pagina"><Cargando/></div>}>
        <Outlet/>
      </Suspense>
    </main>
    <Toaster position="bottom-right" gap={12} offset={24} toastOptions={{ unstyled: true, classNames: { toast: 'vc-aviso', success: 'vc-aviso--exito', error: 'vc-aviso--error', actionButton: 'vc-aviso__accion', title: 'flex-1' } }}/>
  </ConfirmarProvider>;
}
