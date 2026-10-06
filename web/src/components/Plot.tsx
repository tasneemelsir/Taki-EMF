// Plotly wrapper: themed base layout, responsive, and click / hover callbacks.

import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-cartesian-dist-min';
import { cssVar } from '@/lib/colors';
import { useStore } from '@/lib/store';

export const PLOT_FONT = 'Segoe UI, Helvetica Neue, Arial, sans-serif';
export const PLOT_MONO = 'SF Mono, Consolas, Roboto Mono, monospace';

export function themeColors() {
  return {
    ink: cssVar('--ink'), blue: cssVar('--blue'), blueBright: cssVar('--blue-bright'), steel: cssVar('--steel'),
    line: cssVar('--line'), card: cssVar('--card'), green: cssVar('--green'), amber: cssVar('--amber'),
    red: cssVar('--red'), violet: cssVar('--violet'), teal: cssVar('--teal'), tealBright: cssVar('--teal-bright'),
    surface: cssVar('--surface'), phase: { A: cssVar('--phase-a'), B: cssVar('--phase-b'), C: cssVar('--phase-c') } as Record<string, string>,
  };
}

export function axis(title?: string, over: Record<string, unknown> = {}) {
  const c = themeColors();
  return {
    title: title ? { text: title, font: { family: PLOT_FONT, size: 12, color: c.steel }, standoff: 8 } : undefined,
    showgrid: true, gridcolor: c.line, gridwidth: 1, zeroline: true, zerolinecolor: c.steel, zerolinewidth: 1,
    linecolor: c.line, ticks: 'outside', ticklen: 4, tickcolor: c.line, automargin: true,
    tickfont: { family: PLOT_MONO, size: 11, color: c.steel }, ...over,
  };
}

export function baseLayout(over: Record<string, unknown> = {}) {
  const c = themeColors();
  return {
    plot_bgcolor: c.card, paper_bgcolor: 'rgba(0,0,0,0)',
    font: { family: PLOT_FONT, color: c.ink, size: 13 },
    margin: { l: 58, r: 22, t: 16, b: 46 },
    legend: { orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'left', x: 0, font: { size: 11, color: c.steel }, bgcolor: 'rgba(0,0,0,0)' },
    modebar: { bgcolor: 'rgba(0,0,0,0)', color: c.steel, activecolor: c.blueBright, orientation: 'h' },
    // the text colour is set outright: left to Plotly it is picked against the trace colour, not this background
    hoverlabel: { font: { family: PLOT_MONO, size: 12, color: c.ink }, bgcolor: c.card, bordercolor: c.steel, align: 'left' },
    hovermode: 'closest', dragmode: 'pan', ...over,
  };
}

interface Props {
  data: any[];
  layout?: Record<string, unknown>;
  height?: number | string;
  onClick?: (pt: { x: number; y: number; curve: number; index: number; raw: any }) => void;
  onHover?: (pt: { x: number; y: number } | null) => void;
  toolbar?: boolean;
  filename?: string;
  className?: string;
}

export function Plot({ data, layout, height = 420, onClick, onHover, toolbar = true, filename = 'taki-chart', className }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const theme = useStore((s) => s.theme);
  const clickRef = useRef(onClick); clickRef.current = onClick;
  const hoverRef = useRef(onHover); hoverRef.current = onHover;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const config = {
      displaylogo: false, responsive: true, displayModeBar: toolbar ? 'hover' : false, scrollZoom: true,
      modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d', 'toggleSpikelines', 'hoverCompareCartesian', 'hoverClosestCartesian'],
      toImageButtonOptions: { format: 'png', filename, scale: 2 },
    };
    Plotly.react(el, data, { ...baseLayout(), ...(layout ?? {}), autosize: true }, config);
    const anyEl = el as any;
    anyEl.removeAllListeners?.('plotly_click');
    anyEl.removeAllListeners?.('plotly_hover');
    anyEl.removeAllListeners?.('plotly_unhover');
    anyEl.on?.('plotly_click', (ev: any) => {
      const p = ev?.points?.[0];
      if (p && clickRef.current) clickRef.current({ x: p.x, y: p.y, curve: p.curveNumber, index: p.pointNumber, raw: p });
    });
    anyEl.on?.('plotly_hover', (ev: any) => { const p = ev?.points?.[0]; if (p && hoverRef.current) hoverRef.current({ x: p.x, y: p.y }); });
    anyEl.on?.('plotly_unhover', () => hoverRef.current?.(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, layout, theme, toolbar, filename]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => { try { Plotly.Plots.resize(el); } catch { /* not ready */ } });
    ro.observe(el);
    return () => { ro.disconnect(); try { Plotly.purge(el); } catch { /* already gone */ } };
  }, []);

  return <div ref={ref} className={`plot ${className ?? ''}`} style={{ height }} />;
}
