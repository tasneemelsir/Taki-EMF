// Landing page of a share link (/s/<token>): shows what is being shared and
// puts a copy of it in the visitor's own projects.

import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Button, ErrorNote, Spinner } from '@/components/ui';
import { api } from '@/lib/api';
import { fmt, STATUS_LABEL } from '@/lib/format';
import { useStore } from '@/lib/store';
import type { ProjectMeta, User } from '@/lib/types';
import { Badge } from '@/components/ui';
import { AuthFrame } from './AuthPages';

interface Shared { name: string; description: string; owner: { name: string; organisation: string }; summary: ProjectMeta['summary']; updated_at: number; scenarios: number }

export default function SharedPage() {
  const { token } = useParams();
  const nav = useNavigate();
  const { user, meta, setUser, loadLibrary } = useStore();
  const [info, setInfo] = useState<Shared | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<Shared>(`/shared/${token}`).then(setInfo).catch((e) => setError(e?.message ?? 'This link could not be opened.'));
  }, [token]);

  const open = async (asGuest: boolean) => {
    setBusy(true); setError(null);
    try {
      if (!user && asGuest) {
        const r = await api.post<{ user: User }>('/auth/guest');
        setUser(r.user);
        try { await loadLibrary(); } catch { /* loaded again by the workspace */ }
      }
      const r = await api.post<{ project: { id: string } }>(`/shared/${token}/open`);
      nav(`/p/${r.project.id}/dashboard`, { replace: true });
    } catch (e: any) { setError(e?.message ?? 'Could not open the project.'); setBusy(false); }
  };

  const s = info?.summary;
  return (
    <AuthFrame>
      <div className="auth-box">
        <h2>Shared project</h2>
        <ErrorNote error={error} />
        {!info && !error && <div className="row muted small"><Spinner />Opening the link…</div>}
        {info && <>
          <p className="small muted mb-16">{info.owner.name}{info.owner.organisation ? ` (${info.owner.organisation})` : ''} shared a Taki project with you.</p>
          <div className="card" style={{ padding: 14 }}>
            <div className="row between"><b>{info.name}</b>{s?.overall && <Badge status={s.overall}>{STATUS_LABEL[s.overall]}</Badge>}</div>
            {info.description && <div className="small muted mt-4">{info.description}</div>}
            <div className="small mt-8 mono">
              {s?.peak_b !== undefined && <>Peak B {fmt(s.peak_b)} µT · </>}
              {s?.peak_e !== undefined && <>Peak E {fmt(s.peak_e)} kV/m · </>}
              {s?.kv?.length ? `${s.kv.map((k) => k.toFixed(0)).join(' + ')} kV` : ''}
            </div>
            <div className="tiny muted mt-8">{info.scenarios ? `${info.scenarios} saved scenario${info.scenarios === 1 ? '' : 's'} · ` : ''}last changed {new Date(info.updated_at * 1000).toLocaleDateString()}</div>
          </div>
          <p className="small muted mt-12">Opening it puts your own copy in your projects. Nothing you change reaches the original.</p>
          {user ? (
            <Button variant="primary" block className="mt-12" disabled={busy} onClick={() => open(false)}>{busy ? 'Opening…' : 'Open my copy'}</Button>
          ) : (<>
            <Link className="btn primary block mt-12" to="/login" state={{ from: `/s/${token}` }}>Sign in to open it</Link>
            {meta?.allow_guests && <Button block className="mt-8" disabled={busy} onClick={() => open(true)}>{busy ? 'Opening…' : 'Open it as a guest'}</Button>}
            {meta?.allow_signup && <div className="alt">New to Taki? <Link to="/register" state={{ from: `/s/${token}` }}>Create an account</Link></div>}
          </>)}
        </>}
        {error && <div className="alt"><Link to="/projects">Go to my projects</Link></div>}
      </div>
    </AuthFrame>
  );
}
