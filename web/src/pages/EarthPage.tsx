import { useMemo } from 'react';
import { Plot } from '@/components/Plot';
import { Busy, Card, ErrorNote, Metric, Note, PageHead, Pill } from '@/components/ui';
import { barFigure, envelopeFigure } from '@/lib/charts';
import { fmt } from '@/lib/format';
import { useRemote } from '@/lib/hooks';
import { useStore } from '@/lib/store';
import { Loading } from './common';

interface Env { x: number[]; free: number[]; perfect: number[]; selected: number[] | null; selected_label: string; peak_free: number; peak_perfect: number; ratio: number | null; soil_sweep: { soil: string; rho: number; peak_b: number }[] }

export default function EarthPage() {
  const sol = useStore((s) => s.sol);
  const lib = useStore((s) => s.library);
  const env = useRemote<Env>('/earth');
  const fig = useMemo(() => (env.data && sol ? envelopeFigure(env.data, sol) : null), [env.data, sol]);
  const soil = useMemo(() => (env.data ? barFigure(env.data.soil_sweep.map((s) => s.soil), env.data.soil_sweep.map((s) => s.peak_b), { ytitle: 'Peak B (µT)', unit: 'µT' }) : null), [env.data]);
  if (!sol) return <div className="page"><Loading /></div>;
  return (
    <div className="page">
      <PageHead title="Earth sensitivity" lede="Free space and perfectly conducting earth are the two exact limits of earth resistivity, so real earth always lies between them. The shaded band is a defensible bound that does not depend on arguing for one soil value." />
      <ErrorNote error={env.error} />
      <div className="grid c4 mb-12">
        <Metric label="Peak · free space" value={env.data ? fmt(env.data.peak_free) : '—'} unit="µT" sub="ρ → ∞, no earth return" />
        <Metric label="Peak · conducting earth" value={env.data ? fmt(env.data.peak_perfect) : '—'} unit="µT" sub="ρ → 0, mirror image" />
        <Metric label="Envelope ratio" value={env.data?.ratio ? env.data.ratio.toFixed(2) : '—'} unit="×" sub="conducting ÷ free space" />
        <Metric label="Selected model" value={sol.corridor.ground_short} small sub={`peak ${fmt(sol.peak_b)} µT`} />
      </div>
      <div className="plot-card" style={{ position: 'relative' }}>
        <Busy on={env.loading} />
        <div className="head"><h3>Earth-return envelope</h3><span className="sub">magnetic field at {sol.corridor.meas_height} m above ground</span></div>
        {fig ? <Plot data={fig.data} layout={fig.layout} height={440} filename="taki-earth-envelope" /> : <Loading />}
      </div>
      <div className="grid split mt-16">
        <div className="plot-card">
          <div className="head"><h3>Peak B across soil types</h3><span className="sub">finite-resistivity (complex-image) model</span></div>
          {soil ? <Plot data={soil.data} layout={soil.layout} height={320} toolbar={false} /> : <Loading />}
          <div style={{ padding: '0 14px 12px' }}><Note>The finite-resistivity model has not been validated against reference data. Use this chart to see the trend, and the two limits above to bound a reported value.</Note></div>
        </div>
        <Card title="The three ground models">
          {lib?.ground_models.map((m) => (
            <div key={m.id} className="mb-12">
              <div className="row gap-4"><b className="small">{m.label}</b>{m.id === sol.corridor.ground_model && <Pill tone="blue">selected</Pill>}{!m.validated && <Pill tone="amber">not validated</Pill>}</div>
              <div className="small muted">{m.description}</div>
              {m.caution && <div className="small" style={{ color: 'var(--amber)' }}>{m.caution}</div>}
            </div>
          ))}
          <p className="small muted">The electric field always uses a conducting ground plane (method of images), which is the right model for soil at 50/60 Hz.</p>
        </Card>
      </div>
    </div>
  );
}
