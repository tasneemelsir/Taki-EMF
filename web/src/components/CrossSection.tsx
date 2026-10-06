// 2-D elevation of the corridor at mid-span: towers, conductors (by phase),
// buildings drawn by type, the shield and the right-of-way. The same picture
// the Figma prototype called its "twin", in the Taki palette.

import { useMemo, useState } from 'react';
import { useStore } from '@/lib/store';
import type { BuildingCfg, Solution } from '@/lib/types';
import { Chip } from './ui';

const LAYERS = [['towers', 'Towers'], ['conductors', 'Conductors'], ['buildings', 'Buildings'], ['shield', 'Shield'], ['row', 'Right-of-way'], ['glow', 'Field glow']] as const;
type LayerKey = (typeof LAYERS)[number][0];

type Box = { x0: number; y0: number; x1: number; y1: number };
type Label = { x: number; y: number; text: string; anchor: 'start' | 'middle' | 'end'; size: number; fill: string; weight?: number };
const OFF = '#9AA3AA';

/** Places labels one at a time, each at the first of its candidate spots that is clear of everything placed before. */
class Placer {
  private taken: Box[] = [];
  constructor(private W: number, private H: number) {}
  static box(x: number, y: number, text: string, size: number, anchor: Label['anchor']): Box {
    const w = text.length * size * 0.62 + 3;
    const x0 = anchor === 'middle' ? x - w / 2 : anchor === 'end' ? x - w : x;
    return { x0, x1: x0 + w, y0: y - size, y1: y + 2 };
  }
  block(b: Box) { this.taken.push(b); }
  free(b: Box) { return b.x0 >= 0 && b.x1 <= this.W && b.y0 >= 0 && b.y1 <= this.H && !this.taken.some((t) => b.x0 < t.x1 && b.x1 > t.x0 && b.y0 < t.y1 && b.y1 > t.y0); }
  /** `must` labels are placed at the first candidate even when nothing is free. */
  place(cands: Omit<Label, 'text' | 'size' | 'fill' | 'weight'>[], text: string, size: number, fill: string, weight?: number, must = true): Label | null {
    for (const c of cands) {
      const b = Placer.box(c.x, c.y, text, size, c.anchor);
      if (this.free(b)) { this.taken.push(b); return { ...c, text, size, fill, weight }; }
    }
    if (!must || !cands.length) return null;
    this.taken.push(Placer.box(cands[0].x, cands[0].y, text, size, cands[0].anchor));
    return { ...cands[0], text, size, fill, weight };
  }
}

export function CrossSection({ height = 320, controls = true }: { height?: number; controls?: boolean }) {
  const sol = useStore((s) => s.sol);
  const config = useStore((s) => s.config);
  const lib = useStore((s) => s.library);
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({ towers: true, conductors: true, buildings: true, shield: true, row: true, glow: true });
  const W = 1000;
  const geo = useMemo(() => {
    if (!sol || !config) return null;
    const xMin = sol.domain.x_min, xMax = sol.domain.x_max;
    let top = 12;
    for (const l of sol.lines) for (const c of l.conductors) top = Math.max(top, c.y_att + 6);
    for (const b of config.buildings) top = Math.max(top, b.height + (b.roof === 'pitched' ? b.height * 0.3 : 4) + 3);
    const padL = 34, padR = 10, padT = 16, padB = 32;
    const sx = (W - padL - padR) / (xMax - xMin);
    const H = Math.max(160, Math.min(height, Math.round(top * sx + padT + padB)));
    const sy = (H - padT - padB) / top;
    const s = Math.min(sx, sy);
    const X = (x: number) => padL + (x - xMin) * sx;
    const Y = (y: number) => H - padB - y * s;
    return { xMin, xMax, top, X, Y, H, s, sx, padL, padB };
  }, [sol, config, height]);

  // Every label is placed after the things it must not sit on, at the first clear spot of a few.
  const labels = useMemo(() => {
    if (!sol || !config || !geo) return null;
    const { X, Y, H } = geo;
    const P = new Placer(W, H);
    const ground = Y(0);
    const out: { building: (Label | null)[]; line: (Label | null)[]; phase: (Label | null)[][]; row: Label | null; shield: Label | null; meas: Label } = {
      building: [], line: [], phase: [], row: null, shield: null,
      meas: { x: X(geo.xMin) + 4, y: Y(sol.corridor.meas_height) - 3, text: `measured at ${sol.corridor.meas_height} m`, anchor: 'start', size: 8.5, fill: 'var(--blue-bright)' },
    };
    P.block(Placer.box(out.meas.x, out.meas.y, out.meas.text, 8.5, 'start'));
    if (layers.conductors) for (const l of sol.lines) for (const c of l.conductors) {
      const r = c.bundle.length ? 5 + 2.2 * geo.s * Math.max(...c.bundle.map((o) => Math.hypot(o[0], o[1]))) : 5;
      P.block({ x0: X(c.x) - r, x1: X(c.x) + r, y0: Y(c.y) - r, y1: Y(c.y) + r });
    }
    if (layers.buildings) config.buildings.forEach((b) => {
      const sign = b.side === 'left' ? -1 : 1;
      const near = sign * b.distance, far = near + sign * b.width;
      const x0 = X(Math.min(near, far)), x1 = X(Math.max(near, far)), w = x1 - x0;
      const yTop = Y(b.height), h = ground - yTop;
      const roofH = b.roof === 'pitched' ? Math.min(h * 0.3, w * 0.28) : b.roof === 'stepped' ? 14 : 12;
      P.block({ x0, x1, y0: yTop - roofH + 2, y1: ground });
      const xm = (x0 + x1) / 2, y = yTop - roofH - (b.roof === 'pitched' ? 4 : 2);
      out.building.push(P.place([0, -11, -22].map((d) => ({ x: xm, y: y + d, anchor: 'middle' as const })), b.name, 9.5, 'var(--ink)', 600));
    });
    if (layers.shield && sol.shield.on && sol.shield.walls[0]) {
      const sh = sol.shield;
      const top = Math.max(...sh.walls.map((w) => Math.max(w[1], w[3])));
      const xm = sh.walls.reduce((a, w) => a + (w[0] + w[2]) / 2, 0) / sh.walls.length;
      const x = X(sh.is_wire || sh.attached ? xm : sh.walls[0][0]);
      const text = sh.is_wire ? (sh.preset === 'passive-loop' ? 'passive loop' : 'screening wires') : `${sh.material.label.split(' (')[0]} · ${sh.thickness_mm} mm`;
      const y = Y(top) - (sh.is_wire ? 10 : 6);
      out.shield = P.place([0, -11, -22, -33].map((d) => ({ x, y: y + d, anchor: 'middle' as const })), text, 9.5, 'var(--teal)', 700);
    }
    if (layers.towers) sol.lines.forEach((l) => {
      const y = Math.max(11, Y(Math.max(...l.conductors.map((c) => c.y_att)) + 5) - 4);
      const kv = [...new Set(l.circuits.filter((k) => k.on).map((k) => k.kv))];
      out.line.push(P.place([0, -11, 11, -22, 22].map((d) => ({ x: X(l.xc), y: Math.max(11, y + d), anchor: 'middle' as const })),
        `${l.name} · ${kv.length ? kv.join('/') : l.kv} kV`, 9.5, 'var(--steel)'));
    });
    if (layers.row) {
      const xl = X(-sol.corridor.row_half) + 4, xr = X(sol.corridor.row_half) - 4;
      out.row = P.place([{ x: xl, y: 12, anchor: 'start' }, { x: xr, y: 12, anchor: 'end' }, { x: xl - 8, y: 12, anchor: 'end' }, { x: xr + 8, y: 12, anchor: 'start' },
        { x: xl, y: 24, anchor: 'start' }, { x: xl, y: ground - 5, anchor: 'start' }], `ROW ±${sol.corridor.row_half} m`, 9.5, 'var(--steel)');
    }
    if (layers.conductors) sol.lines.forEach((l) => {
      out.phase.push(l.conductors.map((c) => {
        const x = X(c.x), y = Y(c.y), outer = c.x >= l.xc ? 1 : -1;
        const fill = c.on === false ? OFF : `var(--phase-${c.phase.toLowerCase()})`;
        // clear of the conductor's own dots (a bundle is drawn wider than a single wire)
        const r = (c.bundle.length ? 5 + 2.2 * geo.s * Math.max(...c.bundle.map((o) => Math.hypot(o[0], o[1]))) : 5) + 2.5;
        return P.place([
          { x: x + outer * r, y: y + 3, anchor: outer > 0 ? 'start' : 'end' }, { x, y: y - r - 1, anchor: 'middle' }, { x, y: y + r + 9, anchor: 'middle' },
          { x: x - outer * r, y: y + 3, anchor: outer > 0 ? 'end' : 'start' }], c.phase, 9.5, fill, 700, false);
      }));
    });
    return out;
  }, [sol, config, geo, layers]);

  if (!sol || !config || !geo || !labels) return null;
  const { X, Y, H, xMin, xMax } = geo;
  const ground = Y(0);
  const step = xMax - xMin > 160 ? 20 : 10;
  const ticks: number[] = [];
  for (let x = Math.ceil(xMin / step) * step; x <= xMax; x += step) ticks.push(x);
  const maxI = Math.max(1, ...sol.lines.flatMap((l) => l.conductors.map((c) => c.current_a)));
  const text = (l: Label | null, key: string | number) => l && <text key={key} x={l.x} y={l.y} fontSize={l.size} textAnchor={l.anchor} fill={l.fill} fontWeight={l.weight}>{l.text}</text>;
  const anyOff = sol.lines.some((l) => l.conductors.some((c) => c.on === false));

  return (
    <div>
      {controls && (
        <div className="chips mb-8">
          {LAYERS.map(([k, label]) => <Chip key={k} on={layers[k]} onClick={() => setLayers((l) => ({ ...l, [k]: !l[k] }))}>{label}</Chip>)}
        </div>
      )}
      <svg viewBox={`0 0 ${W} ${H}`} className="xsec" role="img" aria-label="Cross-section of the corridor at mid-span">
        <defs>
          <radialGradient id="xs-glow"><stop offset="0" stopColor="var(--amber)" stopOpacity="0.30" /><stop offset="1" stopColor="var(--amber)" stopOpacity="0" /></radialGradient>
          <linearGradient id="xs-shade" x1="0" x2="1"><stop offset="0" stopColor="#fff" stopOpacity="0.16" /><stop offset="1" stopColor="#000" stopOpacity="0.16" /></linearGradient>
          {/* in user space: a filter sized from the bounding box would hide an upright or level sheet, whose box has no width or no height */}
          <filter id="xs-teal" filterUnits="userSpaceOnUse" x={0} y={0} width={W} height={H}><feDropShadow dx="0" dy="0" stdDeviation="2.2" floodColor="#00B8B0" floodOpacity="0.9" /></filter>
        </defs>

        {layers.row && (
          <g>
            <rect x={X(-sol.corridor.row_half)} y={0} width={X(sol.corridor.row_half) - X(-sol.corridor.row_half)} height={ground} fill="var(--blue)" opacity={0.06} />
            {[-1, 1].map((s) => <line key={s} x1={X(s * sol.corridor.row_half)} x2={X(s * sol.corridor.row_half)} y1={0} y2={ground} stroke="var(--steel)" strokeDasharray="3 4" opacity={0.6} />)}
          </g>
        )}

        {layers.glow && sol.lines.flatMap((l, li) => l.conductors.map((c, ci) => (c.current_a > 0
          ? <circle key={`${li}-${ci}`} cx={X(c.x)} cy={Y(c.y)} r={18 + 44 * Math.sqrt(c.current_a / maxI)} fill="url(#xs-glow)" /> : null)))}

        {/* ground */}
        <rect x={0} y={ground} width={W} height={H - ground} fill="var(--surface-2)" />
        <line x1={0} x2={W} y1={ground} y2={ground} stroke="var(--line-strong)" strokeWidth={1.5} />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={X(t)} x2={X(t)} y1={ground} y2={ground + 4} stroke="var(--steel)" />
            <text x={X(t)} y={ground + 14} fontSize={9.5} textAnchor="middle" fill="var(--steel)">{t}</text>
          </g>
        ))}
        <text x={W / 2} y={H - 4} fontSize={9} textAnchor="middle" fill="var(--steel)">lateral distance from the centreline (m)</text>
        <line x1={X(xMin)} x2={X(xMax)} y1={Y(sol.corridor.meas_height)} y2={Y(sol.corridor.meas_height)} stroke="var(--blue-bright)" strokeDasharray="1 5" opacity={0.7} />
        {text(labels.meas, 'meas')}

        {layers.towers && sol.lines.map((l, i) => <Tower key={i} line={l} X={X} Y={Y} />)}

        {layers.conductors && sol.lines.flatMap((l, li) => l.conductors.map((c, ci) => (
          <g key={`${li}-${ci}`}>
            <line x1={X(c.x)} x2={X(c.x)} y1={Y(c.y_att)} y2={Y(c.y)} stroke="var(--steel)" strokeDasharray="2 3" opacity={0.6} />
            {(c.bundle.length ? c.bundle : [[0, 0]]).map((o, k) => (
              <circle key={k} cx={X(c.x + o[0] * (c.bundle.length ? 2.2 : 1))} cy={Y(c.y + o[1] * (c.bundle.length ? 2.2 : 1))} r={c.bundle.length ? 2.6 : 4}
                      fill={c.on === false ? OFF : `var(--phase-${c.phase.toLowerCase()})`} stroke="rgba(0,0,0,.45)" strokeWidth={0.8} />
            ))}
            {text(labels.phase[li]?.[ci] ?? null, 'p')}
          </g>
        )))}
        {layers.towers && labels.line.map((l, i) => text(l, `l${i}`))}

        {layers.buildings && config.buildings.map((b, i) => (
          <BuildingElev key={i} b={b} X={X} Y={Y} s={geo.s} colour={lib?.building_types.find((t) => t.name === b.type)?.colour ?? '#C8CCCF'}
                        floorH={b.floor_h ?? lib?.building_types.find((t) => t.name === b.type)?.floor_h ?? 3.5} probe={sol.receptors[i]?.probe} />
        ))}
        {layers.buildings && labels.building.map((l, i) => text(l, `b${i}`))}

        {layers.shield && sol.shield.on && !sol.shield.is_wire && sol.shield.walls.map((w, i) => (
          <line key={i} x1={X(w[0])} y1={Y(w[1])} x2={X(w[2])} y2={Y(w[3])} stroke="#00B8B0" strokeWidth={4} strokeLinecap="round" filter="url(#xs-teal)" strokeDasharray={sol.shield.mesh ? '3 3' : undefined} />
        ))}
        {layers.shield && sol.shield.on && sol.shield.is_wire && <>
          {sol.shield.bonded && sol.shield.preset === 'passive-loop' && sol.shield.wires.map((w, i) => (i % 2 === 0 && sol.shield.wires[i + 1]
            ? <line key={`b${i}`} x1={X(w[0])} y1={Y(w[1])} x2={X(sol.shield.wires[i + 1][0])} y2={Y(sol.shield.wires[i + 1][1])} stroke="#00B8B0" strokeWidth={1.2} strokeDasharray="4 3" /> : null))}
          {sol.shield.wires.map((w, i) => <circle key={i} cx={X(w[0])} cy={Y(w[1])} r={4.5} fill="var(--card)" stroke="#00B8B0" strokeWidth={2.5} filter="url(#xs-teal)" />)}
        </>}
        {text(labels.shield, 'shield')}
        {text(labels.row, 'row')}

        {(config.points ?? []).map((p, i) => (
          <g key={i}>
            <circle cx={X(p.x)} cy={Y(p.y)} r={5.5} fill="var(--card)" stroke="var(--ink)" strokeWidth={1.6} />
            <text x={X(p.x)} y={Y(p.y) + 3} fontSize={8} textAnchor="middle" fill="var(--ink)" fontWeight={700}>{i + 1}</text>
          </g>
        ))}
      </svg>
      {anyOff && <p className="tiny muted" style={{ margin: '4px 0 0' }}>Grey conductors belong to a circuit that is out of service.</p>}
    </div>
  );
}

function Tower({ line, X, Y }: { line: Solution['lines'][number]; X: (x: number) => number; Y: (y: number) => number }) {
  const att = line.conductors.map((c) => c.y_att);
  const top = Math.max(...att) + 4;
  const xc = line.xc;
  const levels = [...new Set(att.map((a) => a.toFixed(2)))].map(Number).sort((a, b) => a - b);
  const stroke = 'var(--steel)';
  if (line.tower === 'monopole') {
    return (
      <g stroke={stroke} fill="none">
        <path d={`M ${X(xc) - 4} ${Y(0)} L ${X(xc) - 1.6} ${Y(top)} L ${X(xc) + 1.6} ${Y(top)} L ${X(xc) + 4} ${Y(0)} Z`} fill="var(--line-strong)" stroke={stroke} strokeWidth={0.8} />
        {levels.map((lv) => {
          const xs = line.conductors.filter((c) => Math.abs(c.y_att - lv) < 0.01).map((c) => c.x);
          return <line key={lv} x1={X(Math.min(...xs, xc))} x2={X(Math.max(...xs, xc))} y1={Y(lv)} y2={Y(lv)} strokeWidth={2} />;
        })}
      </g>
    );
  }
  const spread = Math.max(...line.conductors.map((c) => Math.abs(c.x - xc)));
  const base = Math.max(3.2, spread * 0.55 + 1.6);
  const waist = 1.1;
  const N = 6;
  const seg: string[] = [];
  const wAt = (h: number) => base - (base - waist) * Math.min(1, h / top);
  for (let i = 0; i < N; i++) {
    const h0 = (top * i) / N, h1 = (top * (i + 1)) / N;
    const w0 = wAt(h0), w1 = wAt(h1);
    seg.push(`M ${X(xc - w0)} ${Y(h0)} L ${X(xc + w1)} ${Y(h1)} M ${X(xc + w0)} ${Y(h0)} L ${X(xc - w1)} ${Y(h1)} M ${X(xc - w1)} ${Y(h1)} L ${X(xc + w1)} ${Y(h1)}`);
  }
  return (
    <g stroke={stroke} fill="none" strokeLinecap="round">
      <path d={`M ${X(xc - base)} ${Y(0)} L ${X(xc - waist)} ${Y(top)} M ${X(xc + base)} ${Y(0)} L ${X(xc + waist)} ${Y(top)}`} strokeWidth={1.6} />
      <path d={seg.join(' ')} strokeWidth={0.7} opacity={0.75} />
      {levels.map((lv) => {
        const xs = line.conductors.filter((c) => Math.abs(c.y_att - lv) < 0.01).map((c) => c.x);
        return <line key={lv} x1={X(Math.min(...xs, xc - wAt(lv)))} x2={X(Math.max(...xs, xc + wAt(lv)))} y1={Y(lv)} y2={Y(lv)} strokeWidth={1.8} />;
      })}
    </g>
  );
}

function BuildingElev({ b, X, Y, s, colour, floorH, probe }: { b: BuildingCfg; X: (x: number) => number; Y: (y: number) => number; s: number; colour: string; floorH: number; probe?: number[] }) {
  const sign = b.side === 'left' ? -1 : 1;
  const near = sign * b.distance, far = near + sign * b.width;
  const x0 = X(Math.min(near, far)), x1 = X(Math.max(near, far));
  const w = x1 - x0;
  const yTop = Y(b.height), yG = Y(0);
  const h = yG - yTop;
  const floors = Math.max(1, Math.round(b.height / floorH));
  const fh = h / floors;
  const cols = Math.max(2, Math.round(b.width / 3.6));
  const wins: React.ReactNode[] = [];
  const ww = Math.min(w / cols * 0.55, 9), wh = Math.min(fh * 0.5, 9);
  if (w > 26 && fh > 6) {
    for (let r = 0; r < floors; r++) for (let c = 0; c < cols; c++) {
      wins.push(<rect key={`${r}-${c}`} x={x0 + ((c + 0.5) / cols) * w - ww / 2} y={yTop + r * fh + fh * 0.25} width={ww} height={wh} rx={0.6} fill="#2A4A63" opacity={0.85} />);
    }
  }
  const roofH = b.roof === 'pitched' ? Math.min(h * 0.3, w * 0.28) : 0;
  return (
    <g>
      <rect x={x0} y={yTop} width={w} height={h} fill={colour} stroke="var(--ink)" strokeWidth={1} />
      <rect x={x0} y={yTop} width={w} height={h} fill="url(#xs-shade)" />
      {b.roof === 'pitched' && <polygon points={`${x0 - 2},${yTop} ${x0 + w / 2},${yTop - roofH} ${x1 + 2},${yTop}`} fill="#8C6A52" stroke="var(--ink)" strokeWidth={1} />}
      {b.roof === 'stepped' && <rect x={x0 + w * 0.22} y={yTop - Math.min(fh, 14)} width={w * 0.56} height={Math.min(fh, 14)} fill={colour} stroke="var(--ink)" strokeWidth={1} />}
      {b.roof === 'flat' && <>
        <rect x={x0 - 1.5} y={yTop - 2.5} width={w + 3} height={2.5} fill="#A8AEB3" stroke="var(--ink)" strokeWidth={0.6} />
        {w > 40 && [0.25, 0.6].map((f) => <rect key={f} x={x0 + w * f} y={yTop - 9} width={Math.min(14, w * 0.12)} height={6.5} fill="#9AA1A6" stroke="var(--ink)" strokeWidth={0.5} />)}
      </>}
      {Array.from({ length: floors - 1 }, (_, i) => <line key={i} x1={x0} x2={x1} y1={yTop + (i + 1) * fh} y2={yTop + (i + 1) * fh} stroke="rgba(0,0,0,.22)" />)}
      {wins}
      {w > 18 && <rect x={x0 + w / 2 - 3} y={yG - Math.min(fh * 0.7, 10)} width={6} height={Math.min(fh * 0.7, 10)} fill="#22323F" />}
      {probe && <g><circle cx={X(probe[0])} cy={Y(probe[1])} r={3.4} fill="#fff" stroke="var(--red)" strokeWidth={1.6} /></g>}
    </g>
  );
}

/** Semi-circular gauge of a value against its limit (replaces the Plotly indicator). */
export function Gauge({ value, limit, unit, label, status }: { value: number; limit: number; unit: string; label: string; status: string }) {
  const max = Math.max(limit * 1.5, value * 1.25, limit + 1e-9);
  const W = 240, H = 138, cx = W / 2, cy = 118, R = 92, T = 15;
  const ang = (v: number) => Math.PI * (1 - Math.min(1, Math.max(0, v / max)));
  const pt = (v: number, r: number) => [cx + r * Math.cos(ang(v)), cy - r * Math.sin(ang(v))];
  const arc = (a: number, b: number, r: number) => {
    const [x0, y0] = pt(a, r), [x1, y1] = pt(b, r);
    return `M ${x0} ${y0} A ${r} ${r} 0 0 1 ${x1} ${y1}`;
  };
  const col = status === 'FAIL' ? 'var(--red)' : status === 'MARGINAL' ? 'var(--amber)' : status === 'PASS' ? 'var(--green)' : 'var(--steel)';
  const [lx, ly] = pt(limit, R + 9), [lx2, ly2] = pt(limit, R - T - 4);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: 280, display: 'block', margin: '0 auto' }} role="img" aria-label={`${label}: ${value.toFixed(2)} ${unit} against a limit of ${limit} ${unit}`}>
      <path d={arc(0, limit * 0.75, R)} stroke="var(--green-bg)" strokeWidth={T} fill="none" />
      <path d={arc(limit * 0.75, limit, R)} stroke="var(--amber-bg)" strokeWidth={T} fill="none" />
      <path d={arc(limit, max, R)} stroke="var(--red-bg)" strokeWidth={T} fill="none" />
      <path d={arc(0, Math.min(value, max), R)} stroke={col} strokeWidth={T * 0.55} fill="none" strokeLinecap="round" />
      <line x1={lx} y1={ly} x2={lx2} y2={ly2} stroke="var(--red)" strokeWidth={2.5} />
      <text x={cx} y={cy - 22} textAnchor="middle" fontSize={25} fontWeight={600} fill="var(--ink)" fontFamily="var(--font-mono)">{value >= 100 ? value.toFixed(0) : value >= 10 ? value.toFixed(1) : value.toFixed(2)}</text>
      <text x={cx} y={cy - 5} textAnchor="middle" fontSize={11} fill="var(--steel)" fontFamily="var(--font-mono)">{unit} · limit {limit}</text>
      <text x={cx - R} y={cy + 14} textAnchor="middle" fontSize={9} fill="var(--steel)" fontFamily="var(--font-mono)">0</text>
      <text x={cx + R} y={cy + 14} textAnchor="middle" fontSize={9} fill="var(--steel)" fontFamily="var(--font-mono)">{max >= 100 ? max.toFixed(0) : max.toFixed(1)}</text>
      <text x={cx} y={12} textAnchor="middle" fontSize={10.5} fill="var(--steel)">{label}</text>
    </svg>
  );
}
