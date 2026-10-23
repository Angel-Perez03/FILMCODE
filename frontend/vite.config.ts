import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const puerto = process.env.VIDEOCODIGO_PUERTO || '8765';
if (!/^\d+$/.test(puerto) || Number(puerto) < 1024 || Number(puerto) > 65535) {
  throw new Error('VIDEOCODIGO_PUERTO debe ser un puerto entre 1024 y 65535.');
}

// React y Base UI van en paquetes propios; three y R3F quedan solos en el del bloque 3D, que se carga aparte.
const PAQUETES: [RegExp, string][] = [
  [/[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler|@tanstack)[\\/]/, 'react'],
  [/[\\/]node_modules[\\/](@base-ui|@floating-ui)[\\/]/, 'base-ui'],
];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: { __PUERTO_API__: JSON.stringify(puerto) },
  build: { rollupOptions: { output: { manualChunks: id => PAQUETES.find(([patron]) => patron.test(id))?.[1] } } },
  server: { host: 'localhost', port: 5173, strictPort: true, proxy: { '/api': { target: `http://127.0.0.1:${puerto}`, changeOrigin: true } } },
});
