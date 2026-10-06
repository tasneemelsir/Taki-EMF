import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Download, FolderOpen } from 'lucide-react';
import { Button, Card, Confirm, ErrorNote, Field, Kv, Note, TextInput } from '@/components/ui';
import { api, saveText } from '@/lib/api';
import { localDay } from '@/lib/format';
import { useStore } from '@/lib/store';
import type { User } from '@/lib/types';
import { PlainShell } from './ProjectsPage';

export default function AccountPage() {
  const { user, setUser, toast, meta } = useStore();
  const nav = useNavigate();
  const [name, setName] = useState(user?.name ?? '');
  const [organisation, setOrganisation] = useState(user?.organisation ?? '');
  const [cur, setCur] = useState('');
  const [next, setNext] = useState('');
  const [again, setAgain] = useState('');
  const [delPw, setDelPw] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pwError, setPwError] = useState<string | null>(null);
  if (!user) return null;
  const min = meta?.min_password ?? 8;

  const saveProfile = async () => {
    setError(null);
    try { const r = await api.patch<{ user: User }>('/auth/me', { name: name.trim(), organisation: organisation.trim() }); setUser(r.user); toast('Profile saved.'); }
    catch (e: any) { setError(e?.message ?? 'Could not save.'); }
  };
  const changePassword = async () => {
    setPwError(null);
    if (next !== again) { setPwError('The two new passwords do not match.'); return; }
    try { await api.post('/auth/password', { current: cur, new: next }); setCur(''); setNext(''); setAgain(''); toast('Password changed. Other devices have been signed out.'); }
    catch (e: any) { setPwError(e?.message ?? 'Could not change the password.'); }
  };
  const deleteAccount = async () => {
    try { await api.post('/auth/delete', { password: delPw }); setUser(null); nav('/login'); }
    catch (e: any) { toast(e?.message ?? 'Could not delete the account.', 'error'); }
  };
  const openFolder = async () => {
    try { await api.post('/desktop/open-data-folder'); }
    catch (e: any) { toast(e?.message ?? 'Could not open the folder.', 'error'); }
  };
  const exportAll = async () => {
    try {
      const all = await api.get<{ projects: unknown[] }>('/projects/export');
      saveText(JSON.stringify(all, null, 1), `taki-projects-${localDay()}.taki.json`, 'application/json');
      toast(`Exported ${all.projects.length} project${all.projects.length === 1 ? '' : 's'} into one file.`);
    } catch (e: any) { toast(e?.message ?? 'Could not export.', 'error'); }
  };

  // The desktop version: one person on this computer. No email, no password, nothing to delete an account from.
  if (meta?.desktop) return (
    <PlainShell crumb="Your name and data">
      <div className="page" style={{ maxWidth: 860 }}>
        <div className="page-head"><div><h1>Your name and data</h1><p className="lede">Your name goes on reports as the author. Everything you make is kept on this computer.</p></div>
          <div className="actions"><Button onClick={() => nav('/projects')}>Back to projects</Button></div></div>
        <div className="col gap-16">
          <Card title="On reports">
            <ErrorNote error={error} />
            <div className="fields-2">
              <Field label="Name"><TextInput value={name} onChange={setName} maxLength={80} /></Field>
              <Field label="Organisation"><TextInput value={organisation} onChange={setOrganisation} maxLength={120} /></Field>
            </div>
            <Button variant="primary" className="mt-12" onClick={saveProfile} disabled={name.trim() === user.name && organisation.trim() === user.organisation}>Save</Button>
          </Card>
          <Card title="Where your projects are">
            <p className="small muted">One folder on this computer holds every project and scenario. Nothing is sent anywhere. Copy the folder to keep a backup, or export the projects as one file to open them on another computer or in the web version of Taki.</p>
            <div className="mt-8"><Kv k="Folder" v={<span className="mono" style={{ userSelect: 'all', wordBreak: 'break-all' }}>{meta.data_dir ?? '—'}</span>} /></div>
            <div className="row wrap mt-12">
              <Button onClick={openFolder}><FolderOpen size={14} />Open the folder</Button>
              <Button onClick={exportAll}><Download size={14} />Export all projects</Button>
            </div>
          </Card>
        </div>
        <Note kind="info" className="mt-16">This is the desktop version of Taki {meta.version}. It runs on this computer only, has no sign-in, and stops when its last window is closed. <Link to="/privacy">What it stores</Link>.</Note>
      </div>
    </PlainShell>
  );

  return (
    <PlainShell crumb="Account">
      <div className="page" style={{ maxWidth: 860 }}>
        <div className="page-head"><div><h1>Account</h1><p className="lede">Your name appears on reports as the author. Your email is only used to sign in.</p></div>
          <div className="actions"><Button onClick={() => nav('/projects')}>Back to projects</Button></div></div>

        {user.is_guest ? (
          <Card title="Guest session">
            <p className="small">You are working without an account. Projects are tied to this browser and will be lost if its site data is cleared.</p>
            <Link className="btn primary mt-8" to="/register">Create an account and keep my projects</Link>
          </Card>
        ) : (
          <div className="col gap-16">
            <Card title="Profile">
              <ErrorNote error={error} />
              <div className="fields-2">
                <Field label="Name"><TextInput value={name} onChange={setName} maxLength={80} /></Field>
                <Field label="Organisation"><TextInput value={organisation} onChange={setOrganisation} maxLength={120} /></Field>
              </div>
              <div className="mt-12"><Kv k="Email" v={user.email} /><Kv k="Member since" v={new Date(user.created_at * 1000).toLocaleDateString()} /></div>
              <Button variant="primary" className="mt-12" onClick={saveProfile} disabled={name.trim() === user.name && organisation.trim() === user.organisation}>Save profile</Button>
            </Card>
            <Card title="Password">
              <ErrorNote error={pwError} />
              <div className="fields-3">
                <Field label="Current password"><TextInput value={cur} onChange={setCur} type="password" autoComplete="current-password" /></Field>
                <Field label="New password"><TextInput value={next} onChange={setNext} type="password" autoComplete="new-password" /></Field>
                <Field label="New password again"><TextInput value={again} onChange={setAgain} type="password" autoComplete="new-password" /></Field>
              </div>
              <Button className="mt-12" onClick={changePassword} disabled={!cur || next.length < min || !again}>Change password</Button>
              <p className="tiny muted mt-8">At least {min} characters. Changing it signs out every other device.</p>
            </Card>
            <Card title="Delete account">
              <p className="small muted">Removes your account, every project and every saved scenario from this server. This cannot be undone; export any project you want to keep first.</p>
              <div className="row mt-8" style={{ alignItems: 'flex-end' }}>
                <div style={{ width: 260 }}><Field label="Confirm with your password"><TextInput value={delPw} onChange={setDelPw} type="password" autoComplete="current-password" /></Field></div>
                <Button variant="danger" disabled={!delPw} onClick={() => setConfirmDelete(true)}>Delete my account</Button>
              </div>
            </Card>
          </div>
        )}
        <Note kind="info" className="mt-16">Passwords are stored only as salted scrypt hashes, and the session cookie cannot be read by scripts. {meta?.email ? 'A forgotten password is reset by an emailed link.' : 'A forgotten password is reset with a one-time link made by whoever runs this copy of Taki.'} <Link to="/privacy">What Taki stores about you</Link>.</Note>
      </div>
      {confirmDelete && <Confirm title="Delete your account?" danger confirmLabel="Delete everything" onClose={() => setConfirmDelete(false)} onConfirm={deleteAccount}>All of your projects and scenarios will be permanently removed.</Confirm>}
    </PlainShell>
  );
}
