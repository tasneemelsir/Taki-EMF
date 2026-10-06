// Installing Taki from the browser, and knowing how this page is running.
//
// Chrome and Edge fire `beforeinstallprompt` when a page can be installed as an
// app. The event is kept here so a button of ours can show the browser's own
// install dialog later. Safari and Firefox have no such event: there the page
// can only say where the browser's own command is.
//
// This file must be imported before the page has finished loading (main.tsx
// does), or the event is missed.

import { useSyncExternalStore } from 'react';

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}
export interface InstallState {
  canPrompt: boolean;      // the browser offers to install, and a button can trigger it
  installed: boolean;      // it was installed while this page was open
  standalone: boolean;     // this page is itself running as an installed app
}

let deferred: InstallPromptEvent | null = null;
let state: InstallState = { canPrompt: false, installed: false, standalone: false };
const listeners = new Set<() => void>();

function isStandalone(): boolean {
  try {
    return window.matchMedia('(display-mode: standalone)').matches || (navigator as unknown as { standalone?: boolean }).standalone === true;
  } catch { return false; }
}

function publish(installed = state.installed) {
  state = { canPrompt: !!deferred, installed, standalone: isStandalone() };
  listeners.forEach((l) => l());
}

if (typeof window !== 'undefined') {
  state = { ...state, standalone: isStandalone() };
  window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferred = e as InstallPromptEvent; publish(); });
  window.addEventListener('appinstalled', () => { deferred = null; publish(true); });
}

/** Show the browser's install dialog. 'unavailable' when this browser has none to show. */
export async function promptInstall(): Promise<'accepted' | 'dismissed' | 'unavailable'> {
  const e = deferred;
  if (!e) return 'unavailable';
  deferred = null;                     // an event can be used once
  try {
    await e.prompt();
    const { outcome } = await e.userChoice;
    publish(outcome === 'accepted' ? true : state.installed);
    return outcome;
  } catch {
    publish();
    return 'unavailable';
  }
}

export function useInstall(): InstallState {
  return useSyncExternalStore((l) => { listeners.add(l); return () => { listeners.delete(l); }; }, () => state, () => state);
}
