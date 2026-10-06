import { useEffect, useMemo, useRef, useState } from 'react';
import { Plus } from 'lucide-react';
import { Plot } from '@/components/Plot';
import { SpanStrip } from '@/components/SpanStrip';
import { Busy, Button, Card, ErrorNote, Metric, Note, PageHead, Segmented, Select, Switch } from '@/components/ui';
import { api } from '@/lib/api';
import { fieldMapFigure } from '@/lib/charts';
import { change, dB, fmt } from '@/lib/format';
import { useElementSize, useRemote } from '@/lib/hooks';
import { useStore } from '@/lib/store';
import type { GridOut, PointRow } from '@/lib/types';
import { Loading, useDeco, useDecodedGrid } from './common';

type View = 'without' | 'with' | 'diff' | 'side';

/** Shared map + observation-point workspace (used by Field map and Compare). */
export function FieldMapWorkspace({ compact }: { compact?: boolean }) {
  const sol = useStore((s) => s.sol);
  const config = useStore((s) => s.config)!;
  const physKey = useStore((s) => s.physKey);
  const setPins = useStore((s) => s.setPins);
  const toast = useStore((s) => s.toast);
  const [q, setQ] = useState<'B' | 'E'>('B');
  const [view, setView] = useState<View>(sol?.shield.on ? 'side' : 'without');
  const [log, setLog] = useState(true);
  const [trueScale, setTrueScale] = useState(false);
  const [box, boxSize] = useElementSize<HTMLDivElement>();
  const zOptions = useMemo(() => {
    const o = [{ value: 0, label: 'Mid-span (z = 0)' }];
    if (sol?.shield.on && Math.abs(sol.shield.zc) > 0.5) o.push({ value: sol.shield.zc, label: `Through the shield (z = ${sol.shield.zc} m)` });
    for (const b of config.buildings) if (Math.abs(b.z_offset) > 0.5 && !o.some((x) => x.value === b.z_offset)) o.push({ value: b.z_offset, label: `Through ${b.name} (z = ${b.z_offset} m)` });
    if (sol) { o.push({ value: sol.corridor.half_span / 2, label: `Quarter span (z = ${sol.corridor.half_span / 2} m)` }); o.push({ value: sol.corridor.half_span, label: `At the tower (z = ${sol.corridor.half_span} m)` }); }
    return o;
  }, [sol, config.buildings]);
  const [z, setZ] = useState(0);
  // a position chosen on the side view of the span need not be one of the named ones
  const zChoices = zOptions.some((o) => o.value === z) ? zOptions : [...zOptions, { value: z, label: `z = ${z} m` }];
  const grid = useRemote<GridOut>('/grid', { z });
  const g = useDecodedGrid(grid.data);
  const deco = useDeco({ pins: true, z });
  const [obs, setObs] = useState<{ x: number; y: number } | null>(null);
  const [pt, setPt] = useState<PointRow | null>(null);
  const shieldOn = !!sol?.shield.on && !!g?.shieldHere;
  const chosen = useRef(false);                      // has the person picked a view themselves?
  const pickView = (v: View) => { chosen.current = true; setView(v); };
  useEffect(() => {
    if (!shieldOn && view !== 'without') setView('without');
    else if (shieldOn && !chosen.current && view === 'without') setView('side');   // a shield just came into the picture
  }, [shieldOn, view]);

  useEffect(() => {
    if (!obs) { setPt(null); return; }
    let live = true;
    api.post<{ rows: PointRow[] }>('/points', { config, points: [{ x: obs.x, y: obs.y, z, label: '' }] })
      .then((r) => { if (live) setPt(r.rows[0] ?? null); }).catch(() => { /* keep the last value */ });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [obs, z, physKey]);

  const figs = useMemo(() => {
    if (!g) return null;
    const src = { x: g.x, y: g.y, z0: q === 'B' ? g.b0 : g.e0, zS: q === 'B' ? g.bS : g.eS };
    const d = { ...deco, obs, refPoint: sol?.shield.on && sol.shield.ref_point && Math.abs(z - sol.shield.zc) < 0.5 ? sol.shield.ref_point : null };
    if (view === 'side') return [fieldMapFigure(src, { quantity: q, view: 'without', log, deco: { ...d, walls: null }, showScale: false, trueScale }), fieldMapFigure(src, { quantity: q, view: 'with', log, deco: d, trueScale })];
    return [fieldMapFigure(src, { quantity: q, view, log, deco: view === 'without' ? { ...d, walls: null } : d, trueScale })];
  }, [g, q, view, log, deco, obs, sol, z, trueScale]);

  if (!sol) return <Loading />;
  const pick = (p: { x: number; y: number }) => setObs({ x: +Number(p.x).toFixed(2), y: Math.max(0, +Number(p.y).toFixed(2)) });
  const unit = q === 'B' ? 'µT' : 'kV/m';
  const h = compact ? 330 : 430;
  // how much taller than life the map is drawn when it fills its panel
  const stretch = g && boxSize.w > 0
    ? ((h - 56) / (g.y[g.y.length - 1] || 1)) / (((boxSize.w - 64 - (view === 'side' ? 0 : 80)) / (g.x[g.x.length - 1] - g.x[0] || 1)) || 1)
    : 0;

  return (
    <>
      <div className="row wrap gap-12 mb-12">
        <Segmented value={q} onChange={setQ} options={[{ value: 'B', label: 'Magnetic B' }, { value: 'E', label: 'Electric E' }]} />
        <Segmented value={view} onChange={pickView} options={[
          { value: 'without', label: 'Without shield' },
          { value: 'with', label: 'With shield', disabled: !shieldOn },
          { value: 'side', label: 'Side by side', disabled: !shieldOn },
          { value: 'diff', label: 'Difference', disabled: !shieldOn }]} />
        <Switch checked={log} onChange={setLog} label="Log scale" disabled={view === 'diff'} title="Colours step by factors of ten, so the weak field far from the line shows as well as the strong field beside the wires. Off, colour is in proportion to the value and only the surroundings of the wires stand out. The numbers are the same either way." />
        <Switch checked={trueScale} onChange={setTrueScale} label="True scale" title="One metre up drawn the same as one metre across. Off, the map fills the panel so it is easier to read, and heights look taller than they are." />
        <div style={{ minWidth: 230 }} title="Where along the span the cross-section is cut. z is measured along the line from mid-span."><Select value={z} onChange={setZ} options={zChoices} /></div>
      </div>
      {!compact && <SpanStrip halfSpan={sol.corridor.half_span} lines={sol.lines} buildings={config.buildings} z={z} onChange={setZ}
        shield={sol.shield.on ? { zc: sol.shield.zc, zh: sol.shield.zh } : null} />}
      <ErrorNote error={grid.error} />
      {sol.shield.enabled && !shieldOn && sol.shield.on && <Note kind="info" className="mb-12">This section is outside the shield's length (z = {sol.shield.zc - sol.shield.zh} to {sol.shield.zc + sol.shield.zh} m), so the field here is unshielded.</Note>}
      {!figs ? <Loading label="Computing the field map…" /> : (
        <div className={figs.length === 2 ? 'grid c2' : undefined} style={{ position: 'relative' }}>
          <Busy on={grid.loading} />
          {figs.map((f, i) => (
            <div className="plot-card" key={i} ref={i === 0 ? box : undefined}>
              <div className="head"><h3>{view === 'diff' ? 'Change caused by the shield' : figs.length === 2 ? (i === 0 ? 'Without shield' : 'With shield') : view === 'with' ? 'With shield' : 'Without shield'}</h3>
                <span className="sub">{view === 'diff' ? 'teal = lower, red = higher' : figs.length === 2 && i === 1 ? 'same colour scale' : `${q === 'B' ? 'magnetic' : 'electric'} field, ${unit}`}{!trueScale && stretch > 1.15 ? ` · heights drawn ×${stretch.toFixed(1)}` : ''}</span></div>
              <Plot data={f.data} layout={f.layout} height={h} onClick={pick} filename={`taki-field-map-${q}`} />
            </div>
          ))}
        </div>
      )}

      <Card className="mt-12" title="Observation point" sub={obs ? `x = ${obs.x} m, y = ${obs.y} m, z = ${z} m` : 'click anywhere on a map'}
            actions={obs && <Button size="sm" onClick={() => { setPins([...config.points, { x: obs.x, y: obs.y, z, label: '' }]); toast('Added to the measurement points.'); }}><Plus size={13} />Add to measurement points</Button>}>
        {pt ? (
          <div className="grid auto">
            <Metric small label="B without" value={fmt(pt.b0)} unit="µT" />
            <Metric small label="B with shield" tone="accent" value={fmt(pt.bS)} unit="µT" sub={`${change(pt.b_red_pct, 1)} · ${dB(pt.b_se_db)}`} />
            <Metric small label="E without" value={fmt(pt.e0)} unit="kV/m" />
            <Metric small label="E with shield" tone="accent" value={fmt(pt.eS)} unit="kV/m" sub={`${change(pt.e_red_pct, 1)} · ${dB(pt.e_se_db)}`} />
            <Metric small label="Share of B limit" value={pt.b_pct_limit !== null ? pt.b_pct_limit.toFixed(1) : '—'} unit="%" sub="unshielded" />
          </div>
        ) : <p className="small muted">Values are recomputed exactly at the point you click, with and without the shield. The readout uses the conductor heights at this position along the span.</p>}
      </Card>
    </>
  );
}

export default function MapPage() {
  return (
    <div className="page wide">
      <PageHead title="Field map" lede="The field over one cross-section of the corridor: a slice cut across the line. Without and with the shield share one colour scale, so they can be compared by eye; the difference view shows where the field falls and where it rises." />
      <FieldMapWorkspace />
    </div>
  );
}
