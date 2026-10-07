// Application frame: grouped navigation on the left, the project bar on top
// (name, save state, live compliance), the page in the middle and the
// inspector on the right.

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { NavLink, Outlet, useNavigate, useParams } from 'react-router-dom';
import {
  BadgeCheck, BarChart3, BookOpen, Box, ChevronsLeft, ChevronsRight, Crosshair, FileText, FolderOpen, Grid3x3,
  LayoutDashboard, Layers, LineChart, Link2, LogOut, MonitorDown, Moon, Mountain, PanelRightClose, PanelRightOpen, Redo2, Save, Search,
  Settings, Shield, Sun, Undo2, User as UserIcon, Waves,
} from 'lucide-react';
import { api } from '@/lib/api';
import { change, fmt, STATUS_LABEL } from '@/lib/format';
import { useHotkey } from '@/lib/hooks';
import { useStore } from '@/lib/store';
import { Inspector } from './Inspector';
import { ShareModal } from './ShareModal';
import { Badge, Button, MenuButton, Modal, Spinner, TextInput, Field, cx } from './ui';

export const NAV: { group: string; items: { to: string; label: string; icon: React.ReactNode; keys?: string }[] }[] = [
  { group: 'Overview', items: [{ to: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={16} /> }] },
  { group: 'Simulate', items: [
    { to: 'profile', label: 'Lateral profile', icon: <LineChart size={16} /> },
    { to: 'map', label: 'Field map', icon: <Grid3x3 size={16} /> },
    { to: 'field-lines', label: 'Field lines', icon: <Waves size={16} /> },
    { to: 'earth', label: 'Earth sensitivity', icon: <Mountain size={16} /> },
    { to: 'measure', label: 'Measure points', icon: <Crosshair size={16} /> },
  ] },
  { group: 'Shielding', items: [
    { to: 'shield', label: 'Shield design', icon: <Shield size={16} /> },
    { to: 'compare', label: 'Compare options', icon: <BarChart3 size={16} /> },
  ] },
  { group: 'Site', items: [{ to: 'twin', label: 'Digital twin', icon: <Box size={16} /> }] },
  { group: 'Analyse', items: [
    { to: 'scenarios', label: 'Scenarios', icon: <Layers size={16} /> },
    { to: 'validation', label: 'Validation', icon: <BadgeCheck size={16} /> },
  ] },
  { group: 'Deliver', items: [
    { to: 'report', label: 'Report', icon: <FileText size={16} /> },
    { to: 'library', label: 'Research library', icon: <BookOpen size={16} /> },
  ] },
  { group: 'System', items: [{ to: 'settings', label: 'Settings', icon: <Settings size={16} /> }] },
];

export function BrandMark({ size = 16 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true"><path d="M13.6 2 5 13.6h5.4L8.8 22 19 9.8h-6z" fill="#fff" /></svg>;
}

export function Shell() {
  const { pid } = useParams();
  const nav = useNavigate();
  const { project, config, openProject, navCollapsed, toggleNav, inspectorOpen, setInspector, undo, redo, saveNow, toast } = useStore();
  const [error, setError] = useState<string | null>(null);
  const [palette, setPalette] = useState(false);
  const [saveScenario, setSaveScenario] = useState(false);
  const [share, setShare] = useState(false);

  useEffect(() => {
    if (!pid) return;
    setError(null);
    openProject(pid).catch((e) => setError(e?.message ?? 'Could not open that project.'));
  }, [pid, openProject]);

  useHotkey('mod+z', (e) => { e.preventDefault(); undo(); }, []);
  useHotkey('mod+shift+z', (e) => { e.preventDefault(); redo(); }, []);
  useHotkey('mod+y', (e) => { e.preventDefault(); redo(); }, []);
  useHotkey('mod+s', (e) => { e.preventDefault(); void saveNow().then(() => toast('Project saved.')); }, []);
  useHotkey('mod+k', (e) => { e.preventDefault(); setPalette(true); }, []);
  useHotkey('mod+i', (e) => { e.preventDefault(); setInspector(!useStore.getState().inspectorOpen); }, []);

  if (error) return (
    <div className="empty" style={{ paddingTop: 120 }}>
      <h3>That project could not be opened</h3><div className="small">{error}</div>
      <div className="mt-12"><Button variant="primary" onClick={() => nav('/projects')}>Back to projects</Button></div>
    </div>
  );
  const ready = !!project && !!config && project.id === pid;

  return (
    <div className={cx('shell', navCollapsed && 'nav-collapsed')}>
      <nav className="nav" aria-label="Sections">
        <div className="nav-brand">
          <span className="mark"><BrandMark /></span><span className="word">Taki</span>
        </div>
        <div className="nav-scroll">
          {NAV.map((g) => (
            <div className="nav-group" key={g.group}>
              <div className="eyebrow">{g.group}</div>
              {g.items.map((it) => (
                <NavLink key={it.to} to={`/p/${pid}/${it.to}`} className={({ isActive }) => cx('nav-item', isActive && 'active')} title={it.label}>
                  {it.icon}<span>{it.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </div>
        <div className="nav-foot">
          <NavLink to="/projects" className="nav-item" title="All projects"><FolderOpen size={16} /><span>All projects</span></NavLink>
          <button className="nav-item" onClick={toggleNav} title={navCollapsed ? 'Expand the menu' : 'Collapse the menu'}>
            {navCollapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}<span>Collapse</span>
          </button>
        </div>
      </nav>

      <div className="main">
        <TopBar onPalette={() => setPalette(true)} onSaveScenario={() => setSaveScenario(true)} onShare={() => setShare(true)} />
        <div className="workspace">
          <main className="content" id="content">
            {ready ? <Outlet /> : <div className="empty" style={{ paddingTop: 120 }}><Spinner /></div>}
          </main>
          {ready && inspectorOpen && <Inspector />}
        </div>
      </div>
      {palette && <CommandPalette onClose={() => setPalette(false)} />}
      {saveScenario && <SaveScenarioModal onClose={() => setSaveScenario(false)} />}
      {share && project && <ShareModal projectId={project.id} name={project.name} onClose={() => setShare(false)} />}
    </div>
  );
}

/**
 * The read-outs in the top bar must never be cut off, whatever the project is called and however wide the
 * window is. This measures them and, when they do not fit, lets the least essential give way first:
 * 1 hides the earth model, 2 the margin, 3 the positions of the peaks (they stay in the tooltips),
 * 4 the shield figure, 5 the electric peak, 6 the magnetic peak, 7 the compliance badge. Everything is on
 * the dashboard as well, and nothing is ever shown half.
 */
const FIT_LEVELS = 7;
function useFit(signature: string) {
  const ref = useRef<HTMLDivElement>(null);
  const [level, setLevel] = useState(0);
  useLayoutEffect(() => { setLevel(0); }, [signature]);            // new content: start from everything shown
  useLayoutEffect(() => {
    const el = ref.current;
    if (el && level < FIT_LEVELS && el.scrollWidth > el.clientWidth + 1) setLevel(level + 1);
  });
  useEffect(() => {
    const bar = ref.current?.parentElement;
    if (!bar || typeof ResizeObserver === 'undefined') return;
    let w = bar.clientWidth;
    const ro = new ResizeObserver(() => { if (Math.abs(bar.clientWidth - w) > 1) { w = bar.clientWidth; setLevel(0); } });
    ro.observe(bar);
    return () => ro.disconnect();
  }, []);
  return [ref, level] as const;
}

function TopBar({ onPalette, onSaveScenario, onShare }: { onPalette: () => void; onSaveScenario: () => void; onShare: () => void }) {
  const { project, sol, solving, saveState, renameProject, past, future, undo, redo, theme, setTheme, inspectorOpen, setInspector, solveError } = useStore();
  const desktop = useStore((s) => !!s.meta?.desktop);
  const [name, setName] = useState(project?.name ?? '');
  useEffect(() => setName(project?.name ?? ''), [project?.id, project?.name]);
  const g = sol?.governing;
  const head = sol?.shield.on ? sol.shield.headline : null;
  const hm = sol?.corridor.meas_height ?? 1;
  const at = (x: number) => (Math.abs(x) < 0.05 ? 'under the centreline' : `${Math.abs(x).toFixed(1)} m ${x < 0 ? 'left' : 'right'} of the centreline`);
  const saveLabel = saveState === 'saved' ? 'Saved' : saveState === 'saving' ? 'Saving…' : saveState === 'dirty' ? 'Unsaved changes' : 'Not saved - retrying on next change';
  const [fitRef, fit] = useFit([name, saveLabel, sol?.hash, sol?.overall, head?.b_red_pct, head?.e_red_pct, solveError, solving].join('|'));
  const gone = (rank: number) => (fit >= rank ? { display: 'none' } : undefined);     // see useFit
  return (
    <header className="topbar">
      <input className="project-name" value={name} aria-label="Project name" maxLength={120}
             style={{ width: `${Math.max(8, Math.min(34, name.length + 2))}ch` }}
             onChange={(e) => setName(e.target.value)}
             onBlur={() => { const n = name.trim() || 'Untitled project'; setName(n); if (n !== project?.name) renameProject(n); }}
             onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }} />
      <span className={cx('save-state', saveState === 'dirty' && 'dirty', saveState === 'error' && 'error')} title={saveLabel}><span className="dot" />{saveLabel}</span>
      <div className="row gap-4">
        <Button variant="ghost" icon size="sm" onClick={undo} disabled={!past.length} title="Undo (Ctrl+Z)" aria-label="Undo"><Undo2 size={15} /></Button>
        <Button variant="ghost" icon size="sm" onClick={redo} disabled={!future.length} title="Redo (Ctrl+Shift+Z)" aria-label="Redo"><Redo2 size={15} /></Button>
      </div>

      <div className="statusline" ref={fitRef}>
        {sol ? <>
          <div className="item" style={gone(7)}><span className="k">Compliance</span><Badge status={sol.overall}>{STATUS_LABEL[sol.overall]}</Badge></div>
          <div className="item" style={gone(6)} title={`The highest magnetic field on the ground-level profile: at mid-span, ${hm} m above ground, ${at(sol.peak_b_x)}. Without any shield. This is the value checked against the limits.`}>
            <span className="k">Peak B · at {hm} m</span><span className="v">{fmt(sol.peak_b)} µT<small style={gone(3)}>x = {sol.peak_b_x.toFixed(0)} m</small></span></div>
          <div className="item" style={gone(5)} title={`The highest electric field on the ground-level profile: at mid-span, ${hm} m above ground, ${at(sol.peak_e_x)}. Without any shield. This is the value checked against the limits.`}>
            <span className="k">Peak E · at {hm} m</span><span className="v">{fmt(sol.peak_e)} kV/m<small style={gone(3)}>x = {sol.peak_e_x.toFixed(0)} m</small></span></div>
          {g && <div className="item" style={gone(2)} title={`Room left under the tightest selected limit: ${g.quantity} against ${g.standard}`}><span className="k">Margin</span><span className="v">{g.headroom.toFixed(0)}%</span></div>}
          <div className="item" style={gone(1)} title={sol.corridor.ground_note}><span className="k">Earth</span><span className="v" style={{ fontFamily: 'var(--font-ui)', fontSize: 12 }}>{sol.corridor.ground_short}</span></div>
          {head && (
            <div className="item" style={gone(4)} title={`${head.basis === 'inside' ? `Change in the average field inside ${head.where}` : `Change in the field at ${head.where}`} with the shield in place: B ${fmt(head.b0)} → ${fmt(head.bS)} µT, E ${fmt(head.e0)} → ${fmt(head.eS)} kV/m.${head.covered ? '' : ' The shield does not reach this building along the line.'} The compliance result never uses the shield.`}>
              <span className="k">Shield · {head.basis === 'inside' ? 'inside' : 'behind it'}</span>
              <span className="v" style={{ color: 'var(--teal)' }}>B {change(head.b_red_pct)} · E {change(head.e_red_pct)}</span>
            </div>
          )}
        </> : solveError ? <span className="small" style={{ color: 'var(--red)' }}>{solveError}</span> : null}
        {solving && <Spinner />}
      </div>

      <div className="grow" />
      <Button size="sm" onClick={onSaveScenario} title="Save the current inputs as a named scenario"><Save size={13} />Save scenario</Button>
      {!desktop && <Button size="sm" onClick={onShare} title="Send someone their own copy of this project"><Link2 size={13} />Share</Button>}
      <Button variant="ghost" icon size="sm" onClick={onPalette} title="Go to… (Ctrl+K)" aria-label="Search"><Search size={15} /></Button>
      <Button variant="ghost" icon size="sm" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} title="Switch theme" aria-label="Switch theme">{theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}</Button>
      <Button variant="ghost" icon size="sm" onClick={() => setInspector(!inspectorOpen)} title="Show or hide the inputs (Ctrl+I)" aria-label="Toggle inputs">
        {inspectorOpen ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
      </Button>
      <UserMenu />
    </header>
  );
}

export function UserMenu() {
  const user = useStore((s) => s.user);
  const desktop = useStore((s) => !!s.meta?.desktop);
  const signup = useStore((s) => !!s.meta?.allow_signup);
  const setInstallOpen = useStore((s) => s.setInstallOpen);
  const nav = useNavigate();
  const [ending, setEnding] = useState(false);
  if (!user) return null;
  const signOut = async () => {
    await useStore.getState().saveNow();
    try { await api.post('/auth/logout'); } catch { /* ignore */ }
    useStore.getState().leave();
    nav('/login', { replace: true });
  };
  const initials = (user.name || 'G').split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase();
  // The desktop version has one person and no sign-in: nothing to sign out of, nothing to install.
  if (desktop) return (
    <MenuButton button={(_o, toggle) => (
      <button onClick={toggle} aria-label="You" title={user.name}
              style={{ width: 30, height: 30, borderRadius: '50%', border: '1px solid var(--line-strong)', background: 'var(--blue-bg)', color: 'var(--blue)', fontWeight: 700, fontSize: 11, cursor: 'pointer' }}>
        {initials}
      </button>
    )}>{(close) => (<>
      <div className="head"><b>{user.name}</b>Desktop version, on this computer</div>
      <div className="sep" />
      <button onClick={() => { close(); nav('/account'); }}><Settings size={14} />Your name and data</button>
      <button onClick={() => { close(); nav('/projects'); }}><FolderOpen size={14} />All projects</button>
    </>)}</MenuButton>
  );
  return (<>
    <MenuButton button={(_o, toggle) => (
      <button onClick={toggle} aria-label="Account" title={user.is_guest ? 'Guest session' : user.name}
              style={{ width: 30, height: 30, borderRadius: '50%', border: '1px solid var(--line-strong)', background: user.is_guest ? 'var(--surface-2)' : 'var(--blue-bg)', color: 'var(--blue)', fontWeight: 700, fontSize: 11, cursor: 'pointer' }}>
        {user.is_guest ? <UserIcon size={14} /> : initials}
      </button>
    )}>{(close) => (<>
      <div className="head"><b>{user.is_guest ? 'Guest session' : user.name}</b>{user.is_guest ? 'Projects are kept for this browser.' : user.email}</div>
      <div className="sep" />
      {user.is_guest && <button onClick={() => { close(); nav('/register'); }}><UserIcon size={14} />Create an account</button>}
      <button onClick={() => { close(); nav('/account'); }}><Settings size={14} />Account</button>
      <button onClick={() => { close(); nav('/projects'); }}><FolderOpen size={14} />All projects</button>
      <button onClick={() => { close(); setInstallOpen(true); }}><MonitorDown size={14} />Taki as an app…</button>
      <div className="sep" />
      {/* A guest has nothing to sign back in with, so leaving is asked about first. */}
      <button onClick={() => { close(); if (user.is_guest) setEnding(true); else void signOut(); }}><LogOut size={14} />Sign out</button>
    </>)}</MenuButton>
    {ending && (
      <Modal title="End this guest session?" onClose={() => setEnding(false)} footer={<>
        <Button onClick={() => setEnding(false)}>Stay</Button>
        {signup && <Button onClick={() => { setEnding(false); nav('/register'); }}>Create an account</Button>}
        <Button variant="danger" onClick={() => { setEnding(false); void signOut(); }}>End the session</Button>
      </>}>
        <div className="small">
          A guest session cannot be opened again once it has ended, so the projects made in it are lost.
          To keep them, {signup ? 'create an account (they move into it), or ' : ''}export them to a file from the projects page first.
        </div>
      </Modal>
    )}
  </>);
}

function SaveScenarioModal({ onClose }: { onClose: () => void }) {
  const project = useStore((s) => s.project);
  const addScenario = useStore((s) => s.addScenario);
  const [name, setName] = useState(`Scenario ${(project?.scenarios.length ?? 0) + 1}`);
  const [note, setNote] = useState('');
  const save = async () => { await addScenario(name.trim() || 'Scenario', note.trim()); onClose(); };
  return (
    <Modal title="Save scenario" onClose={onClose} footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" onClick={save}>Save scenario</Button></>}>
      <p className="small muted">A scenario is a snapshot of every input. Compare scenarios side by side under Analyse → Scenarios, or load one back at any time.</p>
      <Field label="Name"><TextInput value={name} onChange={setName} autoFocus maxLength={80} /></Field>
      <Field label="Note (optional)"><TextInput value={note} onChange={setNote} maxLength={200} placeholder="What is different about this one?" /></Field>
    </Modal>
  );
}

function CommandPalette({ onClose }: { onClose: () => void }) {
  const { pid } = useParams();
  const nav = useNavigate();
  const { setInspector, setTheme, theme } = useStore();
  const [q, setQ] = useState('');
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const all = useMemo(() => {
    const items: { label: string; group: string; run: () => void }[] = [];
    for (const g of NAV) for (const it of g.items) items.push({ label: it.label, group: g.group, run: () => nav(`/p/${pid}/${it.to}`) });
    for (const [tab, label] of [['lines', 'Edit lines'], ['site', 'Edit site and buildings'], ['shield', 'Edit shield'], ['standards', 'Choose standards']] as const)
      items.push({ label, group: 'Inputs', run: () => setInspector(true, tab) });
    items.push({ label: 'All projects', group: 'Go', run: () => nav('/projects') });
    items.push({ label: 'Account', group: 'Go', run: () => nav('/account') });
    items.push({ label: 'Privacy and your data', group: 'Go', run: () => nav('/privacy') });
    if (!useStore.getState().meta?.desktop) items.push({ label: 'Taki as an app: install or download', group: 'Go', run: () => useStore.getState().setInstallOpen(true) });
    items.push({ label: theme === 'dark' ? 'Use the light theme' : 'Use the dark theme', group: 'Display', run: () => setTheme(theme === 'dark' ? 'light' : 'dark') });
    return items;
  }, [pid, nav, setInspector, setTheme, theme]);
  const list = all.filter((i) => i.label.toLowerCase().includes(q.trim().toLowerCase()));
  useEffect(() => { input.current?.focus(); }, []);
  useEffect(() => setSel(0), [q]);
  const go = (i: number) => { const it = list[i]; if (it) { it.run(); onClose(); } };
  return (
    <div className="scrim" style={{ placeItems: 'start center' }} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="palette" role="dialog" aria-label="Go to">
        <input ref={input} value={q} placeholder="Go to a page or an input…" onChange={(e) => setQ(e.target.value)}
               onKeyDown={(e) => {
                 if (e.key === 'Escape') onClose();
                 if (e.key === 'ArrowDown') { e.preventDefault(); setSel((s) => Math.min(list.length - 1, s + 1)); }
                 if (e.key === 'ArrowUp') { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
                 if (e.key === 'Enter') go(sel);
               }} />
        <div className="list">
          {list.map((it, i) => <div key={it.group + it.label} className={cx('opt', i === sel && 'sel')} onMouseEnter={() => setSel(i)} onClick={() => go(i)}>{it.label}<span className="g">{it.group}</span></div>)}
          {!list.length && <div className="opt muted">Nothing matches.</div>}
        </div>
      </div>
    </div>
  );
}
