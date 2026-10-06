import React, { Suspense, useEffect } from 'react';
import { BrowserRouter, Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { InstallModal } from '@/components/InstallModal';
import { BrandMark, Shell } from '@/components/Shell';
import { Button, Spinner, Toasts } from '@/components/ui';
import { setUnauthorisedHandler } from '@/lib/api';
import { useStore } from '@/lib/store';
import AccountPage from '@/pages/AccountPage';
import { ForgotPage, LoginPage, RegisterPage, ResetPage } from '@/pages/AuthPages';
import ComparePage from '@/pages/ComparePage';
import Dashboard from '@/pages/Dashboard';
import EarthPage from '@/pages/EarthPage';
import FieldLinesPage from '@/pages/FieldLinesPage';
import LibraryPage from '@/pages/LibraryPage';
import MapPage from '@/pages/MapPage';
import MeasurePage from '@/pages/MeasurePage';
import PrivacyPage from '@/pages/PrivacyPage';
import ProfilePage from '@/pages/ProfilePage';
import ProjectsPage from '@/pages/ProjectsPage';
import ReportPage from '@/pages/ReportPage';
import ScenariosPage from '@/pages/ScenariosPage';
import SettingsPage from '@/pages/SettingsPage';
import SharedPage from '@/pages/SharedPage';
import ShieldPage from '@/pages/ShieldPage';
import ValidationPage from '@/pages/ValidationPage';

const TwinPage = React.lazy(() => import('@/pages/TwinPage'));

function Splash({ label }: { label?: string }) {
  return <div style={{ height: '100vh', display: 'grid', placeItems: 'center' }}><div className="row muted small"><Spinner />{label ?? 'Loading Taki…'}</div></div>;
}

class ErrorBoundary extends React.Component<{ children: React.ReactNode; resetKey: string }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidUpdate(prev: { resetKey: string }) { if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null }); }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="empty" style={{ paddingTop: 90 }}>
        <h3>This page ran into a problem</h3>
        <div className="small">Your project is safe: inputs are saved on the server as you work.</div>
        <div className="small mono mt-8" style={{ maxWidth: 560, margin: '8px auto 0' }}>{String(this.state.error.message || this.state.error)}</div>
        <div className="row mt-12" style={{ justifyContent: 'center' }}>
          <Button variant="primary" onClick={() => this.setState({ error: null })}>Try again</Button>
          <Button onClick={() => window.location.reload()}>Reload</Button>
        </div>
      </div>
    );
  }
}

function Guarded({ children }: { children: React.ReactNode }) {
  const loc = useLocation();
  return <ErrorBoundary resetKey={loc.pathname}><Suspense fallback={<div className="empty" style={{ paddingTop: 120 }}><Spinner /></div>}>{children}</Suspense></ErrorBoundary>;
}

function RequireAuth() {
  const user = useStore((s) => s.user);
  const library = useStore((s) => s.library);
  const loadLibrary = useStore((s) => s.loadLibrary);
  const loc = useLocation();
  useEffect(() => { if (user && !library) void loadLibrary().catch(() => undefined); }, [user, library, loadLibrary]);
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (!library) return <Splash label="Loading the reference library…" />;
  return <Outlet />;
}

function Home() {
  const user = useStore((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  let last: string | null = null;
  try { last = localStorage.getItem('taki.lastProject'); } catch { /* ignore */ }
  return <Navigate to={last && !user.is_guest ? '/projects' : '/projects'} replace />;
}

/** Desktop version only: the window has no session any more (there is no sign-in to go back to). */
function DesktopLost() {
  return (
    <div className="empty" style={{ paddingTop: 120 }}>
      <span className="nav-brand" style={{ border: 0, padding: 0, height: 'auto', justifyContent: 'center', marginBottom: 14 }}><span className="mark"><BrandMark /></span></span>
      <h3>Open Taki again</h3>
      <div className="small" style={{ maxWidth: 420, margin: '0 auto' }}>This window has lost its link to the program on this computer. Close it and start Taki from its icon. Your projects are safe.</div>
    </div>
  );
}

/** One dialog for the whole app, opened from the account menu, the sign-in page or the settings. */
function InstallDialog() {
  const open = useStore((s) => s.installOpen);
  const setOpen = useStore((s) => s.setInstallOpen);
  return open ? <InstallModal onClose={() => setOpen(false)} /> : null;
}

function NotFound() {
  return (
    <div className="empty" style={{ paddingTop: 120 }}>
      <h3>Page not found</h3>
      <div className="small">That address does not match anything in Taki.</div>
      <div className="mt-12"><Link className="btn primary" to="/projects">Go to projects</Link></div>
    </div>
  );
}

export default function App() {
  const booted = useStore((s) => s.booted);
  const user = useStore((s) => s.user);
  const boot = useStore((s) => s.boot);
  useEffect(() => {
    setUnauthorisedHandler(() => useStore.getState().setUser(null));
    void boot();
  }, [boot]);
  const meta = useStore((s) => s.meta);
  if (!booted) return <Splash />;
  if (meta?.desktop && !user) return <DesktopLost />;
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={user && !user.is_guest ? <Navigate to="/projects" replace /> : <LoginPage />} />
        <Route path="/register" element={user && !user.is_guest ? <Navigate to="/projects" replace /> : <RegisterPage />} />
        <Route path="/forgot" element={user && !user.is_guest ? <Navigate to="/account" replace /> : <ForgotPage />} />
        <Route path="/reset" element={<ResetPage />} />
        <Route path="/s/:token" element={<SharedPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/projects" element={<Guarded><ProjectsPage /></Guarded>} />
          <Route path="/account" element={<Guarded><AccountPage /></Guarded>} />
          <Route path="/p/:pid" element={<Shell />}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<Guarded><Dashboard /></Guarded>} />
            <Route path="profile" element={<Guarded><ProfilePage /></Guarded>} />
            <Route path="map" element={<Guarded><MapPage /></Guarded>} />
            <Route path="field-lines" element={<Guarded><FieldLinesPage /></Guarded>} />
            <Route path="earth" element={<Guarded><EarthPage /></Guarded>} />
            <Route path="measure" element={<Guarded><MeasurePage /></Guarded>} />
            <Route path="shield" element={<Guarded><ShieldPage /></Guarded>} />
            <Route path="compare" element={<Guarded><ComparePage /></Guarded>} />
            <Route path="twin" element={<Guarded><TwinPage /></Guarded>} />
            <Route path="scenarios" element={<Guarded><ScenariosPage /></Guarded>} />
            <Route path="validation" element={<Guarded><ValidationPage /></Guarded>} />
            <Route path="report" element={<Guarded><ReportPage /></Guarded>} />
            <Route path="library" element={<Guarded><LibraryPage /></Guarded>} />
            <Route path="settings" element={<Guarded><SettingsPage /></Guarded>} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
      <InstallDialog />
      <Toasts />
    </BrowserRouter>
  );
}
