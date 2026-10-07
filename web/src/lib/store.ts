// Application state (zustand): the signed-in user, the open project and its
// configuration, the latest solution, and a little UI state.
//
// Flow: any change to the configuration (1) is pushed on the undo stack,
// (2) triggers a debounced solve, and (3) triggers a debounced autosave.

import { create } from 'zustand';
import { api, ApiError } from './api';
import { holdDesktopOpen } from './desktop';
import type { Config, Library, Meta, Pin, Project, Scenario, Solution, User } from './types';

type SaveState = 'saved' | 'dirty' | 'saving' | 'error';
export type InspectorTab = 'lines' | 'site' | 'shield' | 'standards';
export interface Toast { id: number; text: string; kind: 'info' | 'error' }

interface State {
  booted: boolean;
  meta: Meta | null;
  user: User | null;
  /** The last person here signed out or removed their account, rather than losing the session. */
  left: boolean;
  library: Library | null;

  project: Project | null;
  config: Config | null;
  physKey: string;
  past: Config[];
  future: Config[];
  saveState: SaveState;

  sol: Solution | null;
  solving: boolean;
  solveError: string | null;

  theme: 'light' | 'dark';
  inspectorOpen: boolean;
  inspectorTab: InspectorTab;
  navCollapsed: boolean;
  toasts: Toast[];
  aiNarrative: string;
  twinShot: string | null;
  installOpen: boolean;

  boot: () => Promise<void>;
  setUser: (u: User | null) => void;
  leave: () => void;
  loadLibrary: () => Promise<void>;
  openProject: (id: string) => Promise<void>;
  closeProject: () => void;
  setConfig: (fn: (c: Config) => Config | void, opts?: { history?: boolean; label?: string }) => void;
  replaceConfig: (c: Config) => void;
  undo: () => void;
  redo: () => void;
  renameProject: (name: string, description?: string) => void;
  saveNow: () => Promise<void>;
  addScenario: (name: string, note?: string) => Promise<Scenario | null>;
  deleteScenario: (id: string) => Promise<void>;
  setPins: (pins: Pin[]) => void;
  setTheme: (t: 'light' | 'dark') => void;
  setInspector: (open: boolean, tab?: InspectorTab) => void;
  toggleNav: () => void;
  toast: (text: string, kind?: 'info' | 'error') => void;
  dismissToast: (id: number) => void;
  setAiNarrative: (t: string) => void;
  setTwinShot: (s: string | null) => void;
  setInstallOpen: (open: boolean) => void;
}

const PHYS_KEYS: (keyof Config)[] = ['corridor', 'lines', 'buildings', 'shield', 'standards', 'numerics'];
export function physKeyOf(c: Config | null): string {
  if (!c) return '';
  const o: Record<string, unknown> = {};
  for (const k of PHYS_KEYS) o[k] = c[k];
  return JSON.stringify(o);
}

function clone<T>(v: T): T { return JSON.parse(JSON.stringify(v)); }

let solveTimer: number | undefined;
let saveTimer: number | undefined;
let solveAbort: AbortController | null = null;
let toastId = 1;
let libraryLoading: Promise<void> | null = null;
const MAX_HISTORY = 60;
/** What is left of the open work once nobody is signed in. */
const NOBODY = { project: null, config: null, sol: null, library: null, past: [] as Config[], future: [] as Config[] };

function initialTheme(): 'light' | 'dark' {
  try {
    const t = localStorage.getItem('taki.theme');
    if (t === 'dark' || t === 'light') return t;
  } catch { /* storage unavailable */ }
  return 'light';
}

export const useStore = create<State>((set, get) => {
  const scheduleSolve = (delay = 110) => {
    window.clearTimeout(solveTimer);
    solveTimer = window.setTimeout(runSolve, delay);
  };

  const runSolve = async () => {
    const cfg = get().config;
    if (!cfg) return;
    solveAbort?.abort();
    const ctl = new AbortController();
    solveAbort = ctl;
    set({ solving: true });
    try {
      const sol = await api.post<Solution>('/solve', { config: cfg }, ctl.signal);
      if (ctl.signal.aborted) return;
      set({ sol, solving: false, solveError: null });
    } catch (e: any) {
      if (e?.name === 'AbortError') return;
      set({ solving: false, solveError: e instanceof ApiError ? e.message : 'The calculation failed.' });
    }
  };

  const scheduleSave = (delay = 1100) => {
    window.clearTimeout(saveTimer);
    set({ saveState: 'dirty' });
    saveTimer = window.setTimeout(() => { void get().saveNow(); }, delay);
  };

  return {
    booted: false, meta: null, user: null, left: false, library: null,
    project: null, config: null, physKey: '', past: [], future: [], saveState: 'saved',
    sol: null, solving: false, solveError: null,
    theme: initialTheme(), inspectorOpen: true, inspectorTab: 'lines', navCollapsed: false, toasts: [],
    aiNarrative: '', twinShot: null, installOpen: false,

    boot: async () => {
      document.documentElement.dataset.theme = get().theme;
      try {
        const meta = await api.get<Meta>('/meta');
        set({ meta, user: meta.user, booted: true });
        if (meta.desktop && meta.user) holdDesktopOpen();
        if (meta.user) await get().loadLibrary();
      } catch {
        set({ booted: true });
      }
    },

    setUser: (u) => {
      if (u) set({ user: u, left: false });
      else set({ user: null, ...NOBODY });
    },

    // Signing out, or removing the account, is a choice; a session that ran out is not. After a
    // session ran out the sign-in page sends the same person back to the page they were on. After
    // a choice it must not: whoever comes in next, often someone else, starts at their own projects.
    leave: () => {
      window.clearTimeout(saveTimer);
      set({ user: null, left: true, ...NOBODY });
    },

    loadLibrary: () => {
      if (get().library) return Promise.resolve();
      // Two parts of the app ask for the library as a page opens; they share one request.
      libraryLoading ??= api.get<Library>('/library').then((library) => { set({ library }); })
        .finally(() => { libraryLoading = null; });
      return libraryLoading;
    },

    openProject: async (id) => {
      if (get().project?.id === id && get().config) return;
      window.clearTimeout(saveTimer);
      if (get().saveState === 'dirty') await get().saveNow();
      const { project } = await api.get<{ project: Project }>(`/projects/${id}`);
      set({ project, config: project.config, physKey: physKeyOf(project.config), past: [], future: [],
            saveState: 'saved', sol: null, aiNarrative: '', twinShot: null });
      try { localStorage.setItem('taki.lastProject', id); } catch { /* ignore */ }
      scheduleSolve(0);
    },

    closeProject: () => {
      window.clearTimeout(saveTimer);
      if (get().saveState === 'dirty') void get().saveNow();
      set({ project: null, config: null, sol: null, past: [], future: [] });
    },

    setConfig: (fn, opts) => {
      const cur = get().config;
      if (!cur) return;
      const draft = clone(cur);
      const res = fn(draft);
      const next = (res ?? draft) as Config;
      const key = physKeyOf(next);
      const samePhys = key === get().physKey;
      const history = opts?.history !== false;
      set((s) => ({
        config: next, physKey: key,
        past: history ? [...s.past.slice(-MAX_HISTORY + 1), cur] : s.past,
        future: history ? [] : s.future,
      }));
      if (!samePhys) scheduleSolve();
      scheduleSave();
    },

    replaceConfig: (c) => {
      const cur = get().config;
      set((s) => ({ config: c, physKey: physKeyOf(c), past: cur ? [...s.past.slice(-MAX_HISTORY + 1), cur] : s.past, future: [] }));
      scheduleSolve(0);
      scheduleSave();
    },

    undo: () => {
      const { past, config, future } = get();
      if (!past.length || !config) return;
      const prev = past[past.length - 1];
      set({ config: prev, physKey: physKeyOf(prev), past: past.slice(0, -1), future: [config, ...future].slice(0, MAX_HISTORY) });
      scheduleSolve(0); scheduleSave();
    },

    redo: () => {
      const { past, config, future } = get();
      if (!future.length || !config) return;
      const next = future[0];
      set({ config: next, physKey: physKeyOf(next), past: [...past, config], future: future.slice(1) });
      scheduleSolve(0); scheduleSave();
    },

    renameProject: (name, description) => {
      const p = get().project;
      if (!p) return;
      set({ project: { ...p, name, description: description ?? p.description } });
      scheduleSave(600);
    },

    saveNow: async () => {
      const { project, config } = get();
      if (!project || !config) return;
      window.clearTimeout(saveTimer);
      set({ saveState: 'saving' });
      try {
        await api.put(`/projects/${project.id}`, { name: project.name, description: project.description, config });
        if (get().saveState === 'saving') set({ saveState: 'saved' });
      } catch {
        set({ saveState: 'error' });
      }
    },

    addScenario: async (name, note) => {
      const { project, config } = get();
      if (!project || !config) return null;
      try {
        const { scenario } = await api.post<{ scenario: Scenario }>(`/projects/${project.id}/scenarios`, { name, note: note ?? '', config });
        set({ project: { ...get().project!, scenarios: [...get().project!.scenarios, scenario] } });
        get().toast(`Saved scenario "${scenario.name}".`);
        return scenario;
      } catch (e: any) {
        get().toast(e?.message ?? 'Could not save the scenario.', 'error');
        return null;
      }
    },

    deleteScenario: async (id) => {
      const project = get().project;
      if (!project) return;
      try {
        await api.del(`/projects/${project.id}/scenarios/${id}`);
        set({ project: { ...get().project!, scenarios: get().project!.scenarios.filter((s) => s.id !== id) } });
      } catch (e: any) {
        get().toast(e?.message ?? 'Could not delete the scenario.', 'error');
      }
    },

    setPins: (pins) => get().setConfig((c) => { c.points = pins.slice(0, 60); }, { history: false }),

    setTheme: (t) => {
      document.documentElement.dataset.theme = t;
      try { localStorage.setItem('taki.theme', t); } catch { /* ignore */ }
      set({ theme: t });
    },

    setInspector: (open, tab) => set((s) => ({ inspectorOpen: open, inspectorTab: tab ?? s.inspectorTab })),
    toggleNav: () => set((s) => ({ navCollapsed: !s.navCollapsed })),

    toast: (text, kind = 'info') => {
      const id = toastId++;
      set((s) => ({ toasts: [...s.toasts.slice(-3), { id, text, kind }] }));
      window.setTimeout(() => get().dismissToast(id), kind === 'error' ? 6500 : 3200);
    },
    dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
    setAiNarrative: (t) => set({ aiNarrative: t }),
    setTwinShot: (s) => set({ twinShot: s }),
    setInstallOpen: (open) => set({ installOpen: open }),
  };
});

// Flush a pending save when the tab is hidden or closed.
if (typeof window !== 'undefined') {
  window.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && useStore.getState().saveState === 'dirty') {
      void useStore.getState().saveNow();
    }
  });
}
