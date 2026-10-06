// What this copy of Taki stores about the people who use it. Plain statements
// of what the software does; whoever publishes a copy is responsible for it.

import { Link } from 'react-router-dom';
import { useStore } from '@/lib/store';

export default function PrivacyPage() {
  const meta = useStore((s) => s.meta);
  const user = useStore((s) => s.user);
  const where = meta?.database === 'postgresql'
    ? `an online PostgreSQL database${meta.database_host && !/computer|server/i.test(meta.database_host) ? ` hosted by ${meta.database_host}` : ''}`
    : 'a database file on the computer that runs this copy of Taki';
  // The desktop version has no accounts and no server elsewhere: a much shorter story.
  if (meta?.desktop) return (
    <div className="page prose" style={{ maxWidth: 760, margin: '0 auto', padding: '40px 24px 80px' }}>
      <div className="eyebrow">Taki · desktop version</div>
      <h1>Privacy and your data</h1>
      <p className="lede">Everything stays on this computer.</p>

      <h3>What is stored, and where</h3>
      <ul>
        <li><b>Your work</b>: the projects and scenarios you create, and the name and organisation you want on reports.</li>
        <li>It is kept in one folder on this computer{meta.data_dir ? <>: <span className="mono" style={{ wordBreak: 'break-all' }}>{meta.data_dir}</span></> : ''}. Taki sends it nowhere.</li>
        <li>There is no account, no password and no sign-in. Whoever can use this computer as you can open Taki and see the projects.</li>
      </ul>

      <h3>What is not stored or sent</h3>
      <ul>
        <li>No advertising, analytics or tracking, and nothing is loaded from other sites.</li>
        <li>The program listens on this computer only (127.0.0.1); other computers on the network cannot reach it.</li>
        <li>Calculation requests are computed and discarded. Only what you save as a project or scenario is kept.</li>
      </ul>

      <h3>The one feature that contacts another service</h3>
      <ul>
        <li><b>AI narrative in reports</b>: only when you ask for it, the calculated results of that project are sent to the AI service you chose (Anthropic, Google or OpenAI) to write the text, with the API key you entered. The key is kept in this window's own storage on this computer.</li>
      </ul>

      <h3>Removing your data</h3>
      <p>Delete a project from the projects page. To remove everything, uninstall Taki (Start menu, <i>Uninstall Taki</i>) and answer yes when it asks about the projects, or delete the folder above. Export the projects first if you may want them again.</p>

      <p className="mt-24"><Link className="btn" to="/projects">Back to projects</Link></p>
    </div>
  );
  return (
    <div className="page prose" style={{ maxWidth: 760, margin: '0 auto', padding: '40px 24px 80px' }}>
      <div className="eyebrow">Taki</div>
      <h1>Privacy and your data</h1>
      <p className="lede">What this copy of Taki keeps, where, and how to remove it.</p>

      <h3>What is stored</h3>
      <ul>
        <li><b>Your account</b>: name, organisation (if you gave one), email address, and a salted scrypt hash of your password. The password itself is never stored and cannot be read back by anyone.</li>
        <li><b>Your work</b>: the projects and scenarios you create (line, site, shield and standards inputs) and your display preferences.</li>
        <li><b>Sign-ins</b>: one record per signed-in browser, holding a hash of the session token, its expiry and the browser's name. Expired ones are deleted automatically.</li>
        <li><b>Guests</b>: a guest session keeps its projects under an anonymous record with no name or email. It is deleted 30 days after it was last used.</li>
      </ul>
      <p>It is kept in {where}.</p>

      <h3>What is not stored or sent</h3>
      <ul>
        <li>No advertising, analytics or tracking scripts, and no third-party cookies.</li>
        <li>The pages load nothing from other sites: no external fonts, scripts or images.</li>
        <li>Calculation requests are computed and discarded. Only what you save as a project or scenario is kept.</li>
      </ul>

      <h3>Cookies</h3>
      <p>One cookie, <span className="mono">taki_session</span>, keeps you signed in. It is HttpOnly (scripts cannot read it) and is not shared with any other site. Display choices such as the dark theme are kept in your browser's local storage.</p>

      <h3>Optional features that contact other services</h3>
      <ul>
        <li><b>AI narrative in reports</b>: when you ask for it, the calculated results of that project (not your account details) are sent to the AI service you chose (Anthropic, Google or OpenAI) to write the text. It uses the API key you enter for that service. Your key is kept in your browser, passes through this server only inside that request, and is not stored, logged or shown to anyone else, including the person who runs this copy.{meta?.operator_ai?.length ? ` This copy also shares a key of its own for ${meta.operator_ai.join(', ')}, which signed-in accounts may use instead of their own.` : ''}</li>
        <li><b>Password-reset email</b>: {meta?.email ? 'sent through the mail service the operator configured, to your address only.' : 'not configured on this copy; a reset link is handed out by whoever runs it.'}</li>
        <li><b>Share links</b>: a project is visible to people outside your account only if you create a share link for it, and only to those who have the link. You can stop sharing at any time.</li>
      </ul>

      <h3>Removing your data</h3>
      <p>Delete a project from the projects page, or delete your account, with every project and scenario, under <Link to="/account">Account</Link>. Deletion is immediate and cannot be undone. You can export any project as a file first.</p>

      <h3>Who is responsible</h3>
      <p>Taki is software. The person or organisation that runs this copy decides who may use it and is responsible for the data in it; contact them with any request about your data.</p>

      <p className="mt-24"><Link className="btn" to={user ? '/projects' : '/login'}>{user ? 'Back to projects' : 'Back to sign in'}</Link></p>
    </div>
  );
}
