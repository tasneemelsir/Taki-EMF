import { useEffect, useMemo, useRef, useState } from 'react';
import { Copy, Download, FolderInput, MoreHorizontal, Pencil, Save, Trash2, Upload } from 'lucide-react';
import { Plot } from '@/components/Plot';
import { Badge, Busy, Button, Card, Confirm, ErrorNote, Field, MenuButton, Modal, Note, PageHead, Pill, Switch, TextInput } from '@/components/ui';
import { api, saveText } from '@/lib/api';
import { overlayFigure } from '@/lib/charts';
import { ago, change, fmt } from '@/lib/format';
import { useStore } from '@/lib/store';
import type { Config, Scenario, ShieldHeadline, Status } from '@/lib/types';
import { Loading } from './common';

interface Cmp {
  curves: { name: string; x: number[]; b: number[]; e: number[]; bS: number[] | null }[];
  rows: { name: string; error?: string; lines: number; peak_b: number; peak_e: number; row_b: number | null; overall: Status; ground: string; freq: number; shield: string; se_b: number | null; se_e: number | null; peak_b_shield: number | null; shield_model: string | null; shield_effect: ShieldHeadline | null }[];
}

export default function ScenariosPage() {
  const { project, config, sol, physKey, replaceConfig, addScenario, deleteScenario, toast } = useStore();
  const [chosen, setChosen] = useState<string[]>([]);
  const [current, setCurrent] = useState(true);
  const [cmp, setCmp] = useState<Cmp | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<Scenario | null>(null);
  const [q, setQ] = useState<'b' | 'e'>('b');
  const [shields, setShields] = useState(true);
  const file = useRef<HTMLInputElement>(null);
  const scenarios = project?.scenarios ?? [];
  useEffect(() => { setChosen((c) => (c.length ? c.filter((id) => scenarios.some((s) => s.id === id)) : scenarios.slice(0, 3).map((s) => s.id))); /* eslint-disable-next-line */ }, [scenarios.length]);

  useEffect(() => {
    const items = scenarios.filter((s) => chosen.includes(s.id)).map((s) => ({ name: s.name, config: s.config }));
    if (current && config) items.push({ name: 'Current inputs', config });
    if (!items.length) { setCmp(null); return; }
    let live = true;
    setBusy(true);
    const t = window.setTimeout(() => {
      api.post<Cmp>('/scenarios/compare', { items }).then((r) => { if (live) { setCmp(r); setError(null); } })
        .catch((e) => { if (live) setError(e.message); }).finally(() => { if (live) setBusy(false); });
    }, 200);
    return () => { live = false; window.clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chosen, current, physKey, scenarios.length]);

  const anyShield = !!cmp?.curves.some((c) => c.bS);
  const fig = useMemo(() => {
    if (!cmp) return null;
    const curves: { name: string; x: number[]; y: number[]; dash?: string; ci?: number }[] = [];
    cmp.curves.forEach((c, i) => {
      curves.push({ name: c.name, x: c.x, y: q === 'b' ? c.b : c.e, ci: i });
      if (q === 'b' && shields && c.bS) curves.push({ name: `${c.name} · with its shield`, x: c.x, y: c.bS, dash: 'dash', ci: i });
    });
    return overlayFigure(curves, sol, q === 'b' ? 'B field (µT)' : 'E field (kV/m)', q === 'b' ? 'B' : 'E');
  }, [cmp, sol, q, shields]);

  const importFile = async (f: File) => {
    try {
      const raw = JSON.parse(await f.text());
      const { config: cfg, migrated, notes } = await api.post<{ config: Config; migrated: boolean; notes: string[] }>('/normalise', { config: raw.config ?? raw });
      replaceConfig(cfg);
      toast(migrated ? 'Imported and converted a scenario file from an earlier version of Taki.' : 'Configuration imported.');
      for (const n of notes ?? []) toast(n);
    } catch (e: any) {
      toast(e?.message?.includes('JSON') ? 'That file is not valid JSON.' : (e?.message ?? 'Could not import that file.'), 'error');
    }
  };
  if (!project || !config) return <div className="page"><Loading /></div>;
  const slug = (n: string) => n.replace(/[^\w-]+/g, '_').replace(/^_+|_+$/g, '') || 'scenario';
  const putScenarios = (list: Scenario[]) => useStore.setState({ project: { ...useStore.getState().project!, scenarios: list } });
  const duplicate = async (s: Scenario) => {
    try {
      const r = await api.post<{ scenario: Scenario }>(`/projects/${project.id}/scenarios`, { name: `${s.name} (copy)`.slice(0, 80), note: s.note, config: s.config });
      putScenarios([...useStore.getState().project!.scenarios, r.scenario]);
      toast(`Duplicated "${s.name}".`);
    } catch (e: any) { toast(e?.message ?? 'Could not duplicate the scenario.', 'error'); }
  };
  const rename = async (s: Scenario, name: string, note: string) => {
    try {
      await api.patch(`/projects/${project.id}/scenarios/${s.id}`, { name, note });
      putScenarios(useStore.getState().project!.scenarios.map((x) => (x.id === s.id ? { ...x, name, note } : x)));
      setRenaming(null);
    } catch (e: any) { toast(e?.message ?? 'Could not rename the scenario.', 'error'); }
  };
  const exportOne = (s: Scenario) => saveText(JSON.stringify({ taki: 'project-config', schema: s.config.schema, name: s.name, note: s.note, config: s.config }, null, 2), `${slug(s.name)}.taki.json`, 'application/json');

  return (
    <div className="page">
      <PageHead title="Scenarios" lede="A scenario is a named snapshot of every input. Each one is recalculated with its own earth model, frequency, standards, buildings and shield, so the comparison is like for like.">
        <Button size="sm" variant="primary" onClick={() => addScenario(`Scenario ${scenarios.length + 1}`)}><Save size={13} />Save current as scenario</Button>
        <Button size="sm" onClick={() => saveText(JSON.stringify({ taki: 'project-config', schema: config.schema, name: project.name, config }, null, 2), `${project.name.replace(/[^\w-]+/g, '_')}.taki.json`, 'application/json')}><Download size={13} />Export inputs</Button>
        <Button size="sm" onClick={() => file.current?.click()}><Upload size={13} />Import</Button>
        <input ref={file} type="file" accept=".json,application/json" className="hide" onChange={(e) => { const f = e.target.files?.[0]; if (f) void importFile(f); e.target.value = ''; }} />
      </PageHead>

      <div className="grid split">
        <Card title="Saved scenarios" sub={`${scenarios.length} in this project`}>
          {scenarios.length === 0 ? <p className="small muted">None yet. Set up a case, then save it. Importing accepts files exported here and scenario files from earlier versions of Taki.</p> : (
            <div className="table-wrap">
              <table className="tbl">
                <thead><tr><th style={{ width: 28 }} /><th>Name</th><th className="num">Peak B</th><th className="num">Peak E</th><th>Result</th><th /></tr></thead>
                <tbody>
                  {scenarios.map((s) => (
                    <tr key={s.id}>
                      <td><input type="checkbox" aria-label={`Compare ${s.name}`} checked={chosen.includes(s.id)} onChange={() => setChosen((c) => (c.includes(s.id) ? c.filter((x) => x !== s.id) : [...c, s.id]))} /></td>
                      <td>{s.name}<div className="tiny muted">{s.note ? `${s.note} · ` : ''}{ago(s.created_at)}</div></td>
                      <td className="num">{s.summary.peak_b !== undefined ? fmt(s.summary.peak_b) : '—'}</td>
                      <td className="num">{s.summary.peak_e !== undefined ? fmt(s.summary.peak_e) : '—'}</td>
                      <td>{s.summary.overall ? <Badge status={s.summary.overall} /> : '—'}</td>
                      <td className="nowrap right">
                        <Button size="sm" onClick={() => { replaceConfig(s.config); toast(`Loaded "${s.name}". Undo brings your previous inputs back.`); }}><FolderInput size={12} />Load</Button>{' '}
                        <MenuButton button={(_o, toggle) => <Button size="sm" variant="ghost" icon onClick={toggle} aria-label={`More actions for ${s.name}`}><MoreHorizontal size={14} /></Button>}>
                          {(close) => (<>
                            <button onClick={() => { close(); setRenaming(s); }}><Pencil size={14} />Rename</button>
                            <button onClick={() => { close(); void duplicate(s); }}><Copy size={14} />Duplicate</button>
                            <button onClick={() => { close(); exportOne(s); }}><Download size={14} />Export file</button>
                            <div className="sep" />
                            <button style={{ color: 'var(--red)' }} onClick={() => { close(); setConfirm(s.id); }}><Trash2 size={14} />Delete</button>
                          </>)}
                        </MenuButton>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <label className="row small mt-12" style={{ cursor: 'pointer' }}><input type="checkbox" checked={current} onChange={(e) => setCurrent(e.target.checked)} />Include the current inputs in the comparison</label>
        </Card>
        <Card title="How to use scenarios">
          <ul className="small" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
            <li>Save the base case, change one thing (phasing, loading, a second line, a shield), and save again.</li>
            <li>Tick the ones to compare. The chart overlays their profiles; the table lists the numbers.</li>
            <li><b>Load</b> replaces the current inputs with a scenario. It is one undo step.</li>
            <li>Export writes a JSON file you can send to a colleague or keep with a report.</li>
          </ul>
        </Card>
      </div>

      <ErrorNote error={error} />
      {cmp && fig && (
        <>
          <div className="plot-card mt-16" style={{ position: 'relative' }}>
            <Busy on={busy} />
            <div className="head"><h3>Lateral profile by scenario</h3><span className="sub">{q === 'b' && shields && anyShield ? 'solid: unshielded · dashed: with that scenario\'s shield' : 'unshielded field'}</span>
              <div className="tools">{anyShield && q === 'b' && <Switch checked={shields} onChange={setShields} label="Shields" />}<div className="seg sm"><button className={q === 'b' ? 'on' : ''} onClick={() => setQ('b')}>B</button><button className={q === 'e' ? 'on' : ''} onClick={() => setQ('e')}>E</button></div></div>
            </div>
            <Plot data={fig.data} layout={fig.layout} height={420} filename="taki-scenarios" />
          </div>
          <div className="table-wrap mt-12">
            <table className="tbl">
              <thead><tr><th>Scenario</th><th className="num">Lines</th><th className="num">Peak B (µT)</th><th className="num">Peak E (kV/m)</th><th className="num" title="Highest unshielded B at or beyond the edge of the right-of-way">B outside ROW</th><th>Result</th><th>Earth</th><th className="num">Hz</th><th title="The shield, and the change in the average field inside the space it protects">Shield and its effect</th><th className="num" title="Highest B on the ground-level profile with the shield in place">Peak B with shield</th></tr></thead>
              <tbody>
                {cmp.rows.map((r) => r.error ? (
                  <tr key={r.name}><td>{r.name}</td><td colSpan={9} className="bad">{r.error}</td></tr>
                ) : (
                  <tr key={r.name}>
                    <td>{r.name}</td><td className="num">{r.lines}</td><td className="num">{fmt(r.peak_b)}</td><td className="num">{fmt(r.peak_e)}</td>
                    <td className="num">{r.row_b !== null ? fmt(r.row_b) : '—'}</td><td><Badge status={r.overall} /></td><td>{r.ground}</td><td className="num">{r.freq}</td>
                    <td>{r.shield === 'off' ? <span className="muted">off</span> : <>{r.shield}{r.shield_effect && <> <Pill tone="teal" title={`${r.shield_effect.basis === 'inside' ? `Change in the average field inside ${r.shield_effect.where}` : `Change at ${r.shield_effect.where}`}`}>B {change(r.shield_effect.b_red_pct)} · E {change(r.shield_effect.e_red_pct)} {r.shield_effect.basis === 'inside' ? 'inside' : 'behind it'}</Pill></>}</>}</td>
                    <td className="num">{r.peak_b_shield !== null ? fmt(r.peak_b_shield) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Note kind="info" className="mt-8">Each result is that scenario's unshielded peak against its own selected standards.</Note>
        </>
      )}
      {renaming && <RenameScenario s={renaming} onClose={() => setRenaming(null)} onSave={(n, t) => rename(renaming, n, t)} />}
      {confirm && <Confirm title="Delete this scenario?" danger confirmLabel="Delete" onClose={() => setConfirm(null)} onConfirm={() => deleteScenario(confirm)}>The snapshot is removed from this project. The current inputs are not affected.</Confirm>}
    </div>
  );
}

function RenameScenario({ s, onClose, onSave }: { s: Scenario; onClose: () => void; onSave: (name: string, note: string) => void }) {
  const [name, setName] = useState(s.name);
  const [note, setNote] = useState(s.note);
  return (
    <Modal title="Rename scenario" onClose={onClose} footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" onClick={() => onSave(name.trim() || 'Scenario', note.trim())}>Save</Button></>}>
      <Field label="Name"><TextInput value={name} onChange={setName} autoFocus maxLength={80} /></Field>
      <Field label="Note (optional)"><TextInput value={note} onChange={setNote} maxLength={200} placeholder="What is different about this one?" /></Field>
    </Modal>
  );
}
