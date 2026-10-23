import type { RefObject } from 'react';
import { gsap, reducido, refrescarAlCargar, ScrollTrigger, useGSAP } from './gsap';

// Lo marcado con data-entrada sube 24 px y aparece al entrar en pantalla, escalonado y una sola vez.
// Con movimiento reducido solo cambia la opacidad. Lo que llega después con los datos se prepara al aparecer.
export function useEntradas(raiz: RefObject<HTMLElement | null>) {
  useGSAP((_, contextSafe) => {
    const contenedor = raiz.current!;
    const quieto = reducido(), preparados = new WeakSet<Element>();
    const preparar = contextSafe!(() => {
      const nuevos = gsap.utils.toArray<HTMLElement>('[data-entrada]', contenedor).filter(el => !preparados.has(el));
      if (!nuevos.length) return;
      nuevos.forEach(el => preparados.add(el));
      gsap.set(nuevos, { autoAlpha: 0, y: quieto ? 0 : 24 });
      ScrollTrigger.batch(nuevos, {
        start: 'top 88%', once: true,
        // data-entrada="2" o "3" ordena el escalonado: primero el titular, luego el texto y al final la imagen.
        onEnter: lote => gsap.to((lote as HTMLElement[]).sort((a, b) => Number(a.dataset.entrada || 0) - Number(b.dataset.entrada || 0)),
          { autoAlpha: 1, y: 0, duration: quieto ? 0.3 : 0.6, ease: 'entrar', stagger: 0.07, overwrite: true }),
      });
    });
    preparar();
    const cambios = new MutationObserver(preparar);
    cambios.observe(contenedor, { childList: true, subtree: true });
    // Las secciones cambian de alto cuando llegan los datos: se vuelven a medir los disparadores.
    let espera = 0;
    const medir = new ResizeObserver(() => { clearTimeout(espera); espera = window.setTimeout(() => ScrollTrigger.refresh(), 150); });
    medir.observe(contenedor);
    const soltar = refrescarAlCargar(contenedor);
    return () => { cambios.disconnect(); clearTimeout(espera); medir.disconnect(); soltar(); };
  }, { scope: raiz });
}
