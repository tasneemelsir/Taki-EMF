// "Taki as an app": the two ways out of the browser tab. The desktop version
// runs on the person's own computer; installing from the browser keeps using
// this site in a window of its own.

import { useState } from 'react';
import { Check, Download, MonitorDown } from 'lucide-react';
import { promptInstall, useInstall } from '@/lib/install';
import { useStore } from '@/lib/store';
import { Button, Card, Modal, Note, Pill } from './ui';

export function InstallModal({ onClose }: { onClose: () => void }) {
  const meta = useStore((s) => s.meta);
  const toast = useStore((s) => s.toast);
  const inst = useInstall();
  const [busy, setBusy] = useState(false);

  const install = async () => {
    setBusy(true);
    const outcome = await promptInstall();
    setBusy(false);
    if (outcome === 'accepted') toast('Taki is installed. Look for its icon on the desktop or in the Start menu.');
    else if (outcome === 'unavailable') toast('This browser did not offer to install. Use its own menu, described below.', 'error');
  };

  return (
    <Modal title="Taki as an app" wide onClose={onClose} footer={<Button onClick={onClose}>Close</Button>}>
      <p className="small muted" style={{ marginTop: 0 }}>Two ways to have Taki outside a browser tab. They do not get in each other's way: use either, or both.</p>
      <div className="grid c2 mt-12" style={{ alignItems: 'stretch' }}>
        <Card title="Desktop version" actions={<Pill tone="teal">works offline</Pill>}>
          <p className="small">Taki on your own computer: its own window and icon, no sign-in, and no internet once it is installed. Projects are kept on the computer.</p>
          {meta?.desktop_download ? (
            <>
              <a className="btn primary mt-12" href="/api/desktop/package" download><Download size={14} />Download the desktop version</a>
              <div className="tiny muted mt-8">One zip of about 3 MB, for Windows, macOS and Linux. Version {meta.version}.</div>
              <ol className="small install-steps">
                <li>Take the folder out of the zip: right-click it, <i>Extract All</i>.</li>
                <li><b>Windows:</b> double-click <i>Install Taki</i>. Once, it fetches Python and the calculation libraries (about 55 MB) into a folder of its own. No administrator rights are needed.</li>
                <li>Start Taki from its icon on the desktop or in the Start menu.</li>
              </ol>
              <div className="tiny muted"><b>macOS, Linux:</b> in a terminal in that folder, <span className="mono">sh start-desktop.sh</span></div>
            </>
          ) : (
            <Note kind="info" className="mt-12">This copy of Taki does not hand out the desktop version. Ask whoever runs it for the download.</Note>
          )}
        </Card>
        <Card title="Install from this browser" actions={<Pill tone="blue">uses this site</Pill>}>
          <p className="small">The same Taki you are using now, in a window of its own with an icon on the desktop, the taskbar or the home screen. Your account and projects stay where they are. It needs this site to be reachable.</p>
          {inst.standalone ? (
            <Note kind="good" className="mt-12"><Check size={13} /> This window is the installed app.</Note>
          ) : inst.installed ? (
            <Note kind="good" className="mt-12"><Check size={13} /> Installed. Look for the Taki icon on the desktop or in the Start menu.</Note>
          ) : (
            <>
              <Button variant={inst.canPrompt ? 'primary' : undefined} className="mt-12" disabled={!inst.canPrompt || busy} onClick={install}><MonitorDown size={14} />{inst.canPrompt ? 'Install Taki' : 'Install from the browser menu'}</Button>
              {!inst.canPrompt && <div className="tiny muted mt-8">This browser has not offered to install here, or Taki is installed in it already.</div>}
            </>
          )}
          <ul className="small install-steps">
            <li><b>Chrome, Edge:</b> the install icon at the end of the address bar, or the browser menu, <i>Install Taki</i>.</li>
            <li><b>Safari on a Mac:</b> <i>File</i>, then <i>Add to Dock</i>.</li>
            <li><b>iPhone, iPad:</b> <i>Share</i>, then <i>Add to Home Screen</i>.</li>
          </ul>
        </Card>
      </div>
      <Note kind="info" className="mt-12">To take your projects from one to the other, use <b>Export all</b> on the projects page here and <b>Import</b> there. One file carries every project with its scenarios.</Note>
    </Modal>
  );
}
