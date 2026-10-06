import { useMemo, useState } from 'react';
import { Download, Plus, Trash2 } from 'lucide-react';
import { Plot } from '@/components/Plot';
import { Busy, Button, Card, ErrorNote, Field, NumberInput, PageHead, Pill, TextInput } from '@/components/ui';
import { saveText } from '@/lib/api';
import { fieldMapFigure } from '@/lib/charts';
import { change, csv, dB, fmt, pct } from '@/lib/format';
import { useRemote } from '@/lib/hooks';
import { useStore } from '@/lib/store';
import type { GridOut, Pin, PointRow } from '@/lib/types';
import { Loading, useDeco, useDecodedGrid } from './common';

export function PointsTable({ rows, onRemove, onLabel }: { rows: PointRow[]; onRemove?: (i: number) => void; onLabel?: (i: number, label: string) => void }) {
  const shield = rows.some((r) => r.in_shield_length && (Math.abs(r.b_red_pct) > 0.005 || Math.abs(r.e_red_pct) > 0.005));
  return (
    <div className="table-wrap">
      <table className="tbl">
        <thead><tr>
          <th>#</th><th>Label</th><th className="num">x</th><th className="num">y</th><th className="num">z</th>
          <th className="num">B (µT)</th>{shield && <><th className="num">B with shield</th><th className="num" title="With shield minus without">ΔB (µT)</th><th className="num">B SE</th></>}
          <th className="num">E (kV/m)</th>{shield && <><th className="num">E with shield</th><th className="num" title="With shield minus without">ΔE (kV/m)</th><th className="num">E SE</th></>}
          <th className="num">% of B limit</th>{onRemove && <th />}
        </tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td className="num">{r.n}</td>
              <td>{onLabel ? <input className="input" style={{ height: 24, padding: '0 6px', minWidth: 90 }} value={r.label} placeholder="label" maxLength={40} onChange={(e) => onLabel(i, e.target.value)} /> : r.label}</td>
              <td className="num">{r.x.toFixed(1)}</td><td className="num">{r.y.toFixed(1)}</td><td className="num">{r.z.toFixed(1)}</td>
              <td className="num">{fmt(r.b0)}</td>
              {shield && <><td className="num">{r.bS < r.b0 * 1e-3 ? '≈ 0' : fmt(r.bS)} <span className={r.b_red_pct >= 0 ? 'good' : 'bad'}>{change(r.b_red_pct)}</span></td><td className="num">{signed(r.bS - r.b0)}</td><td className="num">{dB(r.b_se_db)}</td></>}
              <td className="num">{fmt(r.e0)}</td>
              {shield && <><td className="num">{r.eS < r.e0 * 1e-3 ? '≈ 0' : fmt(r.eS)} <span className={r.e_red_pct >= 0 ? 'good' : 'bad'}>{change(r.e_red_pct)}</span></td><td className="num">{signed(r.eS - r.e0)}</td><td className="num">{dB(r.e_se_db)}</td></>}
              <td className="num">{pct(r.b_pct_limit, 1)}</td>
              {onRemove && <td><Button size="sm" variant="ghost" icon onClick={() => onRemove(i)} aria-label="Remove point"><Trash2 size={13} /></Button></td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A difference with its sign; "0" when it is below what the display can resolve. */
function signed(v: number): string {
  if (!Number.isFinite(v)) return '—';
  if (Math.abs(v) < 5e-5) return '0';
  return `${v > 0 ? '+' : '−'}${fmt(Math.abs(v))}`;
}

export function pointsCsv(rows: PointRow[]): string {
  return csv([['#', 'label', 'x_m', 'y_m', 'z_m', 'B_uT', 'B_with_shield_uT', 'B_difference_uT', 'B_change_pct', 'B_SE_dB', 'E_kVm', 'E_with_shield_kVm', 'E_difference_kVm', 'E_change_pct', 'E_SE_dB', 'pct_of_B_limit'],
    ...rows.map((r) => [r.n, r.label, r.x, r.y, r.z, r.b0, r.bS, r.bS - r.b0, -r.b_red_pct, r.b_se_db, r.e0, r.eS, r.eS - r.e0, -r.e_red_pct, r.e_se_db, r.b_pct_limit])]);
}

export default function MeasurePage() {
  const sol = useStore((s) => s.sol);
  const config = useStore((s) => s.config)!;
  const setPins = useStore((s) => s.setPins);
  const [x, setX] = useState(0);
  const [y, setY] = useState(config.corridor.meas_height);
  const [z, setZ] = useState(0);
  const [label, setLabel] = useState('');
  const pts = useRemote<{ rows: PointRow[]; b_limit: number | null; b_limit_name: string | null }>('/points', {}, { withPoints: true, delay: 150 });
  const grid = useRemote<GridOut>('/grid', { z: 0 });
  const g = useDecodedGrid(grid.data);
  const deco = useDeco({ pins: true });
  const fig = useMemo(() => (g ? fieldMapFigure({ x: g.x, y: g.y, z0: g.b0, zS: g.bS }, { quantity: 'B', view: sol?.shield.on ? 'with' : 'without', log: true, deco }) : null), [g, deco, sol]);
  if (!sol) return <div className="page"><Loading /></div>;
  const pins = config.points;
  const add = (p: Pin[]) => setPins([...pins, ...p].slice(-60));
  const h = sol.corridor.meas_height, row = sol.corridor.row_half;

  return (
    <div className="page">
      <PageHead title="Measure points" lede="Read the field at any point, with and without the shield. Points you drop in the 3-D twin or on a field map appear here too, and go into the report.">
        {pts.data?.rows.length ? <Button size="sm" onClick={() => saveText(pointsCsv(pts.data!.rows), 'taki_points.csv', 'text/csv')}><Download size={13} />CSV</Button> : null}
      </PageHead>
      <Card className="mb-12">
        <div className="row wrap gap-12" style={{ alignItems: 'flex-end' }}>
          <div style={{ width: 110 }}><Field label="x · lateral"><NumberInput value={x} onChange={setX} step={1} unit="m" /></Field></div>
          <div style={{ width: 110 }}><Field label="y · height"><NumberInput value={y} onChange={setY} min={0} max={200} step={0.5} unit="m" /></Field></div>
          <div style={{ width: 110 }}><Field label="z · along line"><NumberInput value={z} onChange={setZ} step={5} unit="m" /></Field></div>
          <div style={{ width: 170 }}><Field label="Label (optional)"><TextInput value={label} onChange={setLabel} maxLength={40} /></Field></div>
          <Button variant="primary" onClick={() => { add([{ x, y, z, label }]); setLabel(''); }}><Plus size={14} />Add point</Button>
        </div>
        <div className="row wrap mt-12">
          <span className="small muted">Shortcuts:</span>
          <Button size="sm" onClick={() => add([{ x: sol.peak_b_x, y: h, z: 0, label: 'peak B' }])}>Peak B</Button>
          <Button size="sm" onClick={() => add([{ x: 0, y: h, z: 0, label: 'centreline' }])}>Under the line</Button>
          <Button size="sm" onClick={() => add([{ x: -row, y: h, z: 0, label: 'ROW −' }, { x: row, y: h, z: 0, label: 'ROW +' }])}>ROW edges</Button>
          <Button size="sm" disabled={!sol.receptors.length} onClick={() => add(sol.receptors.map((r) => ({ x: r.probe[0], y: r.probe[1], z: r.probe[2], label: r.building })))}>Each building</Button>
          {sol.shield.on && sol.shield.ref_xyz && <Button size="sm" onClick={() => add([{ x: sol.shield.ref_xyz![0], y: sol.shield.ref_xyz![1], z: sol.shield.ref_xyz![2], label: 'behind shield' }])}>Behind the shield</Button>}
          <Button size="sm" variant="danger" disabled={!pins.length} onClick={() => setPins([])}>Clear all</Button>
        </div>
      </Card>
      <ErrorNote error={pts.error} />
      {pins.length === 0 ? <Card><p className="small muted">No points yet. Add one above, click a field map, or click the ground or the field section in the 3-D twin.</p></Card> : (
        <div style={{ position: 'relative' }}>
          <Busy on={pts.loading} />
          {pts.data ? <PointsTable rows={pts.data.rows} onRemove={(i) => setPins(pins.filter((_, k) => k !== i))} onLabel={(i, l) => setPins(pins.map((p, k) => (k === i ? { ...p, label: l } : p)))} /> : <Loading />}
          {pts.data?.b_limit_name && <p className="small muted mt-8">“% of B limit” is the unshielded value against {pts.data.b_limit_name} ({pts.data.b_limit} µT). <Pill>exact values</Pill> are recomputed at each point for the conductor heights at its position along the span.</p>}
        </div>
      )}
      <div className="plot-card mt-16">
        <div className="head"><h3>Where the points are</h3><span className="sub">x–y position on the mid-span section; numbered markers</span></div>
        {fig ? <Plot data={fig.data} layout={fig.layout} height={420} filename="taki-points" onClick={(p) => add([{ x: +Number(p.x).toFixed(1), y: Math.max(0, +Number(p.y).toFixed(1)), z: 0, label: '' }])} /> : <Loading />}
        <div className="small muted" style={{ padding: '0 14px 12px' }}>Click the map to add a point at mid-span.</div>
      </div>
    </div>
  );
}
