// "Share a copy": a link that gives whoever opens it their own copy of the
// project. The owner's project is never changed by anyone else.

import { useEffect, useState } from 'react';
import { Check, Copy, Link2, Link2Off } from 'lucide-react';
import { api } from '@/lib/api';
import { useStore } from '@/lib/store';
import { Button, ErrorNote, Modal, Note, Spinner } from './ui';

export function ShareModal({ projectId, name, onClose, onChanged }: { projectId: string; name: string; onClose: () => void; onChanged?: (shared: boolean) => void }) {
  const toast = useStore((s) => s.toast);
  const saveNow = useStore((s) => s.saveNow);
  const [token, setToken] = useState<string | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let live = true;
    api.get<{ project: { share?: string | null } }>(`/projects/${projectId}`)
      .then((r) => { if (live) setToken(r.project.share ?? null); })
      .catch((e) => { if (live) { setError(e?.message ?? 'Could not read the project.'); setToken(null); } });
    return () => { live = false; };
  }, [projectId]);

  const url = token ? `${window.location.origin}/s/${token}` : '';
  const create = async () => {
    setBusy(true); setError(null);
    try {
      await saveNow();                                   // the link hands out what is saved
      const r = await api.post<{ token: string }>(`/projects/${projectId}/share`);
      setToken(r.token); onChanged?.(true);
    } catch (e: any) { setError(e?.message ?? 'Could not create the link.'); }
    setBusy(false);
  };
  const stop = async () => {
    setBusy(true); setError(null);
    try { await api.del(`/projects/${projectId}/share`); setToken(null); onChanged?.(false); toast('Sharing stopped. The old link no longer works.'); }
    catch (e: any) { setError(e?.message ?? 'Could not stop sharing.'); }
    setBusy(false);
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(url); setCopied(true); setTimeout(() => setCopied(false), 1800); }
    catch { toast('Select the link and copy it by hand.', 'error'); }
  };

  return (
    <Modal title="Share a copy" onClose={onClose} footer={<Button onClick={onClose}>Done</Button>}>
      <ErrorNote error={error} />
      {token === undefined ? <div className="row muted small"><Spinner />Checking…</div> : token ? (
        <>
          <p className="small">Anyone with this link can open their own copy of <b>{name}</b>, with its saved scenarios. Your project stays yours: nothing they change comes back to it.</p>
          <div className="row mt-8" style={{ gap: 6 }}>
            <input className="input mono" readOnly value={url} onFocus={(e) => e.currentTarget.select()} aria-label="Share link" style={{ flex: 1, fontSize: 12 }} />
            <Button variant="primary" onClick={copy}>{copied ? <><Check size={14} />Copied</> : <><Copy size={14} />Copy</>}</Button>
          </div>
          <Note kind="info" className="mt-12">The copy is taken when the link is opened, so it always carries your latest saved inputs.</Note>
          <Button variant="ghost" className="mt-12" disabled={busy} onClick={stop}><Link2Off size={14} />Stop sharing</Button>
        </>
      ) : (
        <>
          <p className="small">Create a link to send <b>{name}</b> to a colleague, a client or a supervisor. They get their own copy to open, change and report from, with or without an account. Your project is not affected.</p>
          <Button variant="primary" className="mt-12" disabled={busy} onClick={create}><Link2 size={14} />{busy ? 'Creating…' : 'Create link'}</Button>
        </>
      )}
    </Modal>
  );
}
