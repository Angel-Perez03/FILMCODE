import { lazy, StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, Link, RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App } from './App';
import { Vacio } from './componentes/Comun';
import './estilos.css';

const cliente = new QueryClient({ defaultOptions: { queries: { staleTime: 1000, refetchOnWindowFocus: false } } });
const Proyectos = lazy(() => import('./paginas/Proyectos').then(m => ({ default: m.Proyectos })));
const Inicio = lazy(() => import('./paginas/Inicio').then(m => ({ default: m.Inicio })));
const NuevoVideo = lazy(() => import('./paginas/NuevoVideo').then(m => ({ default: m.NuevoVideo })));
const ProyectoVista = lazy(() => import('./paginas/Proyecto').then(m => ({ default: m.ProyectoVista })));
const AjustesVista = lazy(() => import('./paginas/Ajustes').then(m => ({ default: m.AjustesVista })));
const perdido = (titulo: string) => <div className="vc-pagina"><Vacio titulo={titulo}><Link className="vc-boton" to="/proyectos">Ver los proyectos</Link></Vacio></div>;
const router = createBrowserRouter([{ element: <App/>, errorElement: perdido('No se pudo abrir esta pantalla'), children: [
  { index: true, element: <Inicio/> },
  { path: 'proyectos', element: <Proyectos/> },
  { path: 'nuevo', element: <NuevoVideo/> },
  { path: 'proyectos/:nombre', element: <ProyectoVista/> },
  { path: 'ajustes', element: <AjustesVista/> },
  { path: '*', element: perdido('Esta página no existe') },
] }]);
createRoot(document.getElementById('root')!).render(<StrictMode>
  <QueryClientProvider client={cliente}>
    <RouterProvider router={router}/>
  </QueryClientProvider>
</StrictMode>);
