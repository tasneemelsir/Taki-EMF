import { useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowRight, Box, FileText, Layers, Shield } from 'lucide-react';
import { CrossSection, Gauge } from '@/components/CrossSection';
import { Plot } from '@/components/Plot';
import { Button, Card, Eyebrow, Kv, Metric, Note, PageHead, Pill } from '@/components/ui';
import { profileFigure } from '@/lib/charts';
import { ago, amps, change, fmt, near0, STATUS_LABEL, STATUS_TONE } from '@/lib/format';
import { useStore } from '@/lib/store';
import { ComplianceRows, Loading, ReceptorTable } from './common';

export default function Dashboard() {
  const sol = useStore((s) => s.sol);
  const project = useStore((s) => s.project);
  const setInspector = useStore((s) => s.setInspector);
  const replaceConfig = useStore((s) => s.replaceConfig);
  const { pid } = useParams();
  const nav = useNavigate();
  const fig = useMemo(() => (sol ? profileFigure(sol, { shield: true }) : null), [sol]);
  if (!sol || !fig) return <div className="page"><Loading label="Solving the fields…" /></div>;
  const g = sol.governing;
  const shd = sol.shield;

  return (
    <div className="page">
      <PageHead title="Dashboard" lede="Peak fields at mid-span, the result against each selected standard, and what the shield does. Compliance always uses the unshielded field." />

      <div className="dash-top">
        <Metric rule label="Peak B" value={fmt(sol.peak_b)} unit="µT" sub={`at x = ${sol.peak_b_x.toFixed(1)} m`} />
        <Metric rule label="Peak E" value={fmt(sol.peak_e)} unit="kV/m" sub={`at x = ${sol.peak_e_x.toFixed(1)} m`} />
        <Metric rule tone={g ? STATUS_TONE[g.status] : ''} label="Margin to limit" value={g ? g.headroom.toFixed(0) : '—'} unit="%"
                sub={g ? `${g.quantity} field vs ${g.standard}` : 'no limit selected'} />
        <Metric rule label="Outside the ROW" value={sol.row_b !== null ? fmt(sol.row_b) : '—'} unit="µT" sub={sol.row_e !== null ? `${fmt(sol.row_e)} kV/m · highest beyond ±${sol.corridor.row_half} m` : ''} />
        <div className="metric" style={{ gridRow: 'span 1', padding: '8px 10px 4px' }}>
          {g ? <Gauge value={g.value} limit={g.limit} unit={g.unit === 'uT' ? 'µT' : g.unit} label={`Peak ${g.quantity} vs ${g.standard}`} status={g.status} />
             : <div className="small muted" style={{ padding: 16 }}>Select a standard to see the governing limit.</div>}
        </div>
      </div>

      <div className="mt-12"><ComplianceRows results={sol.results} /></div>
      {sol.overall === 'FAIL' && <Note kind="bad" className="mt-8">At least one selected standard is exceeded. The rows above show which, and on which field.</Note>}

      <div className="grid split mt-16">
        <div className="plot-card">
          <div className="head"><h3>Lateral field profile</h3><span className="sub">{sol.corridor.ground_note} · {sol.corridor.freq} Hz · {sol.corridor.meas_height} m above ground</span></div>
          <Plot data={fig.data} layout={fig.layout} height={380} filename="taki-profile" />
        </div>
        <div className="col gap-12">
          <Card title="Shielding" actions={<Button size="sm" variant="ghost" onClick={() => nav(`/p/${pid}/shield`)}>Design <ArrowRight size={13} /></Button>}>
            {shd.on ? (
              <>
                {shd.protected ? (
                  <div className="grid c2">
                    <Metric small tone="accent" label="B inside · average" value={change(shd.protected.b.reduction_pct)} sub={`${fmt(shd.protected.b.avg0)} → ${near0(shd.protected.b.avgS, shd.protected.b.avg0)} µT`} />
                    <Metric small tone="accent" label="E inside · average" value={change(shd.protected.e.reduction_pct)} sub={`${fmt(shd.protected.e.avg0)} → ${near0(shd.protected.e.avgS, shd.protected.e.avg0)} kV/m`} />
                  </div>
                ) : (
                  <div className="grid c2">
                    <Metric small tone="accent" label="B at reference" value={change(100 * (1 - Math.pow(10, -shd.se_b / 20)))} sub={`${shd.se_b.toFixed(1)} dB`} />
                    <Metric small tone="accent" label="E at reference" value={change(100 * (1 - Math.pow(10, -shd.se_e / 20)))} sub={`${shd.se_e.toFixed(1)} dB`} />
                  </div>
                )}
                <p className="small muted mt-8">{shd.label} · {shd.material.label.split(' (')[0]}{shd.is_wire ? ` conductors, ${shd.wire_mm2} mm²` : ` · ${shd.thickness_mm} mm`}{shd.protected ? ` · averaged inside ${shd.protected.label}` : ''}.{sol.peak_b_shield > sol.peak_b * 1.05 ? ` Beside the shield the profile peaks at ${fmt(sol.peak_b_shield)} µT, where the induced currents concentrate.` : ''}</p>
                {shd.floating_kv ? <Note className="mt-8">The shield is unearthed and floats at about {fmt(shd.floating_kv)} kV. Treat it as a touch hazard.</Note> : null}
              </>
            ) : (
              <div className="small muted">No shield is active. <button className="btn ghost sm" onClick={() => setInspector(true, 'shield')}><Shield size={12} />Design one around the building</button></div>
            )}
          </Card>
          <Card title="Building receptors">
            <ReceptorTable rows={sol.receptors} compact />
          </Card>
        </div>
      </div>

      <div className="grid split mt-16">
        <Card title="Corridor cross-section" sub="mid-span">
          <CrossSection height={300} />
        </Card>
        <div className="col gap-12">
          <Card title="Configuration">
            {sol.lines.map((l, i) => {
              const live = l.circuits.filter((k) => k.on);
              const split = l.circuits.length > 1 && (l.separate || live.length < l.circuits.length || new Set(live.map((k) => `${k.kv}/${k.operating_a}`)).size > 1);
              return <Kv key={`${l.name}-${i}`} k={l.name} v={split
                ? `${[...new Set(live.map((k) => k.kv))].join('/') || '—'} kV · ${live.length} of ${l.circuits.length} circuits live`
                : `${l.kv} kV · ${amps(l.operating_a)} A${l.circuits.length > 1 ? ' per circuit' : ''} · ${l.load_pct}%`} />;
            })}
            {sol.clearance && <Kv k="Lowest conductor" v={<span style={sol.clearance.ok ? undefined : { color: 'var(--red)' }}>{fmt(sol.clearance.min_height_m, 3)} m above ground</span>} />}
            <Kv k="Earth model" v={sol.corridor.ground_short} />
            <Kv k="Frequency" v={`${sol.corridor.freq} Hz`} />
            <Kv k="Right-of-way" v={`±${sol.corridor.row_half} m`} />
            <Kv k="Standards" v={`${sol.results.length} selected`} />
            <div className="row wrap mt-12">
              <Button size="sm" onClick={() => setInspector(true, 'lines')}>Edit lines</Button>
              <Button size="sm" onClick={() => setInspector(true, 'site')}>Edit site</Button>
              <Button size="sm" onClick={() => setInspector(true, 'standards')}>Standards</Button>
            </div>
          </Card>
          <Card title="Scenarios" actions={<Button size="sm" variant="ghost" onClick={() => nav(`/p/${pid}/scenarios`)}>All <ArrowRight size={13} /></Button>}>
            {project?.scenarios.length ? project.scenarios.slice(-4).reverse().map((s) => (
              <div key={s.id} className="row between small" style={{ padding: '5px 0', borderBottom: '1px solid var(--line)' }}>
                <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.name} <span className="muted">· {ago(s.created_at)}</span></span>
                <span className="row gap-4">
                  {s.summary.overall && <Pill tone={s.summary.overall === 'FAIL' ? 'red' : s.summary.overall === 'MARGINAL' ? 'amber' : 'green'}>{STATUS_LABEL[s.summary.overall]}</Pill>}
                  <Button size="sm" variant="ghost" onClick={() => replaceConfig(s.config)}>Load</Button>
                </span>
              </div>
            )) : <p className="small muted">No saved scenarios yet. Use “Save scenario” in the top bar to keep a snapshot of these inputs.</p>}
          </Card>
          <Card title="Next">
            <div className="row wrap">
              <Button size="sm" onClick={() => nav(`/p/${pid}/twin`)}><Box size={13} />Open the 3-D twin</Button>
              <Button size="sm" onClick={() => nav(`/p/${pid}/compare`)}><Layers size={13} />Compare shield options</Button>
              <Button size="sm" onClick={() => nav(`/p/${pid}/report`)}><FileText size={13} />Build a report</Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
