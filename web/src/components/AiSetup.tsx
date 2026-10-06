// Choose the AI service that drafts the report narrative, and enter your own key for it.

import { useState } from 'react';
import { ExternalLink, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import { useAiPrefs } from '@/lib/ai';
import { useStore } from '@/lib/store';
import type { AiProvider } from '@/lib/types';
import { Button, Field, Note, Select, Spinner, TextInput } from './ui';

const OTHER = '__other__';

/** What a narrative request needs, or null while the chosen service has no key to use. */
export function useAiChoice(): { provider: AiProvider; key: string; model: string; shared: boolean; ready: boolean } | null {
  const lib = useStore((s) => s.library);
  const meta = useStore((s) => s.meta);
  const [prefs] = useAiPrefs();
  const list = lib?.report.ai_providers ?? [];
  const provider = list.find((p) => p.id === prefs.provider) ?? list[0];
  if (!provider) return null;
  const key = (prefs.keys[provider.id] ?? '').trim();
  const shared = !!meta?.operator_ai?.includes(provider.id);
  return { provider, key, model: (prefs.models[provider.id] ?? '').trim() || provider.default_model, shared, ready: !!key || shared };
}

export function AiSetup() {
  const lib = useStore((s) => s.library);
  const toast = useStore((s) => s.toast);
  const [prefs, update] = useAiPrefs();
  const choice = useAiChoice();
  const [loading, setLoading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [typing, setTyping] = useState(false);
  if (!lib || !choice) return null;
  const { provider, key, model, shared } = choice;
  const listed = prefs.lists[provider.id];
  const names = [...new Set([...(listed?.length ? listed : provider.models), model])];
  const custom = typing || !(listed?.length ? listed : provider.models).includes(model);

  const setKey = (v: string) => { setProblem(null); update((p) => ({ ...p, keys: { ...p.keys, [provider.id]: v } })); };
  const setModel = (v: string) => update((p) => ({ ...p, models: { ...p.models, [provider.id]: v } }));
  const loadModels = async () => {
    setLoading(true); setProblem(null);
    try {
      const r = await api.post<{ models: string[] }>('/ai/models', { provider: provider.id, api_key: key });
      update((p) => ({ ...p, lists: { ...p.lists, [provider.id]: r.models },
        models: r.models.includes(model) ? p.models : { ...p.models, [provider.id]: r.models.includes(provider.default_model) ? provider.default_model : r.models[0] } }));
      setTyping(false);
      toast(`${provider.company} accepted the key: ${r.models.length} models available.`);
    } catch (e: any) { setProblem(e?.message ?? 'The models could not be listed.'); }
    setLoading(false);
  };

  return (
    <>
      <Field label="AI service">
        <Select value={provider.id} onChange={(v) => { setProblem(null); setTyping(false); update((p) => ({ ...p, provider: v })); }}
                options={lib.report.ai_providers.map((p) => ({ value: p.id, label: p.label }))} />
      </Field>
      <Field label={`Your ${provider.company} API key`} hint={shared ? 'optional here' : undefined}
             help={<>Kept in this browser only. It travels with each request you make and is never stored on the server or shown to anyone else. <a href={provider.key_url} target="_blank" rel="noreferrer noopener">Get a key <ExternalLink size={10} style={{ verticalAlign: -1 }} /></a></>}>
        <TextInput type="password" value={prefs.keys[provider.id] ?? ''} onChange={setKey} autoComplete="off" placeholder={provider.key_hint} />
      </Field>
      {shared && !key && <Note kind="info" className="mt-8">This copy of Taki shares a {provider.company} key with signed-in accounts, so you can leave yours empty.</Note>}
      <Field label="Model" help={listed?.length ? `${listed.length} models listed for your key.` : 'Suggestions only. Model names change often: load the list your key can use.'}>
        <div className="row gap-4">
          <div style={{ flex: 1, minWidth: 0 }}>
            <Select value={custom ? OTHER : model} onChange={(v) => { if (v === OTHER) setTyping(true); else { setTyping(false); setModel(v); } }}
                    options={[...names.filter((m) => !custom || m !== model).map((m) => ({ value: m, label: m })), { value: OTHER, label: 'Another model…' }]} />
          </div>
          <Button size="sm" onClick={loadModels} disabled={loading || (!key && !shared)} title="Ask the service which models this key can use">{loading ? <Spinner /> : <RefreshCw size={12} />}Load my models</Button>
        </div>
      </Field>
      {custom && <Field label="Model name" help="Exactly as the service writes it."><TextInput value={model} onChange={setModel} maxLength={120} placeholder={provider.default_model} /></Field>}
      {problem && <Note kind="bad" className="mt-8">{problem}</Note>}
      {key && <Button size="sm" variant="ghost" className="mt-8" onClick={() => setKey('')}>Forget this key</Button>}
    </>
  );
}
