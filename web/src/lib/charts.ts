// Figure builders: they turn API results into Plotly traces and layouts.
// Shared conventions: the right-of-way is drawn as the same shaded band on
// every chart; limit lines come from the selected standards; phases use the
// red / yellow / blue electrical convention.

import { axis, baseLayout, PLOT_MONO, themeColors } from '@/components/Plot';
import { DIFF_SCALE, DIFF_SCALE_DARK, PLOTLY_CIVIDIS } from './colors';
import type { ELines } from './elines';
import type { LineOut, Pin, Solution, StdResult } from './types';

export interface Fig { data: any[]; layout: Record<string, unknown> }

function isDark() { return document.documentElement.dataset.theme === 'dark'; }

export function rowBand(rowHalf: number | null | undefined): { shapes: any[]; annotations: any[] } {
  if (!rowHalf) return { shapes: [], annotations: [] };
  const c = themeColors();
  return {
    shapes: [
      { type: 'rect', xref: 'x', yref: 'paper', x0: -rowHalf, x1: rowHalf, y0: 0, y1: 1, fillcolor: c.blue, opacity: 0.06, line: { width: 0 }, layer: 'below' },
      ...[-1, 1].map((s) => ({ type: 'line', xref: 'x', yref: 'paper', x0: s * rowHalf, x1: s * rowHalf, y0: 0, y1: 1, line: { color: c.steel, width: 1, dash: 'dot' }, opacity: 0.55 })),
    ],
    annotations: [{ xref: 'x', yref: 'paper', x: -rowHalf, y: 1, xanchor: 'left', yanchor: 'top', text: ` ROW ±${rowHalf} m`, showarrow: false, font: { size: 10, color: c.steel, family: PLOT_MONO } }],
  };
}

export function limitLines(results: StdResult[] | undefined, q: 'B' | 'E', yref = 'y', maxShown = Infinity): { shapes: any[]; annotations: any[] } {
  const c = themeColors();
  const byValue = new Map<number, string[]>();
  for (const r of results ?? []) {
    const lim = q === 'B' ? r.b.limit : r.e.limit;
    if (lim === null || lim === undefined) continue;
    byValue.set(lim, [...(byValue.get(lim) ?? []), r.name]);
  }
  const shapes: any[] = [], annotations: any[] = [];
  [...byValue.entries()].sort((a, b) => a[0] - b[0]).forEach(([lim, names]) => {
    if (lim > maxShown) return;
    const label = names.length === 1 ? names[0] : `${names[0]} +${names.length - 1}`;
    shapes.push({ type: 'line', xref: 'paper', yref, x0: 0, x1: 1, y0: lim, y1: lim, line: { color: c.red, width: 1.3, dash: 'dash' } });
    annotations.push({ xref: 'paper', yref, x: 0.005, y: lim, xanchor: 'left', yanchor: 'bottom', showarrow: false, text: `${label} — ${lim} ${q === 'B' ? 'µT' : 'kV/m'}`, font: { size: 10, color: c.red, family: PLOT_MONO } });
  });
  return { shapes, annotations };
}

function niceMax(v: number) { return v > 0 ? v * 1.14 : 1; }

/** Top of a y axis: the data, stretched to take in the tightest limit when that limit is close (within 3x). */
function topWithLimit(dataMax: number, results: StdResult[] | undefined, q: 'B' | 'E'): number {
  let tight = Infinity;
  for (const r of results ?? []) { const l = q === 'B' ? r.b.limit : r.e.limit; if (l !== null && l !== undefined && l < tight) tight = l; }
  return niceMax(tight <= 3 * dataMax ? Math.max(dataMax, tight) : dataMax);
}

export function profileFigure(sol: Solution, opts: { shield?: boolean; logY?: boolean; showE?: boolean; showB?: boolean; measured?: { x: number[]; y: number[]; name: string } | null } = {}): Fig {
  const c = themeColors();
  const p = sol.profile;
  const showB = opts.showB !== false, showE = opts.showE !== false;
  const withShield = !!opts.shield && sol.shield.on;
  const data: any[] = [];
  if (showB) data.push({ x: p.x, y: p.b0, mode: 'lines', name: 'B field', line: { color: c.blue, width: 2.6 }, yaxis: 'y', hovertemplate: 'x %{x:.1f} m<br>B %{y:.3f} µT<extra></extra>' });
  if (showE) data.push({ x: p.x, y: p.e0, mode: 'lines', name: 'E field', line: { color: c.blueBright, width: 1.8, dash: 'dot' }, yaxis: showB ? 'y2' : 'y', hovertemplate: 'x %{x:.1f} m<br>E %{y:.3f} kV/m<extra></extra>' });
  if (withShield && showB) data.push({ x: p.x, y: p.bS, mode: 'lines', name: 'B · with shield', line: { color: c.green, width: 2.3 }, yaxis: 'y', hovertemplate: 'x %{x:.1f} m<br>B with shield %{y:.3f} µT<extra></extra>' });
  if (withShield && showE) data.push({ x: p.x, y: p.eS, mode: 'lines', name: 'E · with shield', line: { color: c.green, width: 1.6, dash: 'dot' }, yaxis: showB ? 'y2' : 'y', hovertemplate: 'x %{x:.1f} m<br>E with shield %{y:.3f} kV/m<extra></extra>' });
  if (opts.measured && opts.measured.x.length) data.push({ x: opts.measured.x, y: opts.measured.y, mode: 'markers', name: opts.measured.name, marker: { color: c.ink, size: 8, line: { color: c.card, width: 1.2 } }, yaxis: 'y' });

  const band = rowBand(sol.corridor.row_half);
  const bMax = Math.max(...p.b0, ...(withShield ? p.bS : [0]));
  const eMax = Math.max(...p.e0, ...(withShield ? p.eS : [0]));
  const lim = limitLines(sol.results, showB ? 'B' : 'E', 'y');
  // where the profile meets the shield: a tick for an upright sheet, a bar along the axis for a floor or roof
  const walls = withShield ? sol.shield.walls.map((w) => (Math.abs(w[0] - w[2]) < 0.05
    ? { type: 'line', xref: 'x', yref: 'paper', x0: w[0], x1: w[2], y0: 0, y1: 0.1, line: { color: c.tealBright, width: 4 } }
    : { type: 'line', xref: 'x', yref: 'paper', x0: w[0], x1: w[2], y0: 0.006, y1: 0.006, line: { color: c.tealBright, width: 3 } })) : [];
  const type = opts.logY ? 'log' : 'linear';
  const layout: Record<string, unknown> = {
    ...baseLayout({ margin: { l: 58, r: showB && showE ? 58 : 22, t: 22, b: 46 } }),
    xaxis: axis('Lateral distance from centreline (m)', { zeroline: false }),
    yaxis: axis(showB ? 'B field (µT)' : 'E field (kV/m)', { type, range: opts.logY ? undefined : [0, showB ? topWithLimit(bMax, sol.results, 'B') : topWithLimit(eMax, sol.results, 'E')], rangemode: 'tozero' }),
    shapes: [...band.shapes, ...lim.shapes, ...walls],
    annotations: [...band.annotations, ...lim.annotations],
  };
  if (showB && showE) layout.yaxis2 = axis('E field (kV/m)', { overlaying: 'y', side: 'right', showgrid: false, type, range: opts.logY ? undefined : [0, niceMax(eMax)], rangemode: 'tozero' });
  return { data, layout };
}

export interface SectionDeco {
  lines?: LineOut[];
  walls?: number[][] | null;
  wires?: number[][] | null;
  buildings?: { x0: number; x1: number; h: number; name: string }[];
  rowHalf?: number | null;
  pins?: Pin[];
  obs?: { x: number; y: number } | null;
  refPoint?: number[] | null;
}

function sectionDeco(d: SectionDeco, onDark: boolean) {
  const c = themeColors();
  const shapes: any[] = [], annotations: any[] = [], traces: any[] = [];
  const edge = onDark ? '#FFFFFF' : c.ink;
  for (const b of d.buildings ?? []) {
    shapes.push({ type: 'rect', xref: 'x', yref: 'y', x0: Math.min(b.x0, b.x1), x1: Math.max(b.x0, b.x1), y0: 0, y1: b.h, line: { color: edge, width: 1.3 }, fillcolor: onDark ? 'rgba(255,255,255,0.10)' : 'rgba(15,27,36,0.10)', layer: 'above' });
    annotations.push({ x: (b.x0 + b.x1) / 2, y: b.h, text: b.name, showarrow: false, yshift: 9, font: { size: 10, color: edge } });
  }
  for (const w of d.walls ?? []) traces.push({ x: [w[0], w[2]], y: [w[1], w[3]], mode: 'lines', line: { color: '#00D8CE', width: 5 }, showlegend: false, hovertemplate: 'Shield<extra></extra>', name: 'Shield' });
  if (d.wires?.length) traces.push({ x: d.wires.map((w) => w[0]), y: d.wires.map((w) => w[1]), mode: 'markers', showlegend: false, name: 'Shield conductors',
    marker: { symbol: 'circle-open', size: 11, line: { color: '#00D8CE', width: 2.5 } }, hovertemplate: 'Shield conductor<br>x %{x:.1f} m · y %{y:.1f} m<extra></extra>' });
  const conds = (d.lines ?? []).flatMap((l) => l.conductors.map((k) => ({ ...k, line: l.name })));
  if (conds.length) traces.push({
    x: conds.map((k) => k.x), y: conds.map((k) => k.y), mode: 'markers', name: 'Conductors', showlegend: false,
    text: conds.map((k) => `${k.line} · phase ${k.phase} (circuit ${k.circuit})${k.on === false ? ' · out of service' : ''}`),
    marker: { color: conds.map((k) => (k.on === false ? '#9AA3AA' : c.phase[k.phase])), size: 9, line: { color: '#FFFFFF', width: 1.2 } },
    hovertemplate: '%{text}<br>x %{x:.2f} m · y %{y:.2f} m<extra></extra>',
  });
  if (d.rowHalf) for (const s of [-1, 1]) shapes.push({ type: 'line', xref: 'x', yref: 'y', x0: s * d.rowHalf, x1: s * d.rowHalf, y0: 0, y1: 1e4, line: { color: onDark ? '#FFFFFF' : c.steel, width: 1, dash: 'dot' }, opacity: 0.7 });
  if (d.pins?.length) traces.push({
    x: d.pins.map((p) => p.x), y: d.pins.map((p) => p.y), mode: 'markers+text', text: d.pins.map((_, i) => String(i + 1)), textposition: 'top center',
    textfont: { size: 11, color: onDark ? '#FFFFFF' : c.ink }, name: 'Points', showlegend: false,
    marker: { color: '#FFFFFF', size: 10, line: { color: '#0F1B24', width: 2 } }, hovertemplate: 'Point %{text}<br>x %{x:.1f} m · y %{y:.1f} m<extra></extra>',
  });
  if (d.obs) traces.push({ x: [d.obs.x], y: [d.obs.y], mode: 'markers', showlegend: false, name: 'Observation point', marker: { symbol: 'cross-thin-open', size: 16, line: { color: '#FFFFFF', width: 2.5 } }, hovertemplate: 'Observation point<extra></extra>' });
  if (d.refPoint) traces.push({ x: [d.refPoint[0]], y: [d.refPoint[1]], mode: 'markers', showlegend: false, name: 'Reference point', marker: { symbol: 'diamond-open', size: 11, line: { color: '#FFFFFF', width: 2 } }, hovertemplate: 'Probe point (one-point read-out)<extra></extra>' });
  return { shapes, annotations, traces };
}

/**
 * The colour range of a field map, from the unshielded picture. The top is the level 99.5 % of the
 * picture lies below: the few cells that touch a conductor would otherwise stretch the scale and leave
 * everything else dark. The bottom is its lowest level, at most four decades down. A shielded space
 * falls below the scale and shows as the darkest colour. (engine/report_figures.py does the same.)
 */
export function mapRange(z0: number[][]): { lo: number; hi: number } {
  const flat: number[] = [];
  for (const row of z0) for (const v of row) if (v > 0 && Number.isFinite(v)) flat.push(v);
  if (!flat.length) return { lo: 1e-3, hi: 1 };
  flat.sort((a, b) => a - b);
  const at = (p: number) => {
    const t = p * (flat.length - 1), i = Math.floor(t), f = t - i;
    return i + 1 < flat.length ? flat[i] * (1 - f) + flat[i + 1] * f : flat[i];
  };
  const hi = at(0.995);
  const lo = Math.max(at(0.005), hi * 1e-4);
  return lo < hi ? { lo, hi } : { lo: hi * 1e-3, hi };
}

/** Round tick values for a logarithmic colour bar between lo and hi: 1-2-5 steps, thinned to decades when crowded. */
export function logTicks(lo: number, hi: number): number[] {
  const out: number[] = [];
  for (let k = Math.floor(Math.log10(lo)); k <= Math.ceil(Math.log10(hi)); k++)
    for (const m of [1, 2, 5]) { const v = m * Math.pow(10, k); if (v >= lo * 0.999 && v <= hi * 1.001) out.push(v); }
  if (out.length <= 7) return out.length >= 2 ? out : [lo, hi];
  const decades = out.filter((v) => Math.abs(Math.log10(v) - Math.round(Math.log10(v))) < 1e-9);
  return decades.length >= 2 ? decades : out.filter((_, i) => i % 2 === 0);
}

export function fieldMapFigure(g: { x: number[]; y: number[]; z0: number[][]; zS: number[][] }, opts: {
  quantity: 'B' | 'E'; view: 'without' | 'with' | 'diff'; log?: boolean; deco?: SectionDeco; showScale?: boolean; height?: number;
  /** one metre up = one metre across. Off (the default) the map fills its panel, which stretches heights. */
  trueScale?: boolean;
}): Fig {
  const c = themeColors();
  const unit = opts.quantity === 'B' ? 'µT' : 'kV/m';
  const cbFont = { family: PLOT_MONO, size: 10, color: c.steel };
  const data: any[] = [];
  const { lo, hi: vmax } = mapRange(g.z0);
  if (opts.view === 'diff') {
    const pct = g.z0.map((row, j) => row.map((v, i) => (v > 1e-12 ? ((g.zS[j][i] - v) / v) * 100 : 0)));
    let lim = 5;
    for (const row of pct) for (const v of row) if (Math.abs(v) > lim) lim = Math.abs(v);
    lim = Math.min(lim, 100);
    data.push({ type: 'heatmap', x: g.x, y: g.y, z: pct, zmin: -lim, zmax: lim, zmid: 0, zsmooth: 'best', colorscale: isDark() ? DIFF_SCALE_DARK : DIFF_SCALE,
      showscale: opts.showScale !== false, colorbar: { title: { text: 'Change (%)', font: { size: 11, color: c.steel } }, tickfont: cbFont, thickness: 12, len: 0.9, outlinewidth: 0 },
      hovertemplate: 'x %{x:.1f} m · y %{y:.1f} m<br>%{z:+.1f}%<extra></extra>' });
  } else {
    const z = opts.view === 'with' ? g.zS : g.z0;
    if (opts.log !== false) {
      const zl = z.map((row) => row.map((v) => Math.log10(Math.min(Math.max(v, lo), vmax))));
      const ticks = logTicks(lo, vmax);
      data.push({ type: 'heatmap', x: g.x, y: g.y, z: zl, customdata: z, zmin: Math.log10(lo), zmax: Math.log10(vmax), zsmooth: 'best', colorscale: PLOTLY_CIVIDIS,
        showscale: opts.showScale !== false, colorbar: { title: { text: `${opts.quantity} (${unit}), log`, font: { size: 11, color: c.steel } }, tickvals: ticks.map((t) => Math.log10(t)), ticktext: ticks.map((t) => Number(t.toPrecision(2)).toString()), tickfont: cbFont, thickness: 12, len: 0.9, outlinewidth: 0 },
        hovertemplate: `x %{x:.1f} m · y %{y:.1f} m<br>%{customdata:.3f} ${unit}<extra></extra>` });
    } else {
      data.push({ type: 'heatmap', x: g.x, y: g.y, z, zmin: 0, zmax: vmax, zsmooth: 'best', colorscale: PLOTLY_CIVIDIS,
        showscale: opts.showScale !== false, colorbar: { title: { text: `${opts.quantity} (${unit})`, font: { size: 11, color: c.steel } }, tickfont: cbFont, thickness: 12, len: 0.9, outlinewidth: 0 },
        hovertemplate: `x %{x:.1f} m · y %{y:.1f} m<br>%{z:.3f} ${unit}<extra></extra>` });
    }
  }
  const deco = sectionDeco(opts.deco ?? {}, opts.view !== 'diff' || isDark());
  data.push(...deco.traces);
  const layout = {
    ...baseLayout({ margin: { l: 52, r: 12, t: 12, b: 44 }, showlegend: false }),
    xaxis: axis('Lateral distance (m)', { showgrid: false, zeroline: false, range: [g.x[0], g.x[g.x.length - 1]] }),
    yaxis: axis('Height above ground (m)', { showgrid: false, zeroline: false, range: [0, g.y[g.y.length - 1]],
      ...(opts.trueScale ? { scaleanchor: 'x', scaleratio: 1, constrain: 'domain' } : {}) }),
    shapes: deco.shapes, annotations: deco.annotations,
  };
  return { data, layout };
}

export function envelopeFigure(env: { x: number[]; free: number[]; perfect: number[]; selected: number[] | null; selected_label: string }, sol: Solution): Fig {
  const c = themeColors();
  const up = env.free.map((v, i) => Math.max(v, env.perfect[i]));
  const lo = env.free.map((v, i) => Math.min(v, env.perfect[i]));
  const data: any[] = [
    { x: [...env.x, ...[...env.x].reverse()], y: [...up, ...[...lo].reverse()], fill: 'toself', fillcolor: isDark() ? 'rgba(111,182,242,0.14)' : 'rgba(0,75,135,0.10)', line: { width: 0 }, hoverinfo: 'skip', name: 'Earth-return envelope' },
    { x: env.x, y: env.perfect, mode: 'lines', name: 'Perfectly conducting earth', line: { color: c.blue, width: 2 }, hovertemplate: 'x %{x:.1f} m<br>%{y:.3f} µT<extra>conducting</extra>' },
    { x: env.x, y: env.free, mode: 'lines', name: 'Free space (no earth return)', line: { color: c.steel, width: 1.8, dash: 'dash' }, hovertemplate: 'x %{x:.1f} m<br>%{y:.3f} µT<extra>free space</extra>' },
  ];
  if (env.selected) data.push({ x: env.x, y: env.selected, mode: 'lines', name: env.selected_label || 'Selected model', line: { color: c.violet, width: 2.4, dash: 'dot' } });
  const band = rowBand(sol.corridor.row_half), lim = limitLines(sol.results, 'B');
  return { data, layout: { ...baseLayout({ margin: { l: 58, r: 22, t: 22, b: 46 } }), xaxis: axis('Lateral distance from centreline (m)', { zeroline: false }), yaxis: axis('B field (µT)', { rangemode: 'tozero', range: [0, topWithLimit(Math.max(...up), sol.results, 'B')] }), shapes: [...band.shapes, ...lim.shapes], annotations: [...band.annotations, ...lim.annotations] } };
}

export function barFigure(labels: string[], values: number[], opts: { ytitle: string; baseline?: number | null; baselineLabel?: string; color?: string; unit?: string; second?: { values: number[]; name: string; color?: string }; name?: string } ): Fig {
  const c = themeColors();
  const data: any[] = [{ type: 'bar', x: labels, y: values, name: opts.name ?? opts.ytitle, marker: { color: opts.color ?? c.blue }, hovertemplate: `%{x}<br>%{y:.4g} ${opts.unit ?? ''}<extra></extra>` }];
  if (opts.second) data.push({ type: 'bar', x: labels, y: opts.second.values, name: opts.second.name, marker: { color: opts.second.color ?? c.teal }, hovertemplate: `%{x}<br>%{y:.4g} ${opts.unit ?? ''}<extra></extra>` });
  const shapes: any[] = [], annotations: any[] = [];
  if (opts.baseline !== null && opts.baseline !== undefined) {
    shapes.push({ type: 'line', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: opts.baseline, y1: opts.baseline, line: { color: c.red, width: 1.2, dash: 'dash' } });
    annotations.push({ xref: 'paper', yref: 'y', x: 0.005, y: opts.baseline, xanchor: 'left', yanchor: 'bottom', showarrow: false, text: opts.baselineLabel ?? 'unshielded', font: { size: 10, color: c.red, family: PLOT_MONO } });
  }
  return { data, layout: { ...baseLayout({ margin: { l: 58, r: 16, t: 22, b: 70 }, showlegend: !!opts.second, barmode: 'group', dragmode: false }), xaxis: axis(undefined, { showgrid: false, tickangle: labels.some((l) => l.length > 9) ? -28 : 0, tickfont: { size: 10.5, color: c.steel } }), yaxis: axis(opts.ytitle, { rangemode: 'tozero' }), shapes, annotations } };
}

/**
 * How the potential is mapped before it is contoured in the "show weak field" view: linear below
 * scale / softness, logarithmic above. The server works the softness out from the picture
 * (engine/field_lines.py explains why).
 */
function spread(a: number, scale: number, softness: number): number {
  const v = Math.log1p(Math.abs(a) / (scale / softness)) / Math.log1p(softness);
  return a < 0 ? -v : v;
}

export interface PotentialGrid { x: number[]; y: number[]; nx: number; ny: number; re: Float32Array; im: Float32Array }

/** The potential at the instant ωt = phase, as rows for Plotly; `even` applies the symmetric-log spacing. */
export function potentialAt(g: PotentialGrid, phaseDeg: number, scale: number, even: boolean, softness = 400): number[][] {
  const c = Math.cos((phaseDeg * Math.PI) / 180), s = Math.sin((phaseDeg * Math.PI) / 180);
  const rows: number[][] = new Array(g.ny);
  for (let j = 0; j < g.ny; j++) {
    const row = new Array<number>(g.nx);
    const o = j * g.nx;
    for (let i = 0; i < g.nx; i++) {
      const a = g.re[o + i] * c - g.im[o + i] * s;
      row[i] = even ? spread(a, scale, softness) : a;
    }
    rows[j] = row;
  }
  return rows;
}

/**
 * Arrowheads on the field lines. z is the contoured quantity; its contours are lines of B and
 * B = (∂z/∂y, −∂z/∂x) up to a positive factor, so the direction comes straight from z.
 * Each arrow starts on a coarse grid and is slid onto the nearest drawn line. The lines are drawn
 * at odd half-steps, (k + ½)·step up to ±top, so those are the levels an arrow may land on.
 */
function lineArrows(g: PotentialGrid, z: number[][], step: number, top: number): { x: number[]; y: number[]; angle: number[] } {
  const level = (v: number) => (Math.floor(v / step) + 0.5) * step;
  const out = { x: [] as number[], y: [] as number[], angle: [] as number[] };
  const dx = g.x[1] - g.x[0], dy = g.y[1] - g.y[0];
  const at = (fi: number, fj: number) => {
    const i = Math.max(0, Math.min(g.nx - 2, Math.floor(fi))), j = Math.max(0, Math.min(g.ny - 2, Math.floor(fj)));
    const u = fi - i, v = fj - j;
    return z[j][i] * (1 - u) * (1 - v) + z[j][i + 1] * u * (1 - v) + z[j + 1][i] * (1 - u) * v + z[j + 1][i + 1] * u * v;
  };
  const NX = 15, NY = 6;
  for (let b = 1; b <= NY; b++) for (let a = 1; a <= NX; a++) {
    let fi = ((a - (b % 2 ? 0 : 0.5)) / (NX + 1)) * (g.nx - 1), fj = (b / (NY + 1)) * (g.ny - 1);
    let gx = 0, gy = 0;
    for (let it = 0; it < 6; it++) {                       // slide onto the nearest contour level
      gx = (at(fi + 0.5, fj) - at(fi - 0.5, fj)) / dx; gy = (at(fi, fj + 0.5) - at(fi, fj - 0.5)) / dy;
      const g2 = gx * gx + gy * gy;
      if (!(g2 > 0)) break;
      const z0 = at(fi, fj), want = level(z0);
      const mx = ((want - z0) * gx) / g2, my = ((want - z0) * gy) / g2;   // metres
      const lim = Math.max(dx, dy) * 3, len = Math.hypot(mx, my);
      const k = len > lim ? lim / len : 1;
      fi += (mx * k) / dx; fj += (my * k) / dy;
    }
    if (fi < 1 || fi > g.nx - 2 || fj < 1 || fj > g.ny - 2) continue;
    const mag = Math.hypot(gx, gy);
    if (!(mag > 0)) continue;
    const z0 = at(fi, fj), lv = level(z0);
    if (Math.abs(z0 - lv) > 0.04 * step || Math.abs(lv) > top) continue;       // did not land on a drawn line
    const ax = g.x[0] + fi * dx, ay = g.y[0] + fj * dy;
    let crowded = false;                                                       // two arrows slid to the same spot
    for (let k = 0; k < out.x.length && !crowded; k++) crowded = Math.hypot(out.x[k] - ax, out.y[k] - ay) < 4 * Math.max(dx, dy);
    if (crowded) continue;
    out.x.push(ax); out.y.push(ay);
    out.angle.push((Math.atan2(gy, -gx) * 180) / Math.PI);                   // clockwise from up, for B = (gy, −gx)
  }
  return out;
}

export function fieldLinesFigure(g: PotentialGrid, opts: {
  z: number[][]; ref?: number[][] | null; even: boolean; scale: number; lines: number; deco: SectionDeco; yMax: number;
}): Fig {
  const c = themeColors();
  const N = Math.max(4, Math.round(opts.lines));
  const top = opts.even ? 1 : opts.scale;
  const size = top / N;
  // an odd half-step keeps the zero contour (a line that never closes neatly) out of the picture
  const levels = { start: -top + size / 2, end: top - size / 2, size, coloring: 'none', showlabels: false };
  const data: any[] = [];
  if (opts.ref) data.push({ type: 'contour', x: g.x, y: g.y, z: opts.ref, autocontour: false, contours: levels, showscale: false, hoverinfo: 'skip',
    line: { color: c.steel, width: 0.9, dash: 'dot', smoothing: 0.85 }, name: 'Without the shield', showlegend: true });
  data.push({ type: 'contour', x: g.x, y: g.y, z: opts.z, autocontour: false, contours: levels, showscale: false, hoverinfo: 'skip',
    line: { color: c.blue, width: 1.25, smoothing: 0.85 }, name: opts.ref ? 'With the shield' : 'Field lines', showlegend: !!opts.ref });
  const ar = lineArrows(g, opts.z, size, top);
  if (ar.x.length) data.push({ x: ar.x, y: ar.y, mode: 'markers', hoverinfo: 'skip', showlegend: false,
    marker: { symbol: 'arrow', size: 10, angle: ar.angle, angleref: 'up', color: c.blue, line: { width: 0 } } });
  const d = sectionDeco(opts.deco, isDark());
  data.push(...d.traces);
  return { data, layout: {
    ...baseLayout({ margin: { l: 52, r: 16, t: opts.ref ? 30 : 12, b: 44 }, showlegend: !!opts.ref }),
    xaxis: axis('Lateral distance (m)', { range: [g.x[0], g.x[g.x.length - 1]], zeroline: false, showgrid: false }),
    yaxis: axis('Height above ground (m)', { range: [0, opts.yMax], scaleanchor: 'x', scaleratio: 1, constrain: 'domain', showgrid: false }),
    shapes: d.shapes, annotations: d.annotations } };
}

/**
 * Electric field lines (traced in lib/elines.ts) over the equipotentials. The field crosses an
 * equipotential at right angles; they are spaced like the "show weak field" magnetic lines, so the
 * weak field near a building shows even where no field line reaches.
 */
export function electricLinesFigure(g: { x: number[]; y: number[] }, opts: {
  lines: ELines; ref?: ELines | null; eq?: number[][] | null; eqLines: number; deco: SectionDeco; yMax: number;
}): Fig {
  const c = themeColors();
  const data: any[] = [];
  if (opts.eq) {
    const N = Math.max(4, Math.round(opts.eqLines)), size = 1 / N;
    data.push({ type: 'contour', x: g.x, y: g.y, z: opts.eq, autocontour: false, showscale: false, hoverinfo: 'skip',
      contours: { start: -1 + size / 2, end: 1 - size / 2, size, coloring: 'none', showlabels: false },
      line: { color: c.steel, width: 0.8, dash: 'dot', smoothing: 0.85 }, opacity: 0.7, name: 'Equipotentials', showlegend: true });
  }
  if (opts.ref) data.push({ x: opts.ref.x, y: opts.ref.y, mode: 'lines', hoverinfo: 'skip', connectgaps: false,
    line: { color: c.amber, width: 1, dash: 'dash' }, name: 'Without the shield', showlegend: true });
  data.push({ x: opts.lines.x, y: opts.lines.y, mode: 'lines', hoverinfo: 'skip', connectgaps: false,
    line: { color: c.violet, width: 1.35 }, name: opts.ref ? 'With the shield' : 'Field lines', showlegend: true });
  if (opts.lines.ax.length) data.push({ x: opts.lines.ax, y: opts.lines.ay, mode: 'markers', hoverinfo: 'skip', showlegend: false,
    marker: { symbol: 'arrow', size: 9, angle: opts.lines.angle, angleref: 'up', color: c.violet, line: { width: 0 } } });
  const d = sectionDeco(opts.deco, isDark());
  data.push(...d.traces);
  return { data, layout: {
    ...baseLayout({ margin: { l: 52, r: 16, t: 30, b: 44 }, showlegend: true }),
    xaxis: axis('Lateral distance (m)', { range: [g.x[0], g.x[g.x.length - 1]], zeroline: false, showgrid: false }),
    yaxis: axis('Height above ground (m)', { range: [0, opts.yMax], scaleanchor: 'x', scaleratio: 1, constrain: 'domain', showgrid: false }),
    shapes: d.shapes, annotations: d.annotations } };
}

export function overlayFigure(curves: { name: string; x: number[]; y: number[]; dash?: string; ci?: number }[], sol: Solution | null, ytitle = 'B field (µT)', q: 'B' | 'E' = 'B'): Fig {
  const c = themeColors();
  const pal = [c.blue, c.red, c.green, c.violet, c.amber, c.steel, c.teal, c.blueBright];
  const data = curves.map((k, i) => ({ x: k.x, y: k.y, mode: 'lines', name: k.name, line: { color: pal[(k.ci ?? i) % pal.length], width: k.dash ? 1.8 : 2.2, dash: k.dash }, hovertemplate: `${k.name}<br>x %{x:.1f} m<br>%{y:.3f}<extra></extra>` }));
  const band = rowBand(sol?.corridor.row_half), lim = limitLines(sol?.results, q);
  const top = topWithLimit(Math.max(1e-9, ...curves.flatMap((k) => k.y)), sol?.results, q);
  return { data, layout: { ...baseLayout({ margin: { l: 58, r: 22, t: 26, b: 46 } }), xaxis: axis('Lateral distance from centreline (m)', { zeroline: false }), yaxis: axis(ytitle, { rangemode: 'tozero', range: [0, top] }), shapes: [...band.shapes, ...lim.shapes], annotations: [...band.annotations, ...lim.annotations] } };
}

export function validationFigure(curve: { x: number[]; b: number[] }, pts: { distance: number; reference: number }[], refLabel: string, takiLabel = 'Taki (calculated)', mismatch = false): Fig {
  const c = themeColors();
  return {
    data: [
      { x: curve.x, y: curve.b, mode: 'lines', name: takiLabel, line: { color: mismatch ? c.amber : c.blue, width: 2.6, dash: mismatch ? 'dash' : undefined }, hovertemplate: 'x %{x:.1f} m<br>B %{y:.3f} µT<extra></extra>' },
      { x: pts.map((p) => p.distance), y: pts.map((p) => p.reference), mode: 'markers', name: refLabel, marker: { color: c.ink, size: 9, line: { color: c.card, width: 1.4 } }, hovertemplate: 'x %{x:.1f} m<br>B %{y:.3f} µT<extra></extra>' },
    ],
    layout: { ...baseLayout({ margin: { l: 58, r: 22, t: 26, b: 46 } }), xaxis: axis('Lateral distance (m)', { zeroline: false }), yaxis: axis('B field (µT)', { rangemode: 'tozero' }) },
  };
}
