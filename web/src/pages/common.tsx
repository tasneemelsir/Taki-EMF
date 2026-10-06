// Helpers shared by several pages.

import { useMemo } from 'react';
import { b64f32, linspace, toRows } from '@/lib/decode';
import type { SectionDeco } from '@/lib/charts';
import { useStore } from '@/lib/store';
import type { GridOut, Receptor, StdResult } from '@/lib/types';
import { change, fmt, near0, STATUS_VAR } from '@/lib/format';
import { Badge, Pill, Spinner } from '@/components/ui';

export function Loading({ label }: { label?: string }) {
  return <div className="empty"><Spinner />{label && <div className="small mt-8">{label}</div>}</div>;
}

/** Overlays for cross-section maps: conductors, shield, buildings, ROW, pins. */
export function useDeco(opts: { pins?: boolean; shield?: boolean; z?: number } = {}): SectionDeco {
  const sol = useStore((s) => s.sol);
  const config = useStore((s) => s.config);
  return useMemo(() => {
    if (!sol || !config) return {};
    const z = opts.z ?? 0;
    const inZ = (b: { z_offset: number; depth: number }) => Math.abs(z - b.z_offset) <= b.depth / 2 + 1e-6;
    // away from mid-span the wires hang higher: the same parabola the engine uses
    const u = sol.corridor.half_span > 0 ? Math.min(1, Math.abs(z) / sol.corridor.half_span) : 0;
    const lines = u === 0 ? sol.lines : sol.lines.map((l) => ({ ...l, conductors: l.conductors.map((k) => ({ ...k, y: k.y + (k.y_att - k.y) * u * u })) }));
    return {
      lines,
      walls: opts.shield !== false && sol.shield.on && Math.abs(z - sol.shield.zc) <= sol.shield.zh + 1e-6 ? sol.shield.walls : null,
      wires: opts.shield !== false && sol.shield.on && Math.abs(z - sol.shield.zc) <= sol.shield.zh + 1e-6 ? sol.shield.wires : null,
      buildings: config.buildings.filter(inZ).map((b) => {
        const s = b.side === 'left' ? -1 : 1;
        return { x0: s * b.distance, x1: s * (b.distance + b.width), h: b.height, name: b.name };
      }),
      rowHalf: sol.corridor.row_half,
      pins: opts.pins ? config.points : undefined,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sol, config, opts.pins, opts.shield, opts.z]);
}

export interface DecodedGrid { x: number[]; y: number[]; b0: number[][]; bS: number[][]; e0: number[][]; eS: number[][]; maxB: number; maxE: number; shieldHere: boolean }

export function useDecodedGrid(g: GridOut | null): DecodedGrid | null {
  return useMemo(() => {
    if (!g) return null;
    const dec = (s: string) => toRows(b64f32(s), g.nx, g.ny);
    return { x: linspace(g.x0, g.x1, g.nx), y: linspace(g.y0, g.y1, g.ny), b0: dec(g.b0), bS: dec(g.bS), e0: dec(g.e0), eS: dec(g.eS), maxB: g.max_b, maxE: g.max_e, shieldHere: g.shield_here };
  }, [g]);
}

export function ComplianceRows({ results }: { results: StdResult[] }) {
  if (!results.length) return <div className="note bad">No standard is selected, so compliance cannot be assessed. Choose standards in the inputs panel.</div>;
  return (
    <div>
      {results.map((r) => (
        <div className="comply" key={r.id} style={{ borderLeftColor: STATUS_VAR[r.overall] }}>
          <div className="name" style={{ flex: '0 1 250px' }}>
            {r.name}
            <small>{r.jurisdiction}{r.kind === 'precautionary' ? ' · precautionary value' : ''}{r.population === 'occupational' ? ' · occupational' : ''}{r.needs_verification ? ' · verify limit' : ''}</small>
          </div>
          <div className="bars">
            <Bullet q="B" value={r.b.value} limit={r.b.limit} unit="µT" status={r.b.status} />
            <Bullet q="E" value={r.e.value} limit={r.e.limit} unit="kV/m" status={r.e.status} />
          </div>
          <Badge status={r.overall} />
        </div>
      ))}
    </div>
  );
}

function Bullet({ q, value, limit, unit, status }: { q: string; value: number; limit: number | null; unit: string; status: string }) {
  if (limit === null) return <div className="bullet"><span>{q}</span><span className="track" /><span>no limit</span></div>;
  const frac = value / limit;
  return (
    <div className="bullet" title={`${q} is ${(frac * 100).toFixed(1)}% of the limit`}>
      <span>{q}</span>
      <span className="track"><i style={{ width: `${Math.min(100, frac * 100)}%`, background: STATUS_VAR[status] }} /><b style={{ left: '75%' }} /></span>
      <span>{fmt(value)} / {fmt(limit, 3)} {unit}</span>
    </div>
  );
}

export function ReceptorTable({ rows, compact }: { rows: Receptor[]; compact?: boolean }) {
  if (!rows.length) return <p className="small muted">No buildings are defined. Add one on the Site tab of the inputs.</p>;
  const shield = rows.some((r) => r.barrier_on);
  const emp = rows.some((r) => r.material_key !== 'none');
  const red = (v0: number, vS: number) => (v0 > 0 ? 100 * (1 - vS / v0) : 0);
  if (compact) {
    // a narrow card: two lines per building instead of a wide table
    const line = (q: string, unit: string, v0: number, vS: number, on: boolean) => (
      <div className="row between small" style={{ padding: '2px 0' }}>
        <span className="muted">{q} inside</span>
        <span className="mono">{fmt(v0)}{on && <> → {near0(vS, v0)}</>} {unit}{on && <> <span className={red(v0, vS) >= 0 ? 'good' : 'bad'}>{change(red(v0, vS))}</span></>}</span>
      </div>
    );
    return (
      <div>
        {rows.map((r, i) => (
          <div key={`${r.building}-${i}`} style={{ padding: '6px 0', borderTop: i ? '1px solid var(--line)' : undefined }}>
            <div className="small" style={{ fontWeight: 600 }}>{r.building}{r.inside_row && <> <Pill tone="amber">inside ROW</Pill></>}{shield && !r.barrier_on && <span className="tiny muted" style={{ fontWeight: 400 }}> · not covered by the shield</span>}</div>
            {line('B', 'µT', r.b_in_avg_uT, r.b_in_avg_shield_uT, r.barrier_on)}
            {line('E', 'kV/m', r.e_in_avg_kVm, r.e_in_avg_shield_kVm, r.barrier_on)}
          </div>
        ))}
        <p className="tiny muted" style={{ margin: '6px 0 0' }}>Averages over the inside of each building.</p>
      </div>
    );
  }
  return (
    <div className="table-wrap">
      <table className="tbl">
        <thead><tr>
          <th>Building</th>{!compact && <th>Type</th>}
          <th className="num" title="Average over the inside of the building, 1 m clear of walls, floor and roof">B inside (µT)</th>{shield && <th className="num">with shield</th>}
          {!compact && <><th className="num" title="One point: 1 m inside the wall facing the line, at half height">B at the wall</th>{shield && <th className="num">with shield</th>}</>}
          <th className="num" title="Average over the inside of the building">E inside (kV/m)</th>{shield && <th className="num">with shield</th>}
          {emp && !compact && <th className="num">B · building fabric</th>}
        </tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.building}>
              <td>{r.building}{r.inside_row && <> <Pill tone="amber">inside ROW</Pill></>}</td>
              {!compact && <td className="muted">{r.building_type}</td>}
              <td className="num">{fmt(r.b_in_avg_uT)}</td>
              {shield && <td className="num">{r.barrier_on ? <>{r.b_in_avg_shield_uT < r.b_in_avg_uT * 1e-3 ? '≈ 0' : fmt(r.b_in_avg_shield_uT)} <span className={r.b_in_reduction_pct >= 0 ? 'good' : 'bad'}>{change(red(r.b_in_avg_uT, r.b_in_avg_shield_uT))}</span></> : <span className="muted" title="This building is outside the shield's length along the line">not covered</span>}</td>}
              {!compact && <>
                <td className="num muted">{fmt(r.b_unshielded_uT)}</td>
                {shield && <td className="num muted">{r.barrier_on ? <>{r.b_barrier_uT < r.b_unshielded_uT * 1e-3 ? '≈ 0' : fmt(r.b_barrier_uT)} <span className="tiny">{change(r.barrier_b_reduction_pct)}</span></> : '—'}</td>}
              </>}
              <td className="num">{fmt(r.e_in_avg_kVm)}</td>
              {shield && <td className="num">{r.barrier_on ? <>{r.e_in_avg_shield_kVm < r.e_in_avg_kVm * 1e-3 ? '≈ 0' : fmt(r.e_in_avg_shield_kVm)} <span className={r.e_in_reduction_pct >= 0 ? 'good' : 'bad'}>{change(r.e_in_reduction_pct)}</span></> : <span className="muted">—</span>}</td>}
              {emp && !compact && <td className="num">{r.material_key !== 'none' ? <>{fmt(r.b_shielded_uT)} <span className="muted">({r.material.split(' (')[0]})</span></> : '—'}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
