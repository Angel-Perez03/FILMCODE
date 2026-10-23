export interface Subida { archivo: File; ruta: string }
const ignorar = new Set(['.git', '.venv', 'venv', 'node_modules', '__pycache__', 'dist', 'build', '.idea', '.vscode', '.pytest_cache', '.mypy_cache', 'target', 'bin', 'obj', '.next', 'coverage']);
const extensiones = new Set('py js ts jsx tsx java c h cpp hpp cs go rs rb php kt swift sh ps1 sql html css yml yaml json dockerfile md markdown txt'.split(' '));
export function filtrarSubidas(subidas: Subida[]) {
  const archivos: Subida[] = [], ignorados: string[] = [];
  let total = 0;
  for (const subida of subidas) {
    const partes = subida.ruta.split(/[\\/]/);
    const nombre = partes.at(-1) ?? '';
    let motivo = '';
    if (partes.some(p => ignorar.has(p) || p.startsWith('.'))) motivo = 'carpeta o archivo excluido';
    else if (nombre.toLowerCase() !== 'dockerfile' && !extensiones.has(nombre.split('.').at(-1)?.toLowerCase() ?? '')) motivo = 'formato no admitido';
    else if (subida.archivo.size > 400_000) motivo = 'supera 400 KB';
    else if (archivos.length >= 400) motivo = 'límite de 400 archivos';
    else if (total + subida.archivo.size > 20_000_000) motivo = 'límite de 20 MB';
    if (motivo) ignorados.push(`${subida.ruta}: ${motivo}`); else { archivos.push(subida); total += subida.archivo.size; }
  }
  return {archivos, ignorados, total};
}
export async function archivosArrastrados(datos: DataTransfer): Promise<Subida[]> {
  const entradas = Array.from(datos.items).map(i => i.webkitGetAsEntry?.()).filter((e): e is FileSystemEntry => Boolean(e));
  if (!entradas.length) return Array.from(datos.files).map(archivo => ({archivo, ruta: archivo.name}));
  const salida: Subida[] = []; let vistos = 0;
  async function recorrer(entrada: FileSystemEntry, base = ''): Promise<void> {
    if (++vistos > 20000) throw new Error('La carpeta supera 20.000 entradas. Elige una carpeta más específica.');
    if (ignorar.has(entrada.name) || entrada.name.startsWith('.')) return;
    const ruta = `${base}${entrada.name}`;
    if (entrada.isFile) { const archivo = await new Promise<File>((resolver, rechazar) => (entrada as FileSystemFileEntry).file(resolver, rechazar)); salida.push({archivo, ruta}); }
    else {
      const lector = (entrada as FileSystemDirectoryEntry).createReader();
      while (true) { const lote = await new Promise<FileSystemEntry[]>((resolver, rechazar) => lector.readEntries(resolver, rechazar)); if (!lote.length) break; for (const hijo of lote) await recorrer(hijo, `${ruta}/`); }
    }
  }
  for (const entrada of entradas) await recorrer(entrada);
  return salida;
}
