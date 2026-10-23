import { gsap, reducido } from './gsap';

// La miniatura viaja de la fila de Proyectos a la cabecera del proyecto (mismo data-flip-id), solo con transform.
// Se mide en coordenadas de la ventana porque el cambio de ruta vuelve el scroll a cero entre una medida y la otra.
let pendiente: { id: string; caja: DOMRect; hora: number } | null = null;

export function capturarFlip(id: string) {
  const origen = Array.from(document.querySelectorAll<HTMLElement>(`[data-flip-id="${CSS.escape(id)}"]`)).find(el => el.getClientRects().length > 0);
  pendiente = origen && !reducido() ? { id, caja: origen.getBoundingClientRect(), hora: Date.now() } : null;
}

export function aplicarFlip(destino: HTMLElement | null) {
  if (!destino || !pendiente || destino.dataset.flipId !== pendiente.id) return;
  const { caja, hora } = pendiente;
  pendiente = null;
  if (Date.now() - hora > 3000) return;
  // Espera dos cuadros a que la página nueva vuelva arriba; mientras tanto la miniatura no se ve.
  gsap.set(destino, { autoAlpha: 0 });
  requestAnimationFrame(() => requestAnimationFrame(() => {
    gsap.set(destino, { autoAlpha: 1 });
    const fin = destino.getBoundingClientRect();
    if (!fin.width) return;
    gsap.from(destino, { x: caja.left - fin.left, y: caja.top - fin.top, scale: caja.width / fin.width, transformOrigin: '0 0', duration: 0.42, ease: 'mover', clearProps: 'transform' });
  }));
}
