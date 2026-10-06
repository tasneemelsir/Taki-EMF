// Project list: the landing page after sign-in.

import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Copy, Download, FolderOpen, Link2, MoreHorizontal, Moon, Pencil, Plus, Search, Shield, Sun, Trash2, Upload } from 'lucide-react';
import { ShareModal } from '@/components/ShareModal';
import { BrandMark, UserMenu } from '@/components/Shell';
import { Badge, Button, Confirm, Empty, ErrorNote, Field, MenuButton, Modal, Note, Pill, Spinner, TextInput, cx } from '@/components/ui';
import { api, saveText } from '@/lib/api';
import { ago, fmt } from '@/lib/format';
import { useStore } from '@/lib/store';
import type { Config, Project, ProjectMeta } from '@/lib/types';

interface Template { id: string; name: string; tag: string; description: string; config: Config; summary: ProjectMeta['summary'] }

export function PlainShell({ children, crumb }: { children: React.ReactNode; crumb?: string }) {
  const { theme, setTheme } = useStore();
  return (
    <div style={{ minHeight: '100vh', background: 'var(--surface)' }}>
      <header className="topbar" style={{ height: 'var(--topbar-h)', position: 'sticky', top: 0, zIndex: 20 }}>
        <Link to="/projects" className="row" style={{ textDecoration: 'none', gap: 10 }}>
          <span className="nav-brand" style={{ border: 0, padding: 0, height: 'auto' }}><span className="mark"><BrandMark /></span><span className="word">Taki</span></span>
        </Link>
        {crumb && <span className="muted small">/ {crumb}</span>}
        <div className="grow" />
        <Button variant="ghost" icon size="sm" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} title="Switch theme" aria-label="Switch theme">{theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}</Button>
        <UserMenu />
      </header>
      {children}
    </div>
  );
}

function slug(name: string) { return name.replace(/[^\w-]+/g, '_').replace(/^_+|_+$/g, '') || 'taki_project'; }

export default function ProjectsPage() {
  const nav = useNavigate();
  const { user, toast, closeProject } = useStore();
  const desktop = useStore((s) => !!s.meta?.desktop);
  const [projects, setProjects] = useState<ProjectMeta[] | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState('');
  const [creating, setCreating] = useState<Template | 'pick' | null>(null);
  const [renaming, setRenaming] = useState<ProjectMeta | null>(null);
  const [deleting, setDeleting] = useState<ProjectMeta | null>(null);
  const [sharing, setSharing] = useState<ProjectMeta | null>(null);
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState<{ done: number; total: number } | null>(null);

  const load = async () => {
    try {
      const r = await api.get<{ projects: ProjectMeta[] }>('/projects');
      setProjects(r.projects);
    } catch (e: any) { setError(e?.message ?? 'Could not load your projects.'); }
  };
  useEffect(() => {
    closeProject();
    void load();
    api.get<{ templates: Template[] }>('/templates').then((r) => setTemplates(r.templates)).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const shown = useMemo(() => (projects ?? []).filter((p) => (p.name + ' ' + p.description).toLowerCase().includes(q.trim().toLowerCase())), [projects, q]);

  type Saved = { name: string; note?: string; config: Config };
  const createOne = async (name: string, description: string, config: Config | null, scenarios: Saved[] = []) => {
    const { project } = await api.post<{ project: Project }>('/projects', { name, description, config });
    for (const s of scenarios.slice(0, 60)) {
      try { await api.post(`/projects/${project.id}/scenarios`, { name: s.name, note: s.note ?? '', config: s.config }); } catch { /* skip a bad scenario */ }
    }
    return project;
  };
  const create = async (name: string, description: string, config: Config | null, scenarios: Saved[] = []) => {
    setBusy(true); setError(null);
    try { const project = await createOne(name, description, config, scenarios); nav(`/p/${project.id}/dashboard`); }
    catch (e: any) { setError(e?.message ?? 'Could not create the project.'); setBusy(false); }
  };

  // "Export all" writes every project into one file; this reads such a file back in.
  const importAll = async (items: any[]) => {
    setBusy(true);
    let done = 0, skipped = 0, stopped: string | null = null;
    for (const it of items) {
      setImporting({ done: done + skipped, total: items.length });
      if (!it?.config || !Array.isArray(it.config.lines)) { skipped++; continue; }
      try { await createOne(String(it.name ?? 'Imported project').slice(0, 120) || 'Imported project', String(it.description ?? ''), it.config, Array.isArray(it.scenarios) ? it.scenarios : []); done++; }
      catch (e: any) { stopped = e?.message ?? 'Could not create a project.'; break; }
    }
    setBusy(false); setImporting(null);
    await load();
    if (stopped) setError(`Imported ${done} of ${items.length} projects, then stopped: ${stopped}`);
    else toast(`Imported ${done} project${done === 1 ? '' : 's'}${skipped ? `; ${skipped} could not be read` : ''}.`);
  };
  const exportAll = async () => {
    try {
      const all = await api.get<{ projects: unknown[] }>('/projects/export');
      saveText(JSON.stringify(all, null, 1), `taki-projects-${new Date().toISOString().slice(0, 10)}.taki.json`, 'application/json');
      toast(`Exported ${all.projects.length} project${all.projects.length === 1 ? '' : 's'} into one file.`);
    } catch (e: any) { toast(e?.message ?? 'Could not export.', 'error'); }
  };

  const importFile = async (f: File) => {
    setError(null);
    try {
      if (f.size > 60_000_000) throw new Error('That file is too large to be a Taki file.');
      const raw = JSON.parse(await f.text());
      if (raw?.taki === 'projects' && Array.isArray(raw.projects)) { await importAll(raw.projects); return; }
      if (f.size > 1_500_000) throw new Error('That file is too large to be a Taki project.');
      const cfg = raw?.config ?? raw;
      if (!cfg || typeof cfg !== 'object' || !Array.isArray(cfg.lines)) throw new Error('That file does not look like a Taki project or scenario.');
      const name = String(raw?.name ?? raw?.scenario_name ?? f.name.replace(/\.(taki\.)?json$/i, '')).slice(0, 120) || 'Imported project';
      await create(name, String(raw?.description ?? ''), cfg, Array.isArray(raw?.scenarios) ? raw.scenarios : []);
    } catch (e: any) {
      setError(e instanceof SyntaxError ? 'That file is not valid JSON.' : (e?.message ?? 'Could not read that file.'));
    }
  };

  const duplicate = async (p: ProjectMeta) => {
    try { await api.post(`/projects/${p.id}/duplicate`); toast(`Duplicated "${p.name}".`); void load(); }
    catch (e: any) { toast(e?.message ?? 'Could not duplicate.', 'error'); }
  };
  const exportProject = async (p: ProjectMeta) => {
    try {
      const { project } = await api.get<{ project: Project }>(`/projects/${p.id}`);
      saveText(JSON.stringify({ taki: 'project', version: 4, name: project.name, description: project.description, exported_at: new Date().toISOString(), config: project.config, scenarios: project.scenarios.map((s) => ({ name: s.name, note: s.note, config: s.config })) }, null, 2), `${slug(project.name)}.taki.json`, 'application/json');
    } catch (e: any) { toast(e?.message ?? 'Could not export.', 'error'); }
  };
  const remove = async (p: ProjectMeta) => {
    try { await api.del(`/projects/${p.id}`); setProjects((l) => (l ?? []).filter((x) => x.id !== p.id)); toast(`Deleted "${p.name}".`); }
    catch (e: any) { toast(e?.message ?? 'Could not delete.', 'error'); }
  };

  return (
    <PlainShell>
      <div className="page" style={{ maxWidth: 1240 }}>
        <div className="page-head">
          <div>
            <h1>{user?.is_guest || desktop ? 'Projects' : `Welcome back, ${(user?.name ?? '').split(' ')[0]}`}</h1>
            <p className="lede">Each project is one corridor study: its lines, site, shield, standards and saved scenarios. Everything is saved {desktop ? 'on this computer ' : ''}as you work.</p>
          </div>
          <div className="actions">
            {(projects?.length ?? 0) > 3 && (
              <div className="input-unit" style={{ width: 220 }}>
                <input className="input" placeholder="Search projects" value={q} onChange={(e) => setQ(e.target.value)} style={{ paddingLeft: 30, paddingRight: 9 }} />
                <span className="u" style={{ left: 9, right: 'auto' }}><Search size={14} /></span>
              </div>
            )}
            {(projects?.length ?? 0) > 0 && <Button onClick={exportAll} title="Every project with its scenarios in one file: a backup, and the way to move them to another copy of Taki"><Download size={14} />Export all</Button>}
            <label className="btn" style={{ cursor: 'pointer' }} title="Open a Taki project file, a file made by Export all, or a scenario file from an earlier version of Taki">
              <Upload size={14} />Import
              <input type="file" accept=".json,application/json" style={{ display: 'none' }} onChange={(e) => { const f = e.target.files?.[0]; if (f) void importFile(f); e.target.value = ''; }} />
            </label>
            <Button variant="primary" onClick={() => setCreating('pick')}><Plus size={14} />New project</Button>
          </div>
        </div>

        {user?.is_guest && (
          <Note kind="info" className="mb-16">
            You are in a guest session: projects are kept for this browser only. <Link to="/register">Create a free account</Link> to keep them and open them from anywhere. Nothing you have made is lost when you do.
          </Note>
        )}
        <ErrorNote error={error} />
        {importing && <Note kind="info" className="mb-16"><span className="row gap-8"><Spinner />Importing project {Math.min(importing.total, importing.done + 1)} of {importing.total}…</span></Note>}

        {projects === null ? <div className="empty"><Spinner /></div> : projects.length === 0 ? (
          <div className="card" style={{ background: 'var(--card)' }}>
            <Empty title="No projects yet" action={<Button variant="primary" onClick={() => setCreating('pick')}><Plus size={14} />Create your first project</Button>}>
              Start from a blank corridor or from one of the worked examples below.
            </Empty>
          </div>
        ) : (
          <div className="proj-grid">
            {shown.map((p) => <ProjectCard key={p.id} p={p} onOpen={() => nav(`/p/${p.id}/dashboard`)} onRename={() => setRenaming(p)} onDuplicate={() => duplicate(p)} onShare={desktop ? null : () => setSharing(p)} onExport={() => exportProject(p)} onDelete={() => setDeleting(p)} />)}
            <button className="proj-card proj-new" onClick={() => setCreating('pick')}><Plus size={20} /><span>New project</span></button>
            {shown.length === 0 && q && <div className="small muted">Nothing matches “{q}”.</div>}
          </div>
        )}

        {templates.length > 0 && (
          <>
            <div className="eyebrow mt-24" style={{ marginTop: 32 }}>Start from an example</div>
            <div className="proj-grid">
              {templates.map((t) => (
                <div key={t.id} className="proj-card" onClick={() => setCreating(t)} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') setCreating(t); }}>
                  <div className="row between"><Pill tone={t.tag === 'Shielding' ? 'teal' : 'blue'}>{t.tag}</Pill>{t.summary.overall && <Badge status={t.summary.overall} />}</div>
                  <h3 style={{ paddingRight: 0 }}>{t.name}</h3>
                  <div className="small muted" style={{ minHeight: 54 }}>{t.description}</div>
                  <Stats s={t.summary} />
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {creating && <NewProjectModal templates={templates} initial={creating === 'pick' ? null : creating} busy={busy} onClose={() => setCreating(null)}
                                    onCreate={(name, desc, t) => create(name, desc, t?.config ?? null)} />}
      {renaming && <RenameModal p={renaming} onClose={() => setRenaming(null)} onSaved={() => { setRenaming(null); void load(); }} />}
      {sharing && <ShareModal projectId={sharing.id} name={sharing.name} onClose={() => setSharing(null)} onChanged={() => void load()} />}
      {deleting && <Confirm title="Delete this project?" danger confirmLabel="Delete project" onClose={() => setDeleting(null)} onConfirm={() => remove(deleting)}>
        “{deleting.name}” and its {deleting.scenario_count ?? 0} saved scenario{deleting.scenario_count === 1 ? '' : 's'} will be removed. This cannot be undone. Export it first if you may need it again.
      </Confirm>}
    </PlainShell>
  );
}

function Stats({ s }: { s: ProjectMeta['summary'] }) {
  return (
    <div className="stats">
      <div>Peak B<b>{s.peak_b !== undefined ? <>{fmt(s.peak_b)}<small>µT</small></> : '—'}</b></div>
      <div>Peak E<b>{s.peak_e !== undefined ? <>{fmt(s.peak_e)}<small>kV/m</small></> : '—'}</b></div>
      <div>{s.lines === 1 ? 'Line' : 'Lines'}<b>{s.kv?.length ? <>{s.kv.map((k) => k.toFixed(0)).join('+')}<small>kV</small></> : (s.lines ?? '—')}</b></div>
    </div>
  );
}

function ProjectCard({ p, onOpen, onRename, onDuplicate, onShare, onExport, onDelete }: { p: ProjectMeta; onOpen: () => void; onRename: () => void; onDuplicate: () => void; onShare: (() => void) | null; onExport: () => void; onDelete: () => void }) {
  return (
    <div className="proj-card" onClick={onOpen} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' && e.target === e.currentTarget) onOpen(); }}>
      <div className="more" onClick={(e) => e.stopPropagation()}>
        <MenuButton button={(_o, toggle) => <Button variant="ghost" icon size="sm" onClick={toggle} aria-label="Project actions"><MoreHorizontal size={16} /></Button>}>
          {(close) => (<>
            <button onClick={() => { close(); onOpen(); }}><FolderOpen size={14} />Open</button>
            <button onClick={() => { close(); onRename(); }}><Pencil size={14} />Rename</button>
            <button onClick={() => { close(); onDuplicate(); }}><Copy size={14} />Duplicate</button>
            {onShare && <button onClick={() => { close(); onShare(); }}><Link2 size={14} />Share a copy…</button>}
            <button onClick={() => { close(); onExport(); }}><Download size={14} />Export file</button>
            <div className="sep" />
            <button style={{ color: 'var(--red)' }} onClick={() => { close(); onDelete(); }}><Trash2 size={14} />Delete</button>
          </>)}
        </MenuButton>
      </div>
      <h3 title={p.name}>{p.name}</h3>
      <div className="desc">{p.description || <span style={{ opacity: .7 }}>No description</span>}</div>
      <Stats s={p.summary} />
      <div className="row between small muted">
        <span className="row gap-4">
          {p.summary.overall && <Badge status={p.summary.overall} />}
          {p.summary.shield && <Pill tone="teal"><Shield size={10} />shield</Pill>}
          {p.scenario_count ? <Pill>{p.scenario_count} scenario{p.scenario_count === 1 ? '' : 's'}</Pill> : null}
          {p.shared && <Pill tone="blue"><Link2 size={10} />shared</Pill>}
        </span>
        <span>{ago(p.updated_at)}</span>
      </div>
    </div>
  );
}

function NewProjectModal({ templates, initial, busy, onClose, onCreate }: { templates: Template[]; initial: Template | null; busy: boolean; onClose: () => void; onCreate: (name: string, desc: string, t: Template | null) => void }) {
  const [tid, setTid] = useState(initial?.id ?? 'blank');
  const t = templates.find((x) => x.id === tid) ?? null;
  const [name, setName] = useState(initial && initial.id !== 'blank' ? initial.name : '');
  const [desc, setDesc] = useState('');
  const [touched, setTouched] = useState(!!initial && initial.id !== 'blank');
  const pick = (x: Template) => { setTid(x.id); if (!touched) setName(x.id === 'blank' ? '' : x.name); };
  const go = () => onCreate(name.trim() || (t && t.id !== 'blank' ? t.name : 'Untitled project'), desc.trim(), t);
  return (
    <Modal title="New project" wide onClose={onClose} footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={busy} onClick={go}>{busy ? 'Creating…' : 'Create project'}</Button></>}>
      <div className="fields-2">
        <Field label="Name"><TextInput value={name} onChange={(v) => { setName(v); setTouched(true); }} autoFocus maxLength={120} placeholder="e.g. Jalan Ampang 275 kV corridor" /></Field>
        <Field label="Description (optional)"><TextInput value={desc} onChange={setDesc} maxLength={300} placeholder="Client, location, purpose" /></Field>
      </div>
      <div className="eyebrow" style={{ marginTop: 18 }}>Start from</div>
      <div className="grid c2" style={{ gap: 8 }}>
        {templates.map((x) => (
          <button key={x.id} type="button" className={cx('tile', x.id === tid && 'on')} onClick={() => pick(x)} style={{ padding: '10px 12px' }}>
            <span className="row between"><b style={{ fontSize: 13 }}>{x.name}</b><Pill tone={x.tag === 'Shielding' ? 'teal' : 'blue'}>{x.tag}</Pill></span>
            <small style={{ marginTop: 4, fontSize: 11.5, lineHeight: 1.45 }}>{x.description}</small>
          </button>
        ))}
        {!templates.length && <div className="small muted">A blank corridor with one line and one building.</div>}
      </div>
    </Modal>
  );
}

function RenameModal({ p, onClose, onSaved }: { p: ProjectMeta; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(p.name);
  const [desc, setDesc] = useState(p.description);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    try { await api.put(`/projects/${p.id}`, { name: name.trim() || 'Untitled project', description: desc.trim() }); onSaved(); }
    catch (e: any) { setError(e?.message ?? 'Could not save.'); }
  };
  return (
    <Modal title="Rename project" onClose={onClose} footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" onClick={save}>Save</Button></>}>
      <ErrorNote error={error} />
      <Field label="Name"><TextInput value={name} onChange={setName} autoFocus maxLength={120} /></Field>
      <Field label="Description"><TextInput value={desc} onChange={setDesc} maxLength={300} /></Field>
    </Modal>
  );
}
