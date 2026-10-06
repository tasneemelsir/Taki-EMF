import { useState } from 'react';
import { ArrowRight, Download, FolderOpen, MonitorDown, Moon, Sun, Upload } from 'lucide-react';
import { AiSetup } from '@/components/AiSetup';
import { Button, Card, ErrorNote, Field, Kv, Note, NumberInput, PageHead, Pill, Segmented, Tabs } from '@/components/ui';
import { api, saveText } from '@/lib/api';
import { fmt } from '@/lib/format';
import { useRemote } from '@/lib/hooks';
import { useStore } from '@/lib/store';
import type { Config } from '@/lib/types';
import { Loading } from './common';

interface ChangeItem {
  id: string; title: string; text: string; quantity: string; unit: string; applies: boolean;
  before_label: string; after_label: string; before: number | null; after: number | null;
  current?: number | null; current_label?: string;
}

type Tab = 'model' | 'changes' | 'display' | 'data' | 'about';

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>('model');
  return (
    <div className="page" style={{ maxWidth: 1080 }}>
      <PageHead title="Settings" lede="Calculation domain and resolution, what this version computes differently from earlier ones, display, and moving a project in or out as a file." />
      <Tabs value={tab} onChange={setTab} options={[
        { value: 'model', label: 'Calculation' }, { value: 'changes', label: 'What changed' },
        { value: 'display', label: 'Display & keys' }, { value: 'data', label: 'Import / export' }, { value: 'about', label: 'About & limits' },
      ]} />
      {tab === 'model' && <ModelTab />}
      {tab === 'changes' && <ChangesTab />}
      {tab === 'display' && <DisplayTab />}
      {tab === 'data' && <DataTab />}
      {tab === 'about' && <AboutTab />}
    </div>
  );
}

function ModelTab() {
  const config = useStore((s) => s.config)!;
  const sol = useStore((s) => s.sol);
  const setConfig = useStore((s) => s.setConfig);
  const n = config.numerics;
  const set = (k: keyof Config['numerics'], v: number) => setConfig((c) => { c.numerics[k] = v; });
  return (
    <div className="grid c2">
      <Card title="Calculation domain">
        <p className="small muted">Leave a value at 0 to let Taki choose it from the line geometry, the right-of-way and the buildings.</p>
        <div className="fields-2 mt-8">
          <Field label="Lateral half-width" hint={n.x_half_width ? 'manual' : 'auto'} help="Distance either side of the centreline covered by profiles and maps.">
            <NumberInput value={n.x_half_width} onChange={(v) => set('x_half_width', v)} min={0} max={400} step={5} unit="m" />
          </Field>
          <Field label="Section height" hint={n.y_max ? 'manual' : 'auto'} help="Top of the field map and of the twin's field section.">
            <NumberInput value={n.y_max} onChange={(v) => set('y_max', v)} min={0} max={200} step={5} unit="m" />
          </Field>
        </div>
        {sol && <p className="small muted mt-12">In use now: x from {sol.domain.x_min.toFixed(0)} to {sol.domain.x_max.toFixed(0)} m, height to {sol.domain.y_max.toFixed(0)} m.</p>}
      </Card>
      <Card title="Field-map resolution">
        <p className="small muted">Finer grids sharpen the maps near conductors and take longer. Profiles and pinned points are always computed exactly and do not depend on this.</p>
        <div className="fields-2 mt-8">
          <Field label="Columns (x)"><NumberInput value={n.grid_nx} onChange={(v) => set('grid_nx', Math.round(v))} min={61} max={321} step={20} /></Field>
          <Field label="Rows (y)"><NumberInput value={n.grid_ny} onChange={(v) => set('grid_ny', Math.round(v))} min={41} max={201} step={10} /></Field>
        </div>
        <div className="row wrap mt-12">
          <Button size="sm" onClick={() => setConfig((c) => { c.numerics.grid_nx = 101; c.numerics.grid_ny = 61; })}>Fast</Button>
          <Button size="sm" onClick={() => setConfig((c) => { c.numerics.grid_nx = 141; c.numerics.grid_ny = 81; })}>Standard</Button>
          <Button size="sm" onClick={() => setConfig((c) => { c.numerics.grid_nx = 241; c.numerics.grid_ny = 141; })}>Fine</Button>
        </div>
      </Card>
      <Card title="Conventions" className="surface">
        <Kv k="Coordinates" v="x lateral · y up · z along the line" />
        <Kv k="Origin" v="centreline, ground, mid-span" />
        <Kv k="Field values" v="RMS resultant" />
        <Kv k="Magnetic field" v="flux density B in µT" />
        <Kv k="Electric field" v="unperturbed E in kV/m" />
        <Kv k="Voltage" v="line-to-line RMS, kV" />
        <Kv k="Current" v="per phase RMS, A" />
        <Kv k="Compliance" v="unshielded peak at mid-span" />
        <p className="small muted mt-12">Some published data sets quote peak (amplitude) values. Those are √2 times the RMS value reported here; the Validation page notes where that applies.</p>
      </Card>
      <Card title="What the solver does" className="surface">
        <ul className="small" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.6 }}>
          <li><b>Magnetic field</b> – phasor Biot–Savart sum over every sub-conductor, with the selected earth-return model.</li>
          <li><b>Electric field</b> – Maxwell potential coefficients with ground images; bundle-equivalent radius when enabled.</li>
          <li><b>Along the span</b> – each cross-section uses the conductor heights at that position (parabolic sag).</li>
          <li><b>Shield (physical)</b> – thin-shell boundary elements for the induced sheet currents and magnetisation; charge simulation for the electric field.</li>
          <li><b>Circuits</b> – each circuit of a tower has its own voltage, current, loading and phase order; one out of service is de-energised and earthed.</li>
          <li><b>Field lines</b> – contours of the vector potential at one instant, including the currents induced in a shield.</li>
          <li><b>Checks</b> – thirteen self-checks against exact solutions run on the Validation page.</li>
        </ul>
      </Card>
    </div>
  );
}

function ChangesTab() {
  const r = useRemote<{ items: ChangeItem[] }>('/changes');
  if (!r.data) return r.error ? <ErrorNote error={r.error} /> : <Loading label="Working out both versions for this project…" />;
  return (
    <div>
      <div className="mb-12">
        <Card title="New in version 4.3" sub="what moved since 4.2">
          <ul className="small" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.65, maxWidth: 860 }}>
            <li><b>Desktop version.</b> Taki can now be installed on a computer: its own window and icon, no sign-in, no internet once installed, projects kept on that computer. The web version hands it out as a download (account menu, <i>Taki as an app</i>).</li>
            <li><b>Install from the browser.</b> The web version can be installed as an app from Chrome, Edge or Safari: the same site in a window of its own, with an icon.</li>
            <li><b>Export all, import all.</b> The projects page writes every project with its scenarios into one file and reads such a file back in. That is the backup, and the way to carry work between the web version and the desktop version.</li>
            <li><b>Quicker to open.</b> The files of the interface are now kept by the browser between visits instead of being asked for again each time.</li>
            <li><b>4.3.1 · Examples appear at once.</b> On a small server the example projects on the projects page took many seconds to show, with nothing to say they were coming. Their numbers are now kept ready, and the page says so while it loads them.</li>
            <li><b>4.3.2 · More places to publish it.</b> Taki can now be put on Vercel as it is, free and on a whole processor, and the README compares the hosts with measured times. Nothing changes in the app itself.</li>
            <li><b>4.3.3 · Checked on the published site.</b> Reports now carry the date and time of your own clock: a published copy used its server's, which is hours away. A published copy also starts faster after a quiet spell, and the desktop download no longer carries files of older versions.</li>
          </ul>
          <p className="small muted mt-8" style={{ maxWidth: 860 }}>No calculated number changed in 4.3.</p>
        </Card>
      </div>
      <div className="mb-12">
        <Card title="New in version 4.2" sub="what moved since 4.1">
          <ul className="small" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.65, maxWidth: 860 }}>
            <li><b>4.2.1 · Electric field lines.</b> <i>Field lines</i> now has an <i>Electric E</i> view: lines traced from the wires to the ground, the shield or each other, over dotted equipotentials, played through the cycle like the magnetic ones.</li>
            <li><b>4.2.1 · Where the slice is cut.</b> The field map shows one span from the side, with the building and the shield under it; click or drag to move the cross-section anywhere along the span.</li>
            <li><b>4.2.1 · Two drawing mistakes put right.</b> Arrowheads on the magnetic field lines sat between the lines, and on a field map away from mid-span the wire dots stayed at their mid-span height. The fields themselves were right in both cases.</li>
            <li><b>Circuits one by one.</b> On a tower with more than one circuit, each can have its own voltage, rated current, loading and phase order, or be taken out of service (<i>Lines → Set separately</i>). A 275/132 kV four-circuit tower is added.</li>
            <li><b>Sag and span.</b> Span length alone never changed the mid-span reading, and still does not. Switch on <i>Sag follows the span</i> (<i>Lines → Sag and span</i>) and a longer span hangs lower, as on a real line. The lowest conductor is shown and checked against an indicative ground clearance.</li>
            <li><b>One number for a shield.</b> Everywhere (top bar, dashboard, comparisons, scenarios, twin, report) a shield is now judged on the average field inside the building it protects. The value at one point beside the wall is still given, as a second figure. The average is a true area average now, so percentages are a few points different from 4.1.</li>
            <li><b>Fair comparisons.</b> In <i>Compare options</i> each arrangement is placed sensibly for the building (a barrier wall beside it, as tall as it), not wherever the last settings left it. Free-standing shields can be moved along the line.</li>
            <li><b>Field lines.</b> Drawn as contours of the vector potential: every line closes, none stops in mid-air, and the cycle plays without waiting for the server.</li>
            <li><b>Field map.</b> The colour scale now spans the picture instead of being stretched by the few cells that touch a conductor, so a shielded space shows up dark. The map fills its panel; <i>True scale</i> draws it undistorted.</li>
            <li><b>AI narrative.</b> Claude, Gemini or ChatGPT, each person with their own key, kept in their own browser.</li>
            <li><b>Report.</b> No with-shield columns when there is no shield, each reference listed once, tables kept whole on a page, numbers kept with their units.</li>
          </ul>
        </Card>
      </div>
      <h3 className="mb-8" style={{ fontSize: 14 }}>Corrections since the first versions of Taki</h3>
      <Note kind="info" className="mb-12">Each card recomputes <b>this project</b> under the earlier assumption and under the current one, so you can see how much every correction matters for your case. Static corrections (the standards register) are listed at the end.</Note>
      <div className="col gap-12">
        {r.data.items.map((it) => {
          const delta = it.before !== null && it.after !== null && it.before !== 0 && it.unit !== '%' ? 100 * (it.after - it.before) / Math.abs(it.before) : null;
          return (
            <Card key={it.id} title={it.title} actions={it.applies ? (delta !== null && Math.abs(delta) >= 0.05 ? <Pill tone={Math.abs(delta) >= 10 ? 'amber' : 'blue'}>{delta > 0 ? '+' : '−'}{Math.abs(delta).toFixed(Math.abs(delta) < 10 ? 1 : 0)}% for this project</Pill> : it.unit === '%' ? null : <Pill>no difference here</Pill>) : <Pill>not active in this project</Pill>}>
              <p className="small" style={{ maxWidth: 820 }}>{it.text}</p>
              {it.before !== null && it.after !== null && (
                <div className="row wrap gap-16 mt-8" style={{ alignItems: 'stretch' }}>
                  <Compare label={it.before_label} value={it.before} unit={it.unit} quantity={it.quantity} muted />
                  <div className="row muted"><ArrowRight size={16} /></div>
                  <Compare label={it.after_label} value={it.after} unit={it.unit} quantity={it.quantity} />
                  {it.current !== undefined && it.current !== null && <Compare label={`Selected: ${it.current_label}`} value={it.current} unit={it.unit} quantity={it.quantity} accent />}
                </div>
              )}
            </Card>
          );
        })}
        <Card title="Exposure standards re-checked against their sources">
          <ul className="small" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.65, maxWidth: 860 }}>
            <li>The entry labelled “MS 2332-1:2009” could not be confirmed as a published standard. It is now “Malaysia (ICNIRP 1998 basis)”, with the same numbers (100 µT, 5 kV/m at 50 Hz), and is flagged <i>verify</i>.</li>
            <li>Slovenia and Italy were one combined entry. They are now separate: Slovenia 10 µT / 0.5 kV/m for new sources near sensitive areas; Italy 100 µT limit, 10 µT attention value and 3 µT quality objective.</li>
            <li>Limits follow the frequency: ICNIRP 1998 is 5000/f µT and 250/f kV/m, so 60 Hz systems are checked against 83.3 µT and 4.17 kV/m rather than the 50 Hz numbers.</li>
            <li>The margin shown on the dashboard is the tighter of B and E. Earlier versions looked at B only.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}

function Compare({ label, value, unit, quantity, muted, accent }: { label: string; value: number; unit: string; quantity: string; muted?: boolean; accent?: boolean }) {
  const text = unit === '%' ? `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value).toFixed(1)}` : fmt(value);
  return (
    <div className="metric" style={{ minWidth: 210, flex: '0 1 250px', background: muted ? 'var(--surface)' : undefined }}>
      <div className="label" title={label}>{label}</div>
      <div className="value sm" style={{ color: muted ? 'var(--steel)' : accent ? 'var(--teal)' : undefined }}>{text}<span className="unit">{unit}</span></div>
      <div className="sub">{quantity}</div>
    </div>
  );
}

function DisplayTab() {
  const { theme, setTheme } = useStore();
  const keys: [string, string][] = [
    ['Ctrl / ⌘ + K', 'Go to any page or input'], ['Ctrl / ⌘ + I', 'Show or hide the inputs panel'], ['Ctrl / ⌘ + S', 'Save the project now'],
    ['Ctrl / ⌘ + Z', 'Undo the last change'], ['Ctrl / ⌘ + Shift + Z', 'Redo'], ['↑ / ↓ in a number box', 'Step the value (Shift = ×10)'],
    ['Drag · scroll · right-drag', 'Orbit, zoom and pan the 3-D twin'], ['Click in the twin or a map', 'Pin a measurement point'],
  ];
  return (
    <div className="grid c2">
      <Card title="Theme">
        <Segmented value={theme} onChange={setTheme} options={[{ value: 'light', label: <><Sun size={13} />Light</> }, { value: 'dark', label: <><Moon size={13} />Dark</> }]} />
        <p className="small muted mt-8">Light is the standard Taki theme and is what reports are printed in. Dark is easier on the eyes for long sessions with the 3-D twin.</p>
      </Card>
      <Card title="AI narrative" sub="optional">
        <p className="small muted">The report page can ask an AI service to write a narrative from the computed results. Choose Claude, Gemini or ChatGPT and use your own key for it: every person using this copy of Taki enters theirs, and nobody sees or spends anyone else's.</p>
        <AiSetup />
      </Card>
      <Card title="Keyboard and mouse" className="surface" style={{ gridColumn: '1 / -1' }}>
        <div className="grid c2" style={{ gap: '0 28px' }}>
          {keys.map(([k, v]) => <div key={k} className="row between small" style={{ padding: '6px 0', borderBottom: '1px solid var(--line)' }}><span>{v}</span><span className="kbd">{k}</span></div>)}
        </div>
      </Card>
    </div>
  );
}

function DataTab() {
  const { project, config, replaceConfig, toast } = useStore();
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const exportJson = () => {
    if (!project || !config) return;
    const body = { taki: 'project', version: 4, name: project.name, description: project.description, exported_at: new Date().toISOString(), config, scenarios: project.scenarios.map((s) => ({ name: s.name, note: s.note, config: s.config })) };
    saveText(JSON.stringify(body, null, 2), `${project.name.replace(/[^\w-]+/g, '_') || 'taki_project'}.taki.json`, 'application/json');
  };
  const importFile = async (f: File) => {
    setError(null);
    try {
      if (f.size > 1_500_000) throw new Error('That file is too large to be a Taki project.');
      const raw = JSON.parse(await f.text());
      const candidate = raw?.config ?? raw;
      const { config: clean, migrated, notes } = await api.post<{ config: Config; migrated: boolean; notes: string[] }>('/normalise', { config: candidate });
      replaceConfig(clean);
      setNotes(notes ?? []);
      toast(migrated ? 'Imported and converted an older Taki scenario file.' : 'Imported. Undo (Ctrl+Z) brings the previous inputs back.');
    } catch (e: any) {
      setError(e instanceof SyntaxError ? 'That file is not valid JSON.' : (e?.message ?? 'Could not read that file.'));
    }
  };
  return (
    <div className="grid c2">
      <Card title="Export this project">
        <p className="small muted">A single JSON file with every input and the saved scenarios. Use it as a backup, to move work between accounts or servers, or to attach to a study record.</p>
        <Button className="mt-8" onClick={exportJson}><Download size={14} />Download project file</Button>
      </Card>
      <Card title="Import inputs into this project">
        <p className="small muted">Replaces the current inputs with those in a file. Accepts Taki project files and scenario files saved by the earlier Streamlit versions of Taki (they are converted automatically). The change can be undone.</p>
        <label className="btn mt-8" style={{ cursor: 'pointer' }}>
          <Upload size={14} />Choose a file…
          <input type="file" accept=".json,application/json" style={{ display: 'none' }} onChange={(e) => { const f = e.target.files?.[0]; if (f) void importFile(f); e.target.value = ''; }} />
        </label>
        <div className="mt-8"><ErrorNote error={error} />{notes.map((n) => <Note key={n} kind="info">{n}</Note>)}</div>
      </Card>
      <Card title="Reset" className="surface">
        <p className="small muted">Put every input back to the starting configuration. Saved scenarios are kept, and the change can be undone.</p>
        <Button variant="danger" className="mt-8" onClick={() => { const d = useStore.getState().library?.default_config; if (d) { replaceConfig(JSON.parse(JSON.stringify(d))); toast('Inputs reset to defaults.'); } }}>Reset inputs to defaults</Button>
      </Card>
    </div>
  );
}

function AboutTab() {
  const meta = useStore((s) => s.meta);
  const toast = useStore((s) => s.toast);
  const setInstallOpen = useStore((s) => s.setInstallOpen);
  const desktop = !!meta?.desktop;
  const openFolder = async () => {
    try { await api.post('/desktop/open-data-folder'); }
    catch (e: any) { toast(e?.message ?? 'Could not open the folder.', 'error'); }
  };
  return (
    <div className="grid c2">
      <Card title="Taki">
        <Kv k="Version" v={`${meta?.version ?? '—'}${desktop ? ' · desktop' : ''}`} />
        <Kv k="Engine" v="Python · NumPy" />
        <Kv k="Interface" v="React · three.js · Plotly" />
        {desktop ? <>
          <Kv k="Accounts" v="none: one person, on this computer" />
          <Kv k="Projects" v={<span className="mono" style={{ wordBreak: 'break-all' }}>{meta?.data_dir ?? 'a folder on this computer'}</span>} />
        </> : <>
          <Kv k="Accounts" v={meta?.allow_signup ? 'sign-up open' : 'sign-up closed'} />
          <Kv k="Database" v={meta?.database === 'postgresql' ? `PostgreSQL · ${meta.database_host}` : 'SQLite file on the computer running Taki'} />
          <Kv k="Email" v={meta?.email ? 'password-reset links are emailed' : 'not set up (reset links are printed by the server)'} />
        </>}
        <p className="small muted mt-12">Taki estimates power-frequency electric and magnetic fields around overhead lines, checks them against exposure standards, and evaluates shielding options. Every number shown in the interface comes from the Python engine{desktop ? ' running on this computer' : ' on the server'}; the {desktop ? 'window' : 'browser'} only draws.</p>
      </Card>
      {desktop ? (
        <Card title="Desktop version">
          <p className="small">This copy of Taki runs on this computer only. It has no sign-in, needs no internet, and stops when its last window is closed. Start it again from the Taki icon.</p>
          <div className="row wrap mt-12">
            <Button onClick={openFolder}><FolderOpen size={14} />Open the projects folder</Button>
            {meta?.desktop_download && <a className="btn" href="/api/desktop/package" download title="The installer, to put Taki on another computer"><Download size={14} />Installer for another computer</a>}
          </div>
          <p className="small muted mt-12">To back up or move your work: the projects page, <i>Export all</i>. To update Taki, run <i>Install Taki</i> from a newer download; the projects are kept.</p>
        </Card>
      ) : (
        <Card title="Taki as an app">
          <p className="small">Use Taki outside a browser tab: the desktop version runs on your own computer and works offline; or install this site from the browser to give it a window and an icon of its own.</p>
          <Button className="mt-12" onClick={() => setInstallOpen(true)}><MonitorDown size={14} />Install or download…</Button>
        </Card>
      )}
      <Card title="Limits of the model" className="surface" style={{ gridColumn: '1 / -1' }}>
        <ul className="small" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.65 }}>
          <li>Conductors are straight, parallel and infinitely long within each cross-section; towers, earth wires and nearby metallic objects are not modelled.</li>
          <li>Currents are balanced three-phase at the stated loading. Unbalance and harmonics are not included.</li>
          <li>The electric field is the unperturbed field: people, trees and buildings distort it locally.</li>
          <li>The physical shield model is a cross-section. It represents a shield that is long compared with its distance from the line; the length setting limits where the barrier acts along the span but end effects are not solved.</li>
          <li>Material properties are nominal. Steel permeability in particular varies with grade and with field level.</li>
          <li>Results support screening and design studies. A compliance decision needs measurement by a qualified person to IEEE Std 644 or IEC 61786.</li>
        </ul>
      </Card>
    </div>
  );
}
