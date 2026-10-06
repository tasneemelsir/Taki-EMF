import { useMemo, useState } from 'react';
import { Download } from 'lucide-react';
import { CrossSection } from '@/components/CrossSection';
import { Plot } from '@/components/Plot';
import { Button, Card, Metric, Note, PageHead, Segmented, Switch } from '@/components/ui';
import { saveText } from '@/lib/api';
import { profileFigure } from '@/lib/charts';
import { change, csv, fmt } from '@/lib/format';
import { useStore } from '@/lib/store';
import { Loading } from './common';

function at(xs: number[], ys: number[], x: number): number {
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i++) if (xs[i] >= x) { const f = (x - xs[i - 1]) / (xs[i] - xs[i - 1]); return ys[i - 1] + (ys[i] - ys[i - 1]) * f; }
  return ys[ys.length - 1];
}

/** Outermost distance on one side at which the curve is still at or above `level`. */
function reach(xs: number[], ys: number[], level: number, side: -1 | 1): { kind: 'never' | 'beyond' | 'at'; x?: number } {
  const n = xs.length;
  const order = side === 1 ? Array.from({ length: n }, (_, i) => n - 1 - i) : Array.from({ length: n }, (_, i) => i);
  if (ys[order[0]] >= level) return { kind: 'beyond' };
  for (let k = 1; k < n; k++) {
    const i = order[k], j = order[k - 1];
    if ((side === 1 && xs[i] < 0) || (side === -1 && xs[i] > 0)) break;
    if (ys[i] >= level) {
      const f = (level - ys[j]) / (ys[i] - ys[j] || 1);
      return { kind: 'at', x: xs[j] + (xs[i] - xs[j]) * f };
    }
  }
  return { kind: 'never' };
}

function Reach({ r }: { r: ReturnType<typeof reach> }) {
  if (r.kind === 'never') return <span className="good">not reached</span>;
  if (r.kind === 'beyond') return <span className="warn">beyond the modelled width</span>;
  return <>{Math.abs(r.x!).toFixed(1)} m</>;
}

export default function ProfilePage() {
  const sol = useStore((s) => s.sol);
  const [overlay, setOverlay] = useState(true);
  const [logY, setLogY] = useState(false);
  const [show, setShow] = useState<'both' | 'B' | 'E'>('both');
  const fig = useMemo(() => (sol ? profileFigure(sol, { shield: overlay, logY, showB: show !== 'E', showE: show !== 'B' }) : null), [sol, overlay, logY, show]);
  if (!sol || !fig) return <div className="page"><Loading /></div>;
  const p = sol.profile;
  const row = sol.corridor.row_half;
  const stations = [...new Set([0, -row, row, -20, 20, -30, 30, -50, 50].filter((x) => x >= p.x[0] && x <= p.x[p.x.length - 1]))].sort((a, b) => a - b);
  const levelsB = [...new Set([0.4, 1, 3, 10, 100, ...sol.results.map((r) => r.b.limit).filter((v): v is number => v !== null)])].sort((a, b) => a - b);
  const levelsE = [...new Set([0.5, 1, 5, ...sol.results.map((r) => r.e.limit).filter((v): v is number => v !== null)])].sort((a, b) => a - b);
  const named = (q: 'b' | 'e', v: number) => sol.results.filter((r) => r[q].limit === v).map((r) => r.name).join(', ');
  const exportCsv = () => saveText(csv([['x_m', 'B_uT', 'E_kVm', 'B_with_shield_uT', 'E_with_shield_kVm'], ...p.x.map((x, i) => [x, p.b0[i], p.e0[i], p.bS[i], p.eS[i]])]), 'taki_lateral_profile.csv', 'text/csv');

  return (
    <div className="page">
      <PageHead title="Lateral profile" lede={`Magnetic and electric field against distance from the centreline, at mid-span and ${sol.corridor.meas_height} m above ground. Limit lines and compliance use the unshielded curves.`}>
        <Segmented size="sm" value={show} onChange={setShow} options={[{ value: 'both', label: 'B and E' }, { value: 'B', label: 'B only' }, { value: 'E', label: 'E only' }]} />
        <Switch checked={logY} onChange={setLogY} label="Log scale" />
        {sol.shield.on && <Switch checked={overlay} onChange={setOverlay} label="With shield" />}
        <Button size="sm" onClick={exportCsv}><Download size={13} />CSV</Button>
      </PageHead>

      <div className="grid c4 mb-12">
        <Metric label="Peak B" value={fmt(sol.peak_b)} unit="µT" sub={`at x = ${sol.peak_b_x.toFixed(1)} m`} />
        <Metric label="Peak E" value={fmt(sol.peak_e)} unit="kV/m" sub={`at x = ${sol.peak_e_x.toFixed(1)} m`} />
        <Metric label="B outside the ROW" value={sol.row_b !== null ? fmt(sol.row_b) : '—'} unit="µT" sub={`highest from ±${row} m outward`} />
        <Metric label="E outside the ROW" value={sol.row_e !== null ? fmt(sol.row_e) : '—'} unit="kV/m" sub={`highest from ±${row} m outward`} />
      </div>

      <div className="plot-card">
        <div className="head"><h3>Field against lateral distance</h3><span className="sub">{sol.corridor.ground_note} · {sol.corridor.freq} Hz</span></div>
        <Plot data={fig.data} layout={fig.layout} height={460} filename="taki-lateral-profile" />
      </div>
      {sol.shield.on && overlay && (
        <Note kind="info" className="mt-8">
          With the shield: peak B {fmt(sol.peak_b)} → {fmt(sol.peak_b_shield)} µT, peak E {fmt(sol.peak_e)} → {fmt(sol.peak_e_shield)} kV/m. The peak sits under the line, where a shield at the building does nothing; the benefit shows inside the shield, and right beside it the field can rise.
        </Note>
      )}

      <div className="grid split mt-16">
        <Card title="Corridor cross-section" sub="what this profile cuts through"><CrossSection height={300} /></Card>
        <Card title="Values at set distances">
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th className="num">x (m)</th><th className="num">B (µT)</th><th className="num">E (kV/m)</th>{sol.shield.on && <th className="num">B with shield</th>}</tr></thead>
              <tbody>
                {stations.map((x) => {
                  const b = at(p.x, p.b0, x), bs = at(p.x, p.bS, x);
                  return (
                    <tr key={x}><td className="num">{x}{Math.abs(x) === row ? ' · ROW' : ''}</td><td className="num">{fmt(b)}</td><td className="num">{fmt(at(p.x, p.e0, x))}</td>
                      {sol.shield.on && <td className="num">{fmt(bs)} <span className={bs <= b ? 'good' : 'bad'}>{change(b > 0 ? 100 * (1 - bs / b) : 0)}</span></td>}</tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card className="mt-16" title="How far the field reaches" sub={`distance from the centreline beyond which the unshielded field stays below each level · mid-span, ${sol.corridor.meas_height} m above ground`}>
        <div className="grid c2">
          {([['b', 'Magnetic field', 'µT', levelsB, p.b0], ['e', 'Electric field', 'kV/m', levelsE, p.e0]] as const).map(([q, title, unit, levels, ys]) => (
            <div className="table-wrap" key={q}>
              <table className="tbl">
                <thead><tr><th>{title} below</th><th className="num">Left of the line</th><th className="num">Right of the line</th></tr></thead>
                <tbody>
                  {levels.map((v) => (
                    <tr key={v}>
                      <td><span className="mono">{v} {unit}</span>{named(q, v) && <div className="tiny muted">{named(q, v)}</div>}</td>
                      <td className="num"><Reach r={reach(p.x, ys as number[], v, -1)} /></td>
                      <td className="num"><Reach r={reach(p.x, ys as number[], v, 1)} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
        <p className="small muted mt-8">Useful for siting: a building wholly beyond the stated distance sees less than that level from this corridor at the measurement height. “Not reached” means the field is below the level everywhere on the profile. Levels without a name are common planning thresholds, not limits you have selected.</p>
      </Card>
    </div>
  );
}
