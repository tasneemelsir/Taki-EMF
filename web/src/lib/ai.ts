// The AI service each person chooses for the report narrative, and their key for it.
// Everything here lives in this browser's storage. A key leaves it only inside the one
// request that uses it; the server passes it on to the service and does not keep it.

import { useEffect, useState } from 'react';

export interface AiPrefs {
  provider: string;
  keys: Record<string, string>;
  models: Record<string, string>;
  /** model names each service listed for the key, so the list survives a reload */
  lists: Record<string, string[]>;
}

const KEY = 'taki.ai';
const LEGACY_KEY = 'taki.aiKey';          // v4.0-4.1 kept one Anthropic key under this name

function read(): AiPrefs {
  const base: AiPrefs = { provider: 'anthropic', keys: {}, models: {}, lists: {} };
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const v = JSON.parse(raw);
      return { provider: typeof v.provider === 'string' ? v.provider : base.provider, keys: v.keys ?? {}, models: v.models ?? {}, lists: v.lists ?? {} };
    }
    const old = localStorage.getItem(LEGACY_KEY);
    if (old) base.keys.anthropic = old;
  } catch { /* storage unavailable: nothing is remembered */ }
  return base;
}

let state: AiPrefs = read();
const listeners = new Set<() => void>();

function write(next: AiPrefs) {
  state = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
    localStorage.removeItem(LEGACY_KEY);
  } catch { /* ignore */ }
  listeners.forEach((fn) => fn());
}

export function getAiPrefs(): AiPrefs { return state; }

/** Read and change the AI preferences; every component using this stays in step. */
export function useAiPrefs(): [AiPrefs, (patch: (p: AiPrefs) => AiPrefs) => void] {
  const [, tick] = useState(0);
  useEffect(() => {
    const fn = () => tick((n) => n + 1);
    listeners.add(fn);
    return () => { listeners.delete(fn); };
  }, []);
  return [state, (patch) => write(patch(state))];
}
