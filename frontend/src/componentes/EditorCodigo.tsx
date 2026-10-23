import { useEffect, useRef } from 'react';
import { EditorView, basicSetup } from 'codemirror';
import { EditorState } from '@codemirror/state';
import { json } from '@codemirror/lang-json';
import { languages } from '@codemirror/language-data';
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language';
import { tags } from '@lezer/highlight';

// Paleta de los videos (tokens sintaxis-*), sobre el fondo de la terminal.
const tema = EditorView.theme({
  '&': { backgroundColor: 'var(--terminal)', color: 'var(--sintaxis-nombre)', fontSize: '14px', borderRadius: 'var(--radio-marco)' },
  '.cm-content': { fontFamily: 'var(--font-codigo)', padding: '12px 0', caretColor: 'var(--azul)' },
  '.cm-gutters': { backgroundColor: 'var(--terminal)', color: 'var(--gris)', border: 'none' },
  '&.cm-focused': { outline: '2px solid var(--foco)', outlineOffset: '2px' },
  '.cm-activeLine, .cm-activeLineGutter': { backgroundColor: 'var(--barra)' },
  '.cm-cursor': { borderLeftColor: 'var(--azul)' },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection': { backgroundColor: 'var(--barra)' },
  '.cm-scroller': { overflow: 'auto', maxHeight: '600px', fontFamily: 'var(--font-codigo)', lineHeight: '1.6' },
}, { dark: true });
const colores = syntaxHighlighting(HighlightStyle.define([
  { tag: tags.keyword, color: 'var(--sintaxis-palabra-clave)' }, { tag: [tags.string, tags.special(tags.string)], color: 'var(--sintaxis-cadena)' },
  { tag: [tags.number, tags.bool, tags.null], color: 'var(--sintaxis-numero)' }, { tag: tags.comment, color: 'var(--sintaxis-comentario)' },
  { tag: [tags.operator, tags.punctuation, tags.bracket], color: 'var(--sintaxis-operador)' }, { tag: [tags.function(tags.variableName), tags.function(tags.propertyName)], color: 'var(--sintaxis-funcion)' },
  { tag: [tags.name, tags.propertyName, tags.variableName], color: 'var(--sintaxis-nombre)' }, { tag: tags.standard(tags.variableName), color: 'var(--sintaxis-builtin)' },
]));
export function EditorCodigo({ valor, cambiar, lenguaje = 'json', etiqueta = 'Editor de código' }: {valor: string; cambiar?: (valor: string) => void; lenguaje?: string; etiqueta?: string}) {
  const contenedor = useRef<HTMLDivElement>(null);
  const vista = useRef<EditorView | null>(null);
  const callback = useRef(cambiar); callback.current = cambiar;
  useEffect(() => {
    if (!contenedor.current) return;
    let cancelado = false;
    const crear = async () => {
      const soporte = lenguaje === 'json' ? json() : await languages.find(l => l.name.toLowerCase() === lenguaje.toLowerCase() || l.alias.includes(lenguaje))?.load();
      if (cancelado || !contenedor.current) return;
      vista.current = new EditorView({ parent: contenedor.current, state: EditorState.create({ doc: valor, extensions: [basicSetup, tema, colores, ...(soporte ? [soporte] : []), EditorState.readOnly.of(!callback.current), EditorView.editable.of(Boolean(callback.current)), EditorView.contentAttributes.of({ 'aria-label': etiqueta }), EditorView.updateListener.of(u => { if (u.docChanged) callback.current?.(u.state.doc.toString()); })] }) });
    };
    void crear();
    return () => { cancelado = true; vista.current?.destroy(); vista.current = null; };
    // El documento se sincroniza por separado para conservar cursor y deshacer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lenguaje, etiqueta]);
  useEffect(() => { const editor = vista.current; if (editor && editor.state.doc.toString() !== valor) editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: valor } }); }, [valor]);
  return <div className="vc-editor-codigo" ref={contenedor}/>;
}
