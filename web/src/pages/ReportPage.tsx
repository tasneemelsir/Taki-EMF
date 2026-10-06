import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Camera, FileDown, FileText, Sparkles } from 'lucide-react';
import { AiSetup, useAiChoice } from '@/components/AiSetup';
import { Badge, Busy, Button, Card, ErrorNote, Field, Note, PageHead, Spinner, Tabs, TextInput } from '@/components/ui';
import { api, saveText } from '@/lib/api';
import { STATUS_VAR, localStamp } from '@/lib/format';
import { useStore } from '@/lib/store';
import { Loading } from './common';

type Block = { type: string; text?: string; level?: number; status?: string; header?: string[]; rows?: string[][]; items?: string[]; title?: string; caption?: string; status_col?: number };
interface Doc { title: string; subtitle: string; project: string; author: string; organisation: string; date: string; blocks: Block[] }

function load<T>(key: string, fallback: T): T {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
}

export default function ReportPage() {
  const { config, physKey, library, project, user, aiNarrative, setAiNarrative, twinShot, toast } = useStore();
  const ai = useAiChoice();
  const { pid } = useParams();
  const nav = useNavigate();
  const cat = library?.report;
  const [sections, setSections] = useState<Record<string, boolean>>(() => load('taki.report.sections', {}));
  const [figures, setFigures] = useState<Record<string, boolean>>(() => load('taki.report.figures', {}));
  const [author, setAuthor] = useState(user?.is_guest ? '' : user?.name ?? '');
  const [org, setOrg] = useState(user?.organisation ?? '');
  const objKey = `taki.report.objective.${pid}`;
  const [objective, setObjective] = useState(() => { try { return localStorage.getItem(objKey) ?? ''; } catch { return ''; } });
  const [objectiveSent, setObjectiveSent] = useState(objective);
  useEffect(() => {                                  // typing does not refresh the preview on every key
    try { objective ? localStorage.setItem(objKey, objective) : localStorage.removeItem(objKey); } catch { /* ignore */ }
    const t = window.setTimeout(() => setObjectiveSent(objective), 700);
    return () => window.clearTimeout(t);
  }, [objective, objKey]);
  const [tab, setTab] = useState<'preview' | 'text'>('preview');
  const [doc, setDoc] = useState<{ doc: Doc; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [building, setBuilding] = useState<string | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  const pointsKey = JSON.stringify(config?.points ?? []);

  const sec = useMemo(() => Object.fromEntries((cat?.sections ?? []).map((s) => [s.id, sections[s.id] ?? s.default])), [cat, sections]);
  const figs = useMemo(() => Object.fromEntries((cat?.figures ?? []).map((s) => [s.id, figures[s.id] ?? s.default])), [cat, figures]);
  useEffect(() => { try { localStorage.setItem('taki.report.sections', JSON.stringify(sections)); localStorage.setItem('taki.report.figures', JSON.stringify(figures)); } catch { /* ignore */ } }, [sections, figures]);

  const scenarioCount = project?.scenarios.length ?? 0;
  const options = useMemo(() => ({
    sections: sec, figures: figs, author, organisation: org, ai_narrative: aiNarrative || null,
    objective: objectiveSent.trim() || null,
    scenarios: sec.scenarios ? (project?.scenarios ?? []).map((s) => ({ name: s.name, config: s.config })) : null,
    project: { name: project?.name ?? '', description: project?.description ?? '' },
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [sec, figs, author, org, aiNarrative, objectiveSent, scenarioCount, project?.name, project?.description]);

  useEffect(() => {
    if (!config) return;
    let live = true;
    setBusy(true);
    const t = window.setTimeout(() => {
      api.post<{ doc: Doc; text: string }>('/report/preview', { config, options: { ...options, generated: localStamp() } }).then((r) => { if (live) { setDoc(r); setError(null); } })
        .catch((e) => { if (live) setError(e.message); }).finally(() => { if (live) setBusy(false); });
    }, 350);
    return () => { live = false; window.clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [physKey, pointsKey, options]);

  const download = async (fmt: 'pdf' | 'docx' | 'txt') => {
    setBuilding(fmt);
    try {
      await api.download(`/report/${fmt}`, { config, options: { ...options, generated: localStamp(), twin_png: figs.twin ? twinShot : null } });
    } catch (e: any) { toast(e?.message ?? 'The report could not be built.', 'error'); }
    setBuilding(null);
  };

  const generate = async () => {
    setAiBusy(true);
    try {
      if (!ai) return;
      const r = await api.post<{ text: string; model: string }>('/ai/narrative', { config, provider: ai.provider.id, api_key: ai.key, model: ai.model });
      setAiNarrative(r.text);
      toast(`Narrative drafted by ${r.model}. Review it before you export.`);
    } catch (e: any) { toast(e?.message ?? 'The narrative could not be generated.', 'error'); }
    setAiBusy(false);
  };
  if (!config || !cat) return <div className="page"><Loading /></div>;

  return (
    <div className="page wide">
      <PageHead title="Report" lede="A structured engineering report built from the current results: configuration, method, standards assessment, shield, receptors, measurement points, limitations and references. Nothing in it is written by AI unless you add the optional narrative.">
        <Button variant="primary" onClick={() => download('pdf')} disabled={!!building}>{building === 'pdf' ? <Spinner /> : <FileDown size={14} />}PDF</Button>
        <Button onClick={() => download('docx')} disabled={!!building}>{building === 'docx' ? <Spinner /> : <FileDown size={14} />}Word</Button>
        <Button onClick={() => download('txt')} disabled={!!building}>{building === 'txt' ? <Spinner /> : <FileText size={14} />}Text</Button>
      </PageHead>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(260px, 330px) minmax(0, 1fr)', alignItems: 'start' }}>
        <div className="col gap-12">
          <Card title="Cover">
            <Field label="Prepared by"><TextInput value={author} onChange={setAuthor} maxLength={80} placeholder="Your name" /></Field>
            <Field label="Organisation"><TextInput value={org} onChange={setOrg} maxLength={120} /></Field>
            <Field label="Objective" hint="optional">
              <textarea className="textarea" rows={3} maxLength={2000} value={objective} onChange={(e) => setObjective(e.target.value)} placeholder="What the study is for, e.g. whether a school can be built 30 m from the line." />
            </Field>
            <p className="tiny muted mt-8">The project name and description come from the project; rename it in the top bar.</p>
          </Card>
          <Card title="Sections">
            <div className="col gap-4">
              {cat.sections.map((s) => (
                <label key={s.id} className="row small" style={{ cursor: 'pointer', alignItems: 'flex-start' }}>
                  <input type="checkbox" checked={!!sec[s.id]} onChange={(e) => setSections({ ...sections, [s.id]: e.target.checked })} style={{ marginTop: 3 }} />
                  <span>{s.label}{s.hint && <span className="tiny muted" style={{ display: 'block' }}>{s.id === 'scenarios' && !scenarioCount ? 'no saved scenarios in this project yet' : s.hint}</span>}</span>
                </label>
              ))}
            </div>
          </Card>
          <Card title="Figures" sub="PDF and Word">
            <div className="col gap-4">
              {cat.figures.map((s) => <label key={s.id} className="row small" style={{ cursor: 'pointer' }}><input type="checkbox" checked={!!figs[s.id]} onChange={(e) => setFigures({ ...figures, [s.id]: e.target.checked })} />{s.label}</label>)}
            </div>
            {figs.twin && (twinShot
              ? <div className="mt-8"><img src={twinShot} alt="Captured view of the 3-D twin" style={{ width: '100%', borderRadius: 5, border: '1px solid var(--line)' }} /><p className="tiny muted mt-4">Captured from the twin. Recapture there to change the view.</p></div>
              : <Note kind="info" className="mt-8">No 3-D view captured yet. <button className="btn ghost sm" onClick={() => nav(`/p/${pid}/twin`)}><Camera size={12} />Open the twin</button> and use “Capture for report”.</Note>)}
          </Card>
          <Card title={<span className="row gap-4"><Sparkles size={14} />AI narrative</span>} sub="optional">
            <p className="small muted">Sends the computed results to the AI service you choose, with your own key, to draft a narrative section. The compliance result always comes from the standards engine; the model is told to restate it, not decide it, and its text is labelled as AI-drafted in the report.</p>
            <AiSetup />
            <div className="row mt-12">
              <Button variant="primary" onClick={generate} disabled={aiBusy || !ai?.ready} title={ai?.ready ? undefined : 'Enter your API key first'}>{aiBusy ? <Spinner /> : <Sparkles size={13} />}{aiNarrative ? 'Draft again' : 'Draft narrative'}</Button>
              {aiNarrative && <Button variant="ghost" onClick={() => setAiNarrative('')}>Remove</Button>}
            </div>
            {aiNarrative && <Field label="Review and edit" className="mt-12"><textarea className="textarea" rows={10} value={aiNarrative} onChange={(e) => setAiNarrative(e.target.value)} /></Field>}
          </Card>
        </div>

        <div style={{ position: 'relative', minWidth: 0 }}>
          <Busy on={busy} />
          <ErrorNote error={error} />
          <Tabs value={tab} onChange={setTab} options={[{ value: 'preview', label: 'Preview' }, { value: 'text', label: 'Plain text' }]} />
          {!doc ? <Loading /> : tab === 'text' ? (
            <>
              <textarea className="textarea mono" readOnly value={doc.text} rows={30} style={{ fontSize: 12 }} />
              <div className="row mt-8"><Button size="sm" onClick={() => { void navigator.clipboard?.writeText(doc.text); toast('Copied.'); }}>Copy</Button><Button size="sm" onClick={() => saveText(doc.text, 'taki_report.txt')}>Save .txt</Button></div>
            </>
          ) : <ReportPreview doc={doc.doc} />}
        </div>
      </div>
    </div>
  );
}

/** Keep a number and its unit together, as the PDF does. */
const nb = (s: string) => s.replace(/(\d) (?=(?:µT|kV\/m|kV|mm|m|A|dB|Hz|W)(?![A-Za-z]))/g, '$1\u00a0').replace(/([xyz]) = (?=[-+−]?\d)/g, '$1\u00a0=\u00a0');

function ReportPreview({ doc }: { doc: Doc }) {
  return (
    <div className="report-preview">
      <h1>{doc.title}</h1>
      <p style={{ margin: '4px 0' }}>{doc.subtitle}</p>
      <p className="capt">{[doc.project && `Project: ${doc.project}`, doc.author && `Prepared by: ${doc.author}`, doc.organisation, `Generated: ${doc.date}`].filter(Boolean).join('  |  ')}</p>
      {doc.blocks.map((b, i) => {
        if (b.type === 'heading') return b.level === 2 ? <h3 key={i}>{b.text}</h3> : <h2 key={i}>{b.text}</h2>;
        if (b.type === 'para') return <div key={i}>{(b.text ?? '').split('\n').filter((p) => p.trim()).map((p, k) => <p key={k}>{p}</p>)}</div>;
        if (b.type === 'note') return <p key={i} className="capt">{b.text}</p>;
        if (b.type === 'bullets') return <ul key={i}>{b.items?.map((it, k) => <li key={k}>{it}</li>)}</ul>;
        if (b.type === 'status') return <div key={i} className="status" style={{ borderLeftColor: STATUS_VAR[b.status ?? ''] ?? 'var(--steel)', color: STATUS_VAR[b.status ?? ''] ?? 'var(--ink)' }}>{b.text}</div>;
        if (b.type === 'table') return (
          <div key={i} className="table-wrap" style={{ margin: '6px 0 8px' }}>
            <table className="tbl">
              {b.header && <thead><tr>{b.header.map((h, k) => <th key={k}>{h}</th>)}</tr></thead>}
              <tbody>{b.rows?.map((r, k) => <tr key={k}>{r.map((c, j) => <td key={j}>{b.status_col === j && ['PASS', 'MARGINAL', 'FAIL', 'NOT ASSESSED'].includes(c) ? <Badge status={c.replace(' ', '_')} /> : nb(c)}</td>)}</tr>)}</tbody>
            </table>
          </div>
        );
        return null;
      })}
      <p className="capt mt-16">Figures are added to the PDF and Word files.</p>
    </div>
  );
}
