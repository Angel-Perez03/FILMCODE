import { useSyncExternalStore } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { SplitText } from 'gsap/SplitText';
import { CustomEase } from 'gsap/CustomEase';
import { useGSAP } from '@gsap/react';

// Un solo registro para toda la app, con las dos curvas del sistema de diseño.
gsap.registerPlugin(ScrollTrigger, SplitText, CustomEase, useGSAP);
CustomEase.create('entrar', '0.23, 1, 0.32, 1');
CustomEase.create('mover', '0.77, 0, 0.175, 1');

export const REDUCIDO = '(prefers-reduced-motion: reduce)';
export const reducido = () => window.matchMedia(REDUCIDO).matches;

// Una media query como estado de React (se actualiza si cambia la ventana o la preferencia).
export function useMedia(consulta: string) {
  return useSyncExternalStore(avisar => {
    const lista = window.matchMedia(consulta);
    lista.addEventListener('change', avisar);
    return () => lista.removeEventListener('change', avisar);
  }, () => window.matchMedia(consulta).matches);
}

// ScrollTrigger mide de nuevo cuando terminan de cargar las fuentes y las imágenes.
export function refrescarAlCargar(raiz: HTMLElement) {
  const refrescar = () => ScrollTrigger.refresh();
  void document.fonts?.ready.then(refrescar);
  const pendientes = Array.from(raiz.querySelectorAll('img')).filter(img => !img.complete);
  pendientes.forEach(img => img.addEventListener('load', refrescar, { once: true }));
  return () => pendientes.forEach(img => img.removeEventListener('load', refrescar));
}

export { gsap, ScrollTrigger, SplitText, useGSAP };
