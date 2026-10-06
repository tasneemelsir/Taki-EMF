import { useEffect, useMemo, useRef, useState } from 'react';
import { CheckCircle2, Download, Upload, XCircle } from 'lucide-react';
import { Plot } from '@/components/Plot';
import { Accordion, Busy, Button, Card, ErrorNote, Metric, Note, PageHead, Pill, Select, Switch, Tabs } from '@/components/ui';
import { api } from '@/lib/api';
import { validationFigure } from '@/lib/charts';
import { fmt } from '@/lib/format';
import { useGet } from '@/lib/hooks';
import { useStore } from '@/lib/store';
import { Loading } from './common';

interface Check { id: string; title: string; detail: string; expected: number; got: number; unit: string; error_pct: number; tolerance_pct: number; passed: boolean }
interface Dataset { id: string; label: string; line_type: string; phasing: string; ground_conducting: boolean | null; geometry_available: boolean; points: { location: string; distance_m: number | null; comparable: boolean; b_uT: number | null; e_kVm: number | null }[] }
interface Source { id: string; title: string; data_type: string; data_type_label: string; citation: string; short: string; doi: string; url: string; license: string; provenance: string[]; caveats: { id: string; affects: string; severity: string; status: string; summary: string; detail: string }[]; datasets: Dataset[] }
interface Catalogue { sources: Source[]; bibliography: { kind: string; authors: string; title: string; container: string; year: number; doi: string | null; relevance: string }[] }
interface Result {
  label: string; kind_label: string; basis: string; ground_label: string; height: number; excluded: string[]; notes: string[];
  /** false: a published dataset compared with the open project instead of that source's own tower */
  like_for_like: boolean | null;
  rmse: number; nrmse: number; mape: number | null; mape_used: number; mape_excluded: number; mean_ratio: number | null; ratio_over_sqrt2: number | null;
  n_outside: number; domain: number[]; n_points: number; curve: { x: number[]; b: number[] };
  points: { distance: number; taki: number; reference: number; delta: number; ratio: number | null }[];
  e_points: { distance: number; taki: number; reference: number; ratio: number | null }[];
}

export default function ValidationPage() {
  const config = useStore((s) => s.config);
  const physKey = useStore((s) => s.physKey);
  const checks = useGet<{ checks: Check[] }>('/validation/checks');
  const cat = useGet<Catalogue>('/validation/catalogue');
  const [mode, setMode] = useState<'published' | 'own'>('published');
  const [dsId, setDsId] = useState('');
  const [geom, setGeom] = useState(true);
  const [withShield, setWithShield] = useState(false);
  const shieldOn = useStore((s) => !!s.sol?.shield.on);
  const [matchGround, setMatchGround] = useState(true);
  const [csvText, setCsvText] = useState<string | null>(null);
  const [csvName, setCsvName] = useState('');
  const [res, setRes] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const datasets = useMemo(() => cat.data?.sources.flatMap((s) => s.datasets.map((d) => ({ ...d, source: s }))) ?? [], [cat.data]);
  useEffect(() => { if (!dsId && datasets.length) setDsId((datasets.find((d) => d.geometry_available && d.points.some((p) => p.comparable)) ?? datasets[0]).id); }, [datasets, dsId]);
  const ds = datasets.find((d) => d.id === dsId);

  useEffect(() => {
    if (!config) return;
    if (mode === 'published' && !dsId) return;
    if (mode === 'own' && csvText === null) { setRes(null); return; }
    let live = true;
    setBusy(true);
    const body = mode === 'own' ? { config, csv_text: csvText, with_shield: withShield } : { config, dataset_id: dsId, use_published_geometry: geom && !!ds?.geometry_available, match_ground: matchGround };
    const t = window.setTimeout(() => {
      api.post<Result>('/validation/compare', body).then((r) => { if (live) { setRes(r); setError(null); } })
        .catch((e) => { if (live) { setError(e.message); setRes(null); } }).finally(() => { if (live) setBusy(false); });
    }, 200);
    return () => { live = false; window.clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, dsId, geom, matchGround, csvText, withShield, physKey]);

  const mismatch = res?.like_for_like === false;
  const fig = useMemo(() => (res ? validationFigure(res.curve, res.points, res.label,
    res.like_for_like === false ? 'Taki on YOUR project (a different tower)' : res.like_for_like ? "Taki on the source's tower" : 'Taki (calculated)',
    res.like_for_like === false) : null), [res]);
  const passed = checks.data?.checks.filter((c) => c.passed).length ?? 0;

  return (
    <div className="page">
      <PageHead title="Validation" lede="Three different things, kept apart: verification (does the code solve its equations correctly), code-to-code comparison (does it agree with another solver), and validation (does the model match measurements). A model is not validated because it runs." />

      <Card title="1 · Solver verification" sub={checks.data ? `${passed} of ${checks.data.checks.length} checks pass` : ''} className="mb-12">
        <p className="small muted">Each check compares the solver with an analytical result. They run on this server, on the code you are using.</p>
        <ErrorNote error={checks.error} />
        {!checks.data ? <Loading /> : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Check</th><th className="num">Expected</th><th className="num">Calculated</th><th className="num">Error</th><th className="num">Tolerance</th><th>Result</th></tr></thead>
              <tbody>
                {checks.data.checks.map((c) => (
                  <tr key={c.id}>
                    <td>{c.title}<div className="tiny muted">{c.detail}</div></td>
                    <td className="num">{fmt(c.expected, 5)} {c.unit.replace('uT', 'µT')}</td><td className="num">{fmt(c.got, 5)} {c.unit.replace('uT', 'µT')}</td>
                    <td className="num">{c.error_pct < 1e-6 ? '< 0.000001%' : `${c.error_pct.toPrecision(2)}%`}</td><td className="num">{c.tolerance_pct < 0.001 ? 'exact' : `${c.tolerance_pct}%`}</td>
                    <td>{c.passed ? <span className="row gap-4 good"><CheckCircle2 size={14} />Pass</span> : <span className="row gap-4 bad"><XCircle size={14} />Fail</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="2 · Comparison with reference data" className="mb-12">
        <Tabs value={mode} onChange={setMode} options={[{ value: 'published', label: 'Published reference (code-to-code)' }, { value: 'own', label: 'Your own survey (validation)' }]} />
        {mode === 'published' ? (
          cat.data ? (
            <>
              <div className="row wrap gap-12" style={{ alignItems: 'flex-end' }}>
                <div style={{ flex: '1 1 320px' }}><div className="small mb-8" style={{ fontWeight: 500 }}>Dataset</div>
                  <Select value={dsId} onChange={setDsId} options={datasets.map((d) => ({ value: d.id, label: `${d.label}${d.geometry_available ? '' : ' (no published geometry)'}` }))} /></div>
                <Switch checked={geom && !!ds?.geometry_available} disabled={!ds?.geometry_available} onChange={setGeom} label="Run Taki on the source's tower geometry" />
                <Switch checked={matchGround} onChange={setMatchGround} disabled={!(geom && ds?.geometry_available)} label="Match its ground condition" />
              </div>
              {ds && <div className="cite mt-12"><b>{ds.source.data_type_label}</b><br />{ds.source.citation}{ds.source.license && <><br />Data licence: {ds.source.license}</>}</div>}
              {ds && !ds.geometry_available && <Note>The source did not publish tower geometry for this line type in the article, so Taki can only be run on your current project. That is not a like-for-like comparison: use a dataset that has its geometry.</Note>}
            </>
          ) : <Loading />
        ) : (
          <div className="row wrap gap-12">
            <Button onClick={() => file.current?.click()}><Upload size={14} />Upload field-meter CSV</Button>
            <a className="btn" href="/api/validation/template.csv" download><Download size={14} />Download the template</a>
            <span className="small muted">{csvName ? `Loaded ${csvName}.` : 'Columns: Distance (m from centreline) and B_Field (µT).'}</span>
            <input ref={file} type="file" accept=".csv,text/csv,text/plain" className="hide" onChange={async (e) => { const f = e.target.files?.[0]; if (f) { setCsvText(await f.text()); setCsvName(f.name); } e.target.value = ''; }} />
            {shieldOn && <Switch checked={withShield} onChange={setWithShield} label="Measured with the shield in place" />}
          </div>
        )}
        <ErrorNote error={error} />

        {res && fig && (
          <div className="mt-16" style={{ position: 'relative' }}>
            <Busy on={busy} />
            <p className="small muted">Taki calculated on <b>{res.basis}</b> · {res.ground_label} · {res.height} m above ground.</p>
            {mismatch && (
              <Note kind="bad" className="mb-12">
                <b>Not like for like: do not read this as an error of the solver.</b> The reference values belong to the source's tower; the curve is your own project, which is a different line. The gap between them only says the two lines differ.
                {ds?.geometry_available
                  ? <> Switch on “Run Taki on the source's tower geometry” above to compare the same tower.</>
                  : <> The source did not publish this tower's geometry, so a like-for-like run is not possible for this dataset. Choose one marked with geometry (275/132 kV quadruple circuit or 500 kV double circuit).</>}
              </Note>
            )}
            <div className="grid c4 mb-12" style={mismatch ? { opacity: 0.55 } : undefined} title={mismatch ? 'These figures compare two different lines' : undefined}>
              <Metric label="RMSE" value={fmt(res.rmse)} unit="µT" sub={`${res.n_points} point${res.n_points === 1 ? '' : 's'}`} />
              <Metric label="NRMSE" value={res.nrmse !== null && Number.isFinite(res.nrmse) ? res.nrmse.toFixed(1) : 'n/a'} unit="%" sub="normalised by the reference range" />
              <Metric label="MAPE" value={res.mape !== null ? res.mape.toFixed(1) : 'n/a'} unit="%" sub={`${res.mape_used} used, ${res.mape_excluded} near-zero excluded`} />
              <Metric label="Mean ratio" value={res.mean_ratio !== null ? res.mean_ratio.toFixed(4) : 'n/a'} unit="×" sub={res.ratio_over_sqrt2 !== null ? `÷ √2 = ${res.ratio_over_sqrt2.toFixed(4)}` : 'Taki ÷ reference'} />
            </div>
            {res.notes.map((n, i) => <Note key={i} kind="info">{n}</Note>)}
            {res.excluded.length > 0 && <Note>{res.excluded.length === 1 ? '1 point is' : `${res.excluded.length} points are`} left out ({res.excluded.map((e) => e.replace(/_/g, ' ')).join(', ')}): the source does not state the distance {res.excluded.length === 1 ? 'it corresponds' : 'they correspond'} to, so {res.excluded.length === 1 ? 'it' : 'they'} cannot be placed on a distance axis.</Note>}
            {res.n_outside > 0 && <Note>{res.n_outside === 1 ? '1 reference point falls' : `${res.n_outside} reference points fall`} outside the calculated range ({res.domain[0]} to {res.domain[1]} m); {res.n_outside === 1 ? 'that comparison is' : 'those comparisons are'} not meaningful.</Note>}
            <div className="plot-card mt-12"><Plot data={fig.data} layout={fig.layout} height={400} filename="taki-validation" /></div>
            <div className="grid c2 mt-12">
              <div className="table-wrap">
                <table className="tbl">
                  <thead><tr><th className="num">Distance (m)</th><th className="num">Taki B (µT)</th><th className="num">Reference</th><th className="num">Δ</th><th className="num">Ratio</th></tr></thead>
                  <tbody>{res.points.map((p, i) => <tr key={i}><td className="num">{p.distance}</td><td className="num">{fmt(p.taki, 4)}</td><td className="num">{fmt(p.reference, 4)}</td><td className="num">{fmt(p.delta)}</td><td className="num">{p.ratio !== null ? p.ratio.toFixed(4) : '—'}</td></tr>)}</tbody>
                </table>
              </div>
              {res.e_points.length > 0 && (
                <div>
                  <div className="table-wrap">
                    <table className="tbl">
                      <thead><tr><th className="num">Distance (m)</th><th className="num">Taki E (kV/m)</th><th className="num">Reference</th><th className="num">Ratio</th></tr></thead>
                      <tbody>{res.e_points.map((p, i) => <tr key={i}><td className="num">{p.distance}</td><td className="num">{fmt(p.taki, 4)}</td><td className="num">{fmt(p.reference, 4)}</td><td className="num">{p.ratio !== null ? p.ratio.toFixed(3) : '—'}</td></tr>)}</tbody>
                    </table>
                  </div>
                  <p className="tiny muted mt-4">The source publishes no conductor radius or bundling, which the electric field depends on, so its E values are indicative only.</p>
                </div>
              )}
            </div>
          </div>
        )}
      </Card>

      {cat.data?.sources.map((s) => s.caveats.length > 0 && (
        <Accordion key={s.id} title={`Known comparison caveats — ${s.short}`} defaultOpen>
          {s.caveats.map((c) => (
            <div key={c.id} className="note mb-8" style={{ borderLeftColor: c.severity === 'high' ? 'var(--red)' : c.severity === 'none' ? 'var(--green)' : 'var(--amber)', background: 'var(--card)' }}>
              <b>[{c.affects}] {c.summary}</b> <Pill>{c.status}</Pill><br />{c.detail}
            </div>
          ))}
          {s.provenance.length > 0 && <><div className="eyebrow mt-12">Provenance and method</div><ul className="small" style={{ margin: 0, paddingLeft: 18 }}>{s.provenance.map((p, i) => <li key={i}>{p}</li>)}</ul></>}
        </Accordion>
      ))}
      <Accordion title="Further sources (citation only)">
        <p className="small muted">No third-party data is redistributed. Only the CC0-licensed dataset ships with values; the rest are cited so you can obtain and digitise them yourself with the template above.</p>
        {cat.data?.bibliography.map((e, i) => (
          <div className="cite" key={i}><b>[{e.kind}]</b> {[e.authors, `“${e.title}”`, e.container, String(e.year)].filter(Boolean).join('. ')}<br /><i>{e.relevance}</i>{e.doi && <div className="doi">doi:{e.doi}</div>}</div>
        ))}
      </Accordion>
    </div>
  );
}
