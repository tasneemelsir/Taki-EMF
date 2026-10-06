// Sign in, create an account, continue as a guest, or reset a forgotten password.

import { useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { BadgeCheck, Box, FileText, Shield, Zap } from 'lucide-react';
import { Button, ErrorNote, Field, Note, TextInput } from '@/components/ui';
import { api } from '@/lib/api';
import { useStore } from '@/lib/store';
import type { User } from '@/lib/types';

function Hero() {
  const version = useStore((s) => s.meta?.version);
  return (
    <div className="auth-hero">
      <div className="brand"><span className="mark"><svg width="18" height="18" viewBox="0 0 24 24"><path d="M13.6 2 5 13.6h5.4L8.8 22 19 9.8h-6z" fill="#004B87" /></svg></span>Taki</div>
      <h1>Electric and magnetic fields around power lines, worked out properly.</h1>
      <p>Model a transmission corridor, see the field at every point, check it against exposure standards, and design shielding that holds up to scrutiny.</p>
      <ul>
        <li><Zap size={17} /><span><b>Multi-line corridors</b> with per-line voltage, current, loading and phasing, over three earth models.</span></li>
        <li><Box size={17} /><span><b>3-D digital twin</b> of the site with the field on the ground, on a movable section, and at any point you click.</span></li>
        <li><Shield size={17} /><span><b>Shielding around the building</b>: envelopes, shielded rooms, walls, loops and screens, solved physically in thirteen materials.</span></li>
        <li><BadgeCheck size={17} /><span><b>Thirteen exposure standards</b>, published benchmark comparisons and closed-form self-checks.</span></li>
        <li><FileText size={17} /><span><b>Reports</b> in PDF and Word with the figures, tables and assumptions.</span></li>
      </ul>
      <div className="fine">{version ? `Version ${version} · ` : ''}Screening and design tool. Compliance decisions need measurement by a qualified person.</div>
      <svg className="art" viewBox="0 0 520 420" fill="none" stroke="#fff" strokeWidth="2">
        <path d="M260 40 L220 400 M260 40 L300 400 M232 300 L288 300 M240 220 L280 220 M247 150 L273 150 M220 400 L288 300 M300 400 L232 300 M232 300 L280 220 M288 300 L240 220 M240 220 L273 150 M280 220 L247 150" />
        <path d="M150 110 H370 M170 180 H350 M150 110 L247 150 M370 110 L273 150 M170 180 L240 220 M350 180 L280 220" />
        {[150, 370, 170, 350].map((x, i) => <circle key={i} cx={x} cy={i < 2 ? 118 : 188} r="5" fill="#fff" />)}
        {[60, 110, 170, 240].map((r) => <ellipse key={r} cx="260" cy="150" rx={r * 1.25} ry={r} strokeWidth="1.2" strokeDasharray="3 7" />)}
      </svg>
    </div>
  );
}

/** The two-column frame of every signed-out page: the pitch on the left, a form on the right. */
export function AuthFrame({ children }: { children: React.ReactNode }) {
  const offered = useStore((s) => !!s.meta?.desktop_download);
  const setInstallOpen = useStore((s) => s.setInstallOpen);
  return (
    <div className="auth-page">
      <Hero />
      <div className="auth-form">
        {children}
        <div className="auth-foot">
          <Link to="/privacy">Privacy and your data</Link>
          {offered && <> · <button type="button" className="linklike" onClick={() => setInstallOpen(true)}>Desktop version</button></>}
        </div>
      </div>
    </div>
  );
}

function useAfterAuth() {
  const nav = useNavigate();
  const loc = useLocation();
  const setUser = useStore((s) => s.setUser);
  const loadLibrary = useStore((s) => s.loadLibrary);
  return async (user: User) => {
    setUser(user);
    try { await loadLibrary(); } catch { /* shown later */ }
    const from = (loc.state as any)?.from as string | undefined;
    const back = from && from.startsWith('/') && !from.startsWith('//') && !/^\/(login|register|forgot|reset)/.test(from);
    nav(back ? from : '/projects', { replace: true });
  };
}

export function LoginPage() {
  const meta = useStore((s) => s.meta);
  const loc = useLocation();
  const done = useAfterAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setError(null);
    try { const { user } = await api.post<{ user: User }>('/auth/login', { email, password }); await done(user); }
    catch (err: any) { setError(err?.message ?? 'Could not sign in.'); setBusy(false); }
  };
  const guest = async () => {
    setBusy(true); setError(null);
    try { const { user } = await api.post<{ user: User }>('/auth/guest'); await done(user); }
    catch (err: any) { setError(err?.message ?? 'Could not start a guest session.'); setBusy(false); }
  };

  return (
    <AuthFrame>
        <form className="auth-box" onSubmit={submit}>
          <h2>Sign in</h2>
          <p className="small muted mb-16">Open your projects and pick up where you left off.</p>
          <ErrorNote error={error} />
          <Field label="Email"><TextInput value={email} onChange={setEmail} type="email" autoComplete="email" autoFocus id="email" /></Field>
          <Field label="Password"><TextInput value={password} onChange={setPassword} type="password" autoComplete="current-password" id="password" /></Field>
          <div className="tiny" style={{ textAlign: 'right', marginTop: 6 }}><Link to="/forgot" state={{ email }}>Forgot your password?</Link></div>
          <Button variant="primary" block type="submit" disabled={busy || !email || !password} className="mt-12">{busy ? 'Signing in…' : 'Sign in'}</Button>
          {meta?.allow_guests && <>
            <div className="auth-or">or</div>
            <Button block onClick={guest} disabled={busy}>Continue as a guest</Button>
            <p className="tiny muted mt-8" style={{ textAlign: 'center' }}>No sign-up. Your work stays in this browser, and you can turn the session into an account later.</p>
          </>}
          {meta?.allow_signup && <div className="alt">New to Taki? <Link to="/register" state={loc.state}>Create an account</Link></div>}
        </form>
    </AuthFrame>
  );
}

export function ForgotPage() {
  const meta = useStore((s) => s.meta);
  const loc = useLocation();
  const [email, setEmail] = useState(((loc.state as any)?.email as string) ?? '');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setError(null);
    try { await api.post('/auth/forgot', { email }); setSent(true); }
    catch (err: any) { setError(err?.message ?? 'Could not start the reset.'); }
    setBusy(false);
  };
  return (
    <AuthFrame>
      <form className="auth-box" onSubmit={submit}>
        <h2>Reset your password</h2>
        {sent ? (
          <>
            {meta?.email
              ? <Note kind="good">If <b>{email}</b> has an account, a link to choose a new password is on its way. It works once, for an hour. Check the spam folder if it does not arrive.</Note>
              : <Note kind="info">This copy of Taki has no email service. If <b>{email}</b> has an account, a reset link has been printed in the window of the Taki server: ask whoever runs it to send it to you. It works once, for an hour.</Note>}
            <div className="alt"><Link to="/login">Back to sign in</Link></div>
          </>
        ) : (
          <>
            <p className="small muted mb-16">Enter the email of your account. {meta?.email ? 'We will send a link to choose a new password.' : 'A reset link will be made for it.'}</p>
            <ErrorNote error={error} />
            <Field label="Email"><TextInput value={email} onChange={setEmail} type="email" autoComplete="email" autoFocus /></Field>
            <Button variant="primary" block type="submit" disabled={busy || !email} className="mt-16">{busy ? 'Working…' : 'Send reset link'}</Button>
            <div className="alt"><Link to="/login">Back to sign in</Link></div>
          </>
        )}
      </form>
    </AuthFrame>
  );
}

export function ResetPage() {
  const meta = useStore((s) => s.meta);
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const done = useAfterAuth();
  const [password, setPassword] = useState('');
  const [again, setAgain] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const min = meta?.min_password ?? 8;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== again) { setError('The two passwords do not match.'); return; }
    setBusy(true); setError(null);
    try { const { user } = await api.post<{ user: User }>('/auth/reset', { token, password }); await done(user); }
    catch (err: any) { setError(err?.message ?? 'Could not set the password.'); setBusy(false); }
  };
  return (
    <AuthFrame>
      <form className="auth-box" onSubmit={submit}>
        <h2>Choose a new password</h2>
        {!token ? <Note kind="bad">This page needs the link from the reset message. <Link to="/forgot">Ask for a new one.</Link></Note> : (
          <>
            <p className="small muted mb-16">You will be signed in with it, and signed out everywhere else.</p>
            <ErrorNote error={error} />
            <Field label="New password" help={`At least ${min} characters.`}><TextInput value={password} onChange={setPassword} type="password" autoComplete="new-password" autoFocus /></Field>
            <Field label="New password again"><TextInput value={again} onChange={setAgain} type="password" autoComplete="new-password" /></Field>
            <Button variant="primary" block type="submit" disabled={busy || password.length < min || !again} className="mt-16">{busy ? 'Saving…' : 'Set password and sign in'}</Button>
            <div className="alt"><Link to="/forgot">Ask for a new link</Link> · <Link to="/login">Sign in</Link></div>
          </>
        )}
      </form>
    </AuthFrame>
  );
}

export function RegisterPage() {
  const meta = useStore((s) => s.meta);
  const current = useStore((s) => s.user);
  const loc = useLocation();
  const done = useAfterAuth();
  const [name, setName] = useState('');
  const [organisation, setOrganisation] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const min = meta?.min_password ?? 8;
  const upgrading = !!current?.is_guest;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setError(null);
    try { const { user } = await api.post<{ user: User }>('/auth/register', { name, organisation, email, password }); await done(user); }
    catch (err: any) { setError(err?.message ?? 'Could not create the account.'); setBusy(false); }
  };

  return (
    <AuthFrame>
        <form className="auth-box" onSubmit={submit}>
          <h2>Create your account</h2>
          <p className="small muted mb-16">{upgrading ? 'Your guest projects move into the new account.' : 'Free. Your projects are saved and available wherever you sign in.'}</p>
          {meta && !meta.allow_signup && <Note kind="bad" className="mb-12">New accounts are switched off on this server.</Note>}
          <ErrorNote error={error} />
          <div className="fields-2">
            <Field label="Name"><TextInput value={name} onChange={setName} autoComplete="name" autoFocus maxLength={80} /></Field>
            <Field label="Organisation" hint="optional"><TextInput value={organisation} onChange={setOrganisation} autoComplete="organization" maxLength={120} /></Field>
          </div>
          <Field label="Email" className="mt-8"><TextInput value={email} onChange={setEmail} type="email" autoComplete="email" /></Field>
          <Field label="Password" help={`At least ${min} characters. A phrase of a few words is both stronger and easier to remember.`}>
            <TextInput value={password} onChange={setPassword} type="password" autoComplete="new-password" />
          </Field>
          <Button variant="primary" block type="submit" disabled={busy || !email || password.length < min} className="mt-16">{busy ? 'Creating…' : 'Create account'}</Button>
          <div className="alt">Already have an account? <Link to="/login" state={loc.state}>Sign in</Link></div>
          {upgrading && <div className="alt" style={{ marginTop: 6 }}><Link to="/projects">Back to my projects</Link></div>}
        </form>
    </AuthFrame>
  );
}
