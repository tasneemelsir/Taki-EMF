import { useMemo, useState } from 'react';
import { Download } from 'lucide-react';
import { Plot } from '@/components/Plot';
import { Busy, Button, ErrorNote, Note, PageHead, Pill, Select, Tabs } from '@/components/ui';
import { saveText } from '@/lib/api';
import { barFigure } from '@/lib/charts';
import { change, csv, dB, fmt } from '@/lib/format';
import { useRemote } from '@/lib/hooks';
import { useStore } from '@/lib/store';
import type { SweepRow } from '@/lib/types';
import { Loading } from './common';
import { FieldMapWorkspace } from './MapPage';

type Tab = 'withwithout' | 'material' | 'thickness' | 'geometry' | 'height' | 'distance' | 'coverage' | 'layers' | 'bonding' | 'building';
const TABS: { value: Tab; label: string; blurb?: string }[] = [
  { value: 'withwithout', label: 'With / without' },
  { value: 'geometry', label: 'Measures', blurb: 'Every established measure side by side for this site: shielding around the building, barriers and conductors between the line and the building, and changes at the line itself. Sheet options use your current material and thickness, and each is placed for the building being judged.' },
  { value: 'material', label: 'Materials', blurb: 'Every library material in your current arrangement and thickness.' },
  { value: 'thickness', label: 'Thickness', blurb: 'The same sheet from 0.5 mm to 100 mm.' },
  { value: 'height', label: 'Height', blurb: 'A wall (barrier or perimeter) from 2 m to 30 m.' },
  { value: 'distance', label: 'Position', blurb: 'How far the shield stands off: the gap from the building for sheets round it, the distance from the line for barriers, loops and screens. A barrier very close to the line can raise the field further out.' },
  { value: 'coverage', label: 'Coverage', blurb: 'Gaps between panels, from half covered to continuous.' },
  { value: 'layers', label: 'Layers', blurb: 'One, two or three spaced layers.' },
  { value: 'bonding', label: 'Earthing & seams', blurb: 'Earthing matters for the electric field; bonding matters for the magnetic field.' },
  { value: 'building', label: 'Building type', blurb: 'The receptor building replaced by each type at its typical size.' },
];

interface SweepData { rows: SweepRow[]; b0: number; e0: number; receptor: string; basis: 'inside' | 'point'; probe: string; xlabel: string; model: string; note: string; other_building: string | null }

function Sweep({ kind, receptor }: { kind: Exclude<Tab, 'withwithout'>; receptor: number }) {
  const setConfig = useStore((s) => s.setConfig);
  const toast = useStore((s) => s.toast);
  const apply = (row: SweepRow) => {
    // every row carries exactly the settings it was solved with
    setConfig((c) => { Object.assign(c.shield, { preset: row.id, enabled: true, target_building: receptor, ...(row.changes ?? {}) }); });
    toast(`Shield set to: ${row.label}. Undo brings the previous one back.`);
  };
  const r = useRemote<SweepData>('/shield/sweep', { kind, receptor });
  const [q, setQ] = useState<'B' | 'E'>(kind === 'bonding' ? 'E' : 'B');
  const inside = r.data?.basis !== 'point';
  const fig = useMemo(() => {
    if (!r.data?.rows.length) return null;
    const rows = r.data.rows, unit = q === 'B' ? 'µT' : 'kV/m';
    return barFigure(rows.map((x) => { const l = x.short ?? x.label; return l.length > 26 ? l.slice(0, 25) + '…' : l; }), rows.map((x) => (q === 'B' ? x.bS : x.eS)),
      { ytitle: `${q} ${inside ? 'inside, average' : 'at the point'} (${unit})`, baseline: kind === 'building' ? null : (q === 'B' ? r.data.b0 : r.data.e0), baselineLabel: `unshielded ${fmt(q === 'B' ? r.data.b0 : r.data.e0)}`, unit });
  }, [r.data, q, kind, inside]);
  if (r.error) return <ErrorNote error={r.error} />;
  if (!r.data) return <Loading label="Solving each option…" />;
  const rows = r.data.rows;
  if (!rows.length) {
    return <Note kind="info">{kind === 'distance'
      ? 'Position has nothing to vary for this arrangement: a shielded room, a floor sheet and a custom layout are placed by their own settings in the inputs panel.'
      : kind === 'building' ? 'Add a building on the Site tab to compare building types.' : 'There is nothing to compare for this arrangement.'}</Note>;
  }
  const best = rows.reduce((a, b) => ((q === 'B' ? b.bS < a.bS : b.eS < a.eS) ? b : a), rows[0]);
  const exportCsv = () => saveText(csv([
    ['option', 'placement', 'basis', 'B_uT', 'B_with_uT', 'B_change_pct', 'B_highest_point_with_uT', 'B_at_probe_uT', 'B_at_probe_with_uT', 'E_kVm', 'E_with_kVm', 'E_change_pct', 'E_highest_point_with_kVm', 'sheet_SE_B_dB'],
    ...rows.map((x) => [x.label, x.sub, x.basis === 'inside' ? `average inside ${x.where}` : 'one point', x.b0, x.bS, -x.b_red_pct, x.b_maxS, x.b_pt0, x.b_ptS, x.e0, x.eS, -x.e_red_pct, x.e_maxS, x.sheet_se_b])]), `taki_compare_${kind}.csv`, 'text/csv');
  const tiny = (v: number, ref: number) => (v < ref * 1e-3 ? '≈ 0' : fmt(v));
  return (
    <div style={{ position: 'relative' }}>
      <Busy on={r.loading} />
      {r.data.other_building && <Note className="mb-12">The shield in this project is built around {r.data.other_building}. These numbers are for another building, which that shield does not enclose, so expect little change. Choose {r.data.other_building} as the building above, or move the shield (inputs → Shield → Building to protect).</Note>}
      <div className="plot-card mb-12">
        <div className="head"><h3>{q === 'B' ? 'Magnetic' : 'Electric'} field {r.data.receptor}{inside ? ', average' : ''}</h3><span className="sub">{r.data.model} model · lower is better</span>
          <div className="tools">
            <div className="seg sm"><button className={q === 'B' ? 'on' : ''} onClick={() => setQ('B')}>B</button><button className={q === 'E' ? 'on' : ''} onClick={() => setQ('E')}>E</button></div>
            <Button size="sm" onClick={exportCsv}><Download size={12} />CSV</Button>
          </div>
        </div>
        {fig && <Plot data={fig.data} layout={fig.layout} height={330} toolbar={false} />}
      </div>
      <div className="table-wrap">
        <table className="tbl">
          <thead><tr>
            <th style={{ minWidth: 270 }}>Option</th>
            <th className="num" title={inside ? 'Average over the inside of the building, 1 m clear of walls, floor and roof' : 'At the point'}>B {inside ? 'inside' : ''} (µT)</th>
            <th className="num">B change</th>
            {inside && <th className="num" title="The highest value anywhere inside, with this option. Next to an open edge it can be above the unshielded value.">B highest point</th>}
            {inside && <th className="num" title="One point: 1 m inside the wall facing the line, at half height. It usually shows a much larger change than the building as a whole.">B at the wall</th>}
            <th className="num" title={inside ? 'Average over the inside of the building' : 'At the point'}>E {inside ? 'inside' : ''} (kV/m)</th>
            <th className="num">E change</th>
            <th className="num" title="Infinite-sheet value for this material and thickness, for comparison only">Sheet SE(B)</th>{kind === 'geometry' && <th />}
          </tr></thead>
          <tbody>
            {rows.map((x, i) => (
              <tr key={`${x.label}-${i}`} className={x === best ? 'sel' : undefined}>
                <td>{x.label}{x.in_use && <> <Pill tone="blue">in use</Pill></>}{x.sub && <div className="tiny muted">{x.sub}</div>}{!x.has_geometry && <div className="tiny" style={{ color: 'var(--amber)' }}>needs a building</div>}</td>
                <td className="num">{tiny(x.bS, x.b0)}</td><td className={`num ${x.b_red_pct >= 0 ? 'good' : 'bad'}`}>{change(x.b_red_pct, 1)}</td>
                {inside && <td className={`num ${x.b_maxS !== null && x.b_max0 !== null && x.b_maxS > x.b_max0 * 1.05 ? 'bad' : ''}`}>{x.b_maxS !== null ? tiny(x.b_maxS, x.b_max0 ?? x.b_maxS) : '—'}</td>}
                {inside && <td className="num muted">{tiny(x.b_ptS, x.b_pt0)} <span className="tiny">{change(x.b_pt_red_pct)}</span></td>}
                <td className="num">{tiny(x.eS, x.e0)}</td><td className={`num ${x.e_red_pct >= 0 ? 'good' : 'bad'}`}>{change(x.e_red_pct, 1)}</td>
                <td className="num muted">{dB(x.sheet_se_b)}</td>
                {kind === 'geometry' && <td className="right">{x.id && x.id !== 'line'
                  ? (x.in_use ? null : <Button size="sm" onClick={() => apply(x)} title="Make this the shield, exactly as it was solved here">Use</Button>)
                  : <span className="tiny muted">Lines tab</span>}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {r.data.note && <Note kind="info" className="mt-8">{r.data.note}</Note>}
      <p className="small muted mt-8">
        {inside
          ? <>Every option is solved again and judged on the <b>average field inside the building</b>, because one point can sit in a quiet spot or a hot one. The highlighted row has the lowest average {q}. “B at the wall” is the single point 1 m inside the wall facing the line: note how much more it changes than the average.</>
          : <>Every option is solved again and read at {r.data.receptor}. The highlighted row gives the lowest {q} field there.</>}
        {' '}“Sheet SE” is the infinite-sheet figure for the material, for comparison only.
      </p>
    </div>
  );
}

export default function ComparePage() {
  const sol = useStore((s) => s.sol);
  const config = useStore((s) => s.config)!;
  const [tab, setTab] = useState<Tab>('withwithout');
  // the building these comparisons are judged on: the one the shield protects, until another is chosen
  const [receptor, setReceptor] = useState(() => Math.min(config.shield.target_building, Math.max(0, config.buildings.length - 1)));
  if (!sol) return <div className="page"><Loading /></div>;
  const t = TABS.find((x) => x.value === tab)!;
  return (
    <div className="page wide">
      <PageHead title="Compare options" lede="The same line and site with one thing changed at a time. Every bar is a fresh solve, not a rule of thumb.">
        {config.buildings.length > 0 && tab !== 'withwithout' && (
          <div style={{ width: 290 }}><Select value={Math.min(receptor, config.buildings.length - 1)} onChange={setReceptor} options={config.buildings.map((b, i) => ({ value: i, label: `Judged inside: ${b.name}` }))} /></div>
        )}
      </PageHead>
      <Tabs value={tab} onChange={setTab} options={TABS} />
      {tab === 'withwithout' ? (
        sol.shield.on ? <FieldMapWorkspace compact /> : <Note kind="info">Switch the shield on (inputs panel → Shield) to compare the field with and without it.</Note>
      ) : (
        <>
          {t.blurb && <p className="small muted mb-12">{t.blurb}</p>}
          <Sweep key={tab} kind={tab} receptor={receptor} />
        </>
      )}
    </div>
  );
}
