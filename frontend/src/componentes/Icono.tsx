import { AppWindow, Archive, Box, Brackets, ChartNoAxesColumn, CircleCheck, Clapperboard, Clock, Cloud, Code, Container, Cpu, Database, Download, File, Files, Flag, Folder, Grid2x2, Image, KeyRound, Laptop, Layers, Lightbulb, List, ListChecks, ListTree, Lock, Monitor, Network, Package, Puzzle, Rocket, RotateCcw, Route, Server, Settings, Shield, Smartphone, SquareStack, SquareTerminal, Table, Terminal, TriangleAlert, User, Users, Waypoints, Webhook, Workflow, Zap } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// Tipos de escena y los 35 íconos del backend (estilo.NOMBRES_ICONOS), según el sistema de diseño.
const iconos: Record<string, LucideIcon> = {
  portada: Clapperboard, idea: Lightbulb, lista: List, archivos: Files, diagrama: Workflow, grafo: Waypoints, arreglo: Brackets, arbol: ListTree,
  pila: SquareStack, codigo: Code, grafo_traza: Route, arreglo_traza: ChartNoAxesColumn, lista_traza: ListChecks, terminal: Terminal, tabla: Table,
  capas: Layers, piezas: Puzzle, cierre: Flag,
  alerta: TriangleAlert, api: Webhook, archivo: File, base_datos: Database, candado: Lock, carpeta: Folder, check: CircleCheck, chip_ia: Cpu,
  cohete: Rocket, contenedor: Box, descarga: Download, docker: Container, engranaje: Settings, escudo: Shield, grupo: Users, imagen: Image,
  linux: SquareTerminal, llave: KeyRound, navegador: AppWindow, nube: Cloud, paquete: Package, pantalla: Monitor, portatil: Laptop, rayo: Zap,
  red: Network, registro: Archive, reinicio: RotateCcw, reloj: Clock, servidor: Server, telefono: Smartphone, usuario: User, windows: Grid2x2,
};
export function Icono({ nombre, size = 20 }: {nombre: string; size?: number}) {
  const Componente = iconos[nombre] ?? File;
  return <Componente size={size} aria-hidden="true" />;
}
