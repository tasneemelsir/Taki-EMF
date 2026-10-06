import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from './api';
import { useStore } from './store';

// Results of the heavier endpoints, keyed by endpoint + request + configuration.
const cache = new Map<string, unknown>();
const MAX = 40;

function remember(key: string, value: unknown) {
  cache.delete(key);
  cache.set(key, value);
  while (cache.size > MAX) cache.delete(cache.keys().next().value as string);
}

export interface Remote<T> { data: T | null; loading: boolean; error: string | null; reload: () => void }

/**
 * Fetch data that depends on the current configuration. Refetches (debounced)
 * when the configuration or `extra` changes, keeps showing the previous result
 * while the new one loads, and drops responses that arrive out of order.
 */
export function useRemote<T>(path: string | null, extra: Record<string, unknown> = {}, opts: { delay?: number; withPoints?: boolean; enabled?: boolean } = {}): Remote<T> {
  const physKey = useStore((s) => s.physKey);
  const pointsKey = useStore((s) => (opts.withPoints ? JSON.stringify(s.config?.points ?? []) : ''));
  const extraKey = JSON.stringify(extra);
  const enabled = opts.enabled !== false && !!path;
  const key = `${path}|${extraKey}|${pointsKey}|${physKey}`;
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: string | null }>(() => ({
    data: (cache.get(key) as T) ?? null, loading: false, error: null,
  }));
  const [tick, setTick] = useState(0);
  const seq = useRef(0);

  useEffect(() => {
    if (!enabled || !physKey) return;
    const hit = cache.get(key) as T | undefined;
    if (hit !== undefined && tick === 0) {
      setState({ data: hit, loading: false, error: null });
      return;
    }
    const my = ++seq.current;
    const ctl = new AbortController();
    setState((s) => ({ ...s, loading: true }));
    const timer = window.setTimeout(async () => {
      try {
        const config = useStore.getState().config;
        const data = await api.post<T>(path!, { config, ...extra }, ctl.signal);
        if (my !== seq.current) return;
        remember(key, data);
        setState({ data, loading: false, error: null });
      } catch (e: any) {
        if (e?.name === 'AbortError' || my !== seq.current) return;
        setState((s) => ({ ...s, loading: false, error: e instanceof ApiError ? e.message : 'Request failed.' }));
      }
    }, opts.delay ?? 220);
    return () => { window.clearTimeout(timer); ctl.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled, tick]);

  return { ...state, reload: () => { cache.delete(key); setTick((t) => t + 1); } };
}

/** Plain GET with a module-level cache (static reference data). */
export function useGet<T>(path: string): Remote<T> {
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: string | null }>(() => ({
    data: (cache.get(path) as T) ?? null, loading: !cache.has(path), error: null,
  }));
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (cache.has(path) && tick === 0) return;
    let live = true;
    setState((s) => ({ ...s, loading: true }));
    api.get<T>(path).then((data) => { if (live) { remember(path, data); setState({ data, loading: false, error: null }); } })
      .catch((e) => { if (live) setState((s) => ({ ...s, loading: false, error: e?.message ?? 'Request failed.' })); });
    return () => { live = false; };
  }, [path, tick]);
  return { ...state, reload: () => { cache.delete(path); setTick((t) => t + 1); } };
}

export function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = window.setTimeout(() => setV(value), ms); return () => window.clearTimeout(t); }, [value, ms]);
  return v;
}

/**
 * The size of an element, kept up to date. The ref is a callback, so it also works for an element
 * that is not there on the first render (a page that shows a spinner until its data arrives).
 */
export function useElementSize<T extends HTMLElement>(): [(el: T | null) => void, { w: number; h: number }] {
  const [size, setSize] = useState({ w: 0, h: 0 });
  const watcher = useRef<ResizeObserver | null>(null);
  const ref = useCallback((el: T | null) => {
    watcher.current?.disconnect();
    watcher.current = null;
    if (!el) return;
    const measure = () => setSize((s) => (s.w === el.clientWidth && s.h === el.clientHeight ? s : { w: el.clientWidth, h: el.clientHeight }));
    watcher.current = new ResizeObserver(measure);
    watcher.current.observe(el);
    measure();
  }, []);
  useEffect(() => () => watcher.current?.disconnect(), []);
  return [ref, size];
}

export function useHotkey(combo: string, handler: (e: KeyboardEvent) => void, deps: unknown[] = []) {
  useEffect(() => {
    const parts = combo.toLowerCase().split('+');
    const key = parts[parts.length - 1];
    const needMod = parts.includes('mod');
    const needShift = parts.includes('shift');
    const fn = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (needMod !== mod || needShift !== e.shiftKey) return;
      if (e.key.toLowerCase() !== key) return;
      const t = e.target as HTMLElement | null;
      const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable);
      if (typing && !needMod) return;
      if (typing && (key === 'z' || key === 'y')) return;     // leave native text undo alone
      handler(e);
    };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
