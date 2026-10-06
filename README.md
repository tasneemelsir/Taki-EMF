# Taki

Electric and magnetic fields around high-voltage overhead lines: simulation, exposure-standard
assessment, shielding design, a 3-D digital twin of the site, and reports. A web application with
accounts and saved projects, which also installs as a desktop program that needs neither an
account nor the internet.

Taki is a screening and design tool. Its numbers are calculated estimates; a compliance decision
needs as-built line data and measurements by a qualified person.

---

## Contents

1. [Start it](#1-start-it)
2. [The desktop version](#2-the-desktop-version)
3. [What it does](#3-what-it-does)
4. [Accounts and where the data lives](#4-accounts-and-where-the-data-lives)
5. [Use an online database (Supabase or Neon)](#5-use-an-online-database-supabase-or-neon)
6. [Put it on the internet](#6-put-it-on-the-internet)
7. [Settings](#7-settings)
8. [What is calculated, and how far to trust it](#8-what-is-calculated-and-how-far-to-trust-it)
9. [What changed](#9-what-changed)
10. [Project layout](#10-project-layout)
11. [Working on the code](#11-working-on-the-code)

---

## 1. Start it

You need **Python 3.10 or newer**. Nothing else: the web interface is already built.

| | |
|---|---|
| **Windows** | double-click `start.bat` |
| **macOS / Linux** | `sh start.sh` |

The first run takes a few minutes (it makes its own Python environment in `.venv` and installs
what it needs). After that it starts in seconds and opens <http://localhost:8000> in your browser.

By hand, if you prefer:

```
pip install -r requirements.txt
python run.py
```

Create an account, or press **Continue as a guest** to look around first. A guest session can be
turned into an account later without losing its projects.

**Replacing an older copy.** Unzip the new version into a new folder, then copy two things across
from the old folder before you start it: the `data` folder (your accounts and projects, if you
keep them on this computer) and the `.env` file (your settings, including the connection to an
online database if you set one up). Nothing else needs to move.

---

## 2. The desktop version

The same Taki as a program on one computer: a window of its own, an icon on the desktop, no
sign-in, and no internet once it is installed. Projects are kept on that computer.

### Install it on Windows

Double-click **`install-desktop.bat`**. People who use the web version get the same thing as a
download: account menu, *Taki as an app*, *Download the desktop version*. In that download the
file is called **Install Taki**.

It asks for no administrator password and does not need Python on the computer. Once, it fetches

* Python 3.13 from python.org, for Taki alone, and
* the calculation libraries from pypi.org (about 45 MB), at the exact versions in
  `requirements-desktop.lock`, each file checked against its SHA-256 before it is used.

It then puts a **Taki** icon on the desktop and in the Start menu, lists Taki under *Installed
apps*, and starts it.

| | |
|---|---|
| The program | `%LOCALAPPDATA%\Programs\Taki` (about 200 MB) |
| Your projects | `%LOCALAPPDATA%\Taki` |
| Update | run the installer of a newer copy; the projects are kept |
| Remove | Start menu, *Uninstall Taki*. It asks before it touches the projects |
| Taskbar | pin the Taki icon from the desktop, not the open window |
| A computer without internet | install on one that has it, copy `%LOCALAPPDATA%\Programs\Taki` to the same place on the other, and run `app\install-desktop.bat` inside it. That makes the shortcuts and fetches nothing |

If python.org cannot be reached, the installer uses a Python 3.10 or newer that is already on the
computer instead. A file `python-3.13.x-embed-amd64.zip` put beside the installer is used in
place of the download, and a folder `wheels` beside it in place of pypi.org.

### macOS and Linux

```
sh start-desktop.sh
```

Python 3.10 or newer is needed. The window is Chrome, Edge or Chromium if one is installed;
otherwise Taki opens as a tab of the usual browser. Projects are kept in
`~/Library/Application Support/Taki` (macOS) or `~/.local/share/taki` (Linux).

From a copy that is already set up, `python run.py desktop` does the same on any system.

### How it behaves

* **One person, no sign-in.** The program signs its own window in. There is no password, no
  account and no guest session; the name on reports is set under *Your name and data*.
* **A window of its own.** Edge (every Windows computer has it) or Chrome in "app" mode, with a
  browser profile of its own in the data folder, so it shares nothing with your everyday browsing.
* **Starts at once.** The window opens within a second or two and shows *Starting Taki* while
  the calculation engine loads behind it.
* **Stops with its window.** Each open window holds a quiet connection to the program; a few
  seconds after the last one closes, the program ends. Starting Taki again while it runs opens
  a second window on the same copy.
* **This computer only.** It listens on `127.0.0.1`, so nothing else on the network can reach
  it, and it answers only when addressed as this computer.
* **Never an online database.** The `.env` file and `DATABASE_URL` are ignored.
* **Sharing links are left out**, since a link to this computer is no use to anyone else. Send
  the project file instead (*Export file*).
* If something goes wrong it says so in a message box; the details are in `taki.log` in the
  data folder.

| Setting (environment) | Meaning | Default |
|---|---|---|
| `TAKI_DESKTOP_DATA_DIR` | folder for the projects (also `--data-dir`) | see above |
| `TAKI_DESKTOP_PORT` | port on this computer (also `--port`); a free one is used if it is taken | 8254 |
| `TAKI_DESKTOP_WINDOW` | `app`, `tab` (the usual browser) or `none` (also `--window`) | `app` |
| `TAKI_BROWSER` | the browser to use for the window, as a path or a name | found automatically |

### Moving projects between the two

On the projects page, **Export all** writes every project with its scenarios into one file, and
**Import** reads such a file back in, on the web version and on the desktop version alike. That
one file is also the backup.

### Installing the web version from the browser

Separately from all this, the web version can be installed as an app from Chrome, Edge or
Safari (account menu, *Taki as an app*, *Install Taki*). That gives the same site a window and an
icon of its own. It still needs the site: use it for a hosted Taki you want one click away, and
the desktop version when the work has to stay on the computer or happen offline.

---

## 3. What it does

**Lines** – one to four parallel lines in a corridor. A line is one row of towers: four presets
(132 kV double circuit, 275 kV monopole, 500 kV quadruple bundle, and a 275/132 kV tower carrying
four circuits) or a custom geometry, with voltage, rated current, loading, phase arrangement
(ABC-ABC / ABC-CBA), phase offset, bundle, centreline offset and height adjustment. Loading sets
the operating current and the thermal sag.

On a tower that carries more than one circuit, **each circuit can be set on its own**: voltage,
rated current, loading, phase order, and whether it is in service. A circuit out of service is
taken as de-energised and earthed.

Span length by itself does not change the reading at mid-span, because the mid-span heights are
what you enter. Switch on **Sag follows the span** and the towers keep their height while the sag
grows with the square of the span, so a longer span hangs lower and reads higher. The lowest
conductor is shown with an indicative minimum ground clearance for its voltage.

**Site** – right-of-way, span, three earth models (free space, perfectly conducting earth,
complex-image earth with soil resistivity), 50/60 Hz, and up to six buildings of six types
(residential, office, school, hospital, data centre, warehouse) with shape, roof, size and position.

**Results** – lateral profile, 2-D field maps for B and E, magnetic and electric field lines that
can be played through the AC cycle, earth-model sensitivity, how far the field reaches, and the
field at any point you choose.

A field map is one slice cut across the line. **z** is the distance along the line from mid-span,
where the wires hang lowest and the field near the ground is highest; the towers are at plus and
minus half the span, where the wires are higher. The map page shows one span from the side, with
the building and the shield under it: click or drag there to move the slice. *Log scale* makes
the colours step by factors of ten, so the weak field shows as well as the strong; *True scale*
draws one metre up the same as one metre across.

Magnetic field lines can be spaced two ways. *Equal flux* puts the same flux between neighbouring
lines, so they crowd where the field is strong and hardly any reach a building some way off.
*Show weak field* spreads them so the weak field shows too; their spacing is then no longer the
strength. Electric field lines run from a wire that is positive at that instant to the ground, an
earthed shield or a wire that is negative; the same charge stands behind every line. Dotted
equipotentials, which the field crosses at right angles, show the weak field that few lines reach.

**Standards** – thirteen exposure standards and planning values, each checked at the system
frequency, with the governing case and margin. Compliance always uses the unshielded field.

**Shielding** – fourteen arrangements, solved physically for the actual geometry:

| Around the building | Between the line and the building |
|---|---|
| walls and roof (the default) | barrier wall |
| complete envelope (walls, roof, floor) | double barrier wall |
| walls only (roof left open) | mesh barrier wall |
| shielded room inside the building | passive loop, with optional series-capacitor compensation |
| perimeter wall | earthed screening wires |
| roof only, facade only, floor only | **custom layout**: plates you place by coordinates |

Where the shield sits is yours to set. Sheets round the building can be fixed to its surfaces or
stand off them (gap from the walls, height above the roof, overhang of a roof canopy, level of a
shielded floor); barriers, loops and screens are placed by distance from the line, by length and
by where they are centred along the line (one press puts them beside the building); a shielded
room by its size and position inside the building; and the custom layout takes any set of
straight plates. Taki warns if a shield comes too close to a live conductor, or does not reach
the building it is meant for.

Thirteen materials (plus your own), thickness, one to three layers, a second material, coverage,
bonded or unbonded seams, earthed or floating.

**A shield is judged on the average field inside the building it protects**, 1 m clear of the
walls, floor and roof. That one figure is what the top bar, the dashboard, the comparisons, the
twin and the report show. The highest point inside and the value at a single point just inside
the wall facing the line are given beside it: right behind a shielded wall the field can fall far
more than the building as a whole gains, and at an open edge it can rise.

**Compare options** puts every arrangement, material and thickness side by side for your site,
together with measures at the line itself (taller towers, phasing). The arrangement in use is
shown as you set it; each of the others is placed sensibly for the building (a barrier as tall as
the building, at the best of the positions tried between it and the line), so the comparison is a
fair one.

**Digital twin** – a 3-D scene of towers, sagging conductors, buildings and the shield, with the
field on the ground, on a movable vertical section, as contours, a glow and an iso-surface. Click
anywhere to read the field there, with and without the shield.

**Scenarios** – named snapshots of every input; compare them on one chart and in one table.

**Validation** – thirteen self-checks against exact solutions, comparison with a published
dataset (run on the source's own tower when it published one, and clearly marked when it is not a
like-for-like comparison), and comparison with your own field-meter survey (CSV).

**Reports** – PDF, Word and plain text, with the sections and figures you choose.

**AI narrative (optional)** – the report page can ask Claude (Anthropic), Gemini (Google) or
ChatGPT (OpenAI) to draft a narrative from the computed results. **Each person uses their own
key.** It is typed into the app, kept in that person's browser, sent with the one request that
needs it and never stored by Taki, so nobody sees or spends anyone else's. *Load my models* asks
the service which models that key can use. The narrative never decides compliance.

**Research library** – the references behind the methods, limits and material data, with what
could and could not be verified for each.

**Sharing** – *Share* makes a link that gives a colleague their own copy of a project.

**Export all, import** – every project with its scenarios in one file, from the projects page:
the backup, and the way to carry work to another copy of Taki.

---

## 4. Accounts and where the data lives

Everyone signs in (or uses a guest session). Projects, scenarios and preferences belong to the
account and are saved as you work.

* Passwords are stored only as salted scrypt hashes.
* The sign-in cookie is HttpOnly and SameSite; the database holds only a hash of it.
* Sign-in, sign-up and password-reset attempts are rate-limited.
* **Forgot password** makes a one-hour, single-use link. With email configured (section 7) it is
  emailed; without, it is printed in the window the server runs in, for you to pass on.
* `/privacy` in the app states what is stored.

Out of the box the data is kept in a file on the computer running Taki (`data/taki.db`, SQLite).
That is right for one computer. For a website, use an online database: next section.

The desktop version (section 2) has none of this: one person, no account, and a data folder of
its own.

Useful commands:

```
python run.py users                   list the accounts
python run.py reset-password EMAIL    set a new password for an account
python run.py check-db                test the database Taki is set to use
```

On Windows, double-clicking **`check-database.bat`** runs the last one and keeps the window open.

---

## 5. Use an online database (Supabase or Neon)

Taki can keep its accounts and projects in any hosted PostgreSQL database. **You do not write SQL
or install a database**: you create a free project on the provider's website, give Taki the
connection string once, and Taki creates its own tables.

### Which one

| | Supabase | Neon |
|---|---|---|
| Free plan | 500 MB, 2 projects | 1 GB per project, no card needed |
| When unused | paused after a week; press *Restore* in the dashboard | sleeps after minutes, wakes by itself on the next visit |
| Looking at the data | table editor in the dashboard | tables view in the console |

Both work the same with Taki. **Supabase** suits a site that is running all the time: Taki's own
housekeeping touches the database every few hours, which keeps it active. **Neon** is less trouble
if Taki runs only now and then (on your own computer, or on a host that sleeps when idle), because
it never needs restoring by hand. Limits are as published in mid-2026; check the provider's
pricing page.

### Steps (Supabase)

1. Go to **supabase.com**, sign up, and press **New project**. Choose a name, a region near your
   users, and a **database password**. Keep that password.
2. When the project is ready, press **Connect** at the top of the page. Under *Connection string*
   choose **Session pooler** and copy the URI. It looks like
   `postgresql://postgres.abcdefgh:[YOUR-PASSWORD]@aws-0-xx.pooler.supabase.com:5432/postgres`
3. On your computer, run the connection helper:
   * Windows: double-click **`connect-database.bat`**
   * macOS / Linux: `sh connect-database.sh` (or `python run.py setup-db`)
4. Paste the string. If it still says `[YOUR-PASSWORD]`, the helper asks for the password.

The helper tests the connection, creates the tables, offers to copy the accounts and projects you
already have on this computer, and saves the setting in a file called `.env`. It ends by saying
**CONNECTED** and waits for a key, so the window does not vanish.

### Steps (Neon)

1. Go to **neon.com**, sign up, and create a project (any name, a region near you).
2. On the project page press **Connect** and copy what the box shows. It may be the bare address
   (`postgresql://...`) or a whole command (`psql 'postgresql://...'`): paste either as it is.
3. Run the connection helper as above and paste.

### Check that it worked

* Windows: double-click **`check-database.bat`**. macOS / Linux: `sh check-database.sh`.
  It prints `Database OK (postgresql, online, Neon)` with the number of accounts and projects.
* Or start Taki: the start-up window says where accounts and projects are kept, and
  *Settings → About & limits* shows the same.

### Good to know

* Use Supabase's **Session pooler** string. The *Direct connection* string only works on IPv6
  networks; the helper tells you if you pasted that one.
* The `.env` file contains the database password. Do not publish it or send it to anyone (it is
  in `.gitignore`). If something goes wrong, the error text is enough to find the cause.
* Taki switches on row-level security for its tables, which closes them to the public REST API
  Supabase puts in front of every database. Taki itself connects as the owner and is unaffected.
* To go back to the local file: `python run.py use-local-db`. Nothing online is deleted.
* To copy a local database file into the online one later: `python run.py copy-db`.

---

## 6. Put it on the internet

Taki is one Python server, so any host that runs a Docker container or a Python process will do.
Two things matter: use an **online database** (section 5), because most hosts wipe their own disk
on every deploy, and serve it over **HTTPS**.

### Render (has a free plan)

1. Put this folder in a GitHub repository (private is fine).
2. On render.com: **New → Blueprint**, pick the repository. Render reads `render.yaml` and builds
   the `Dockerfile`.
3. It asks for two values: `DATABASE_URL` (the string from section 5) and `TAKI_PUBLIC_URL` (the
   address Render gives the site, e.g. `https://taki.onrender.com`).

On Render's free plan the site sleeps after 15 minutes without visitors and takes about a minute
to wake. A paid instance, or any other container host, removes that.

### Docker anywhere

```
docker build -t taki .
docker run -p 8000:8000 -e DATABASE_URL="postgresql://..." -e TAKI_SECURE_COOKIES=1 \
           -e TAKI_PUBLIC_URL="https://your.address" taki
```

### Your own server

```
python run.py --host 0.0.0.0 --workers 2 --no-browser
```

behind a reverse proxy (Caddy, nginx) that provides HTTPS. Set `TAKI_SECURE_COOKIES=1`,
`TAKI_PUBLIC_URL`, and `TAKI_TRUSTED_PROXIES` to the proxy's address.

### Before you publish

* `TAKI_SECURE_COOKIES=1` and `TAKI_PUBLIC_URL` are set.
* Decide whether anyone may sign up (`TAKI_ALLOW_SIGNUP`) and whether guests are allowed
  (`TAKI_ALLOW_GUESTS`).
* Set up email if you want users to reset their own passwords (section 7).
* With several workers, keep `workers × TAKI_DB_POOL` under your database plan's connection limit.

---

## 7. Settings

Everything is optional. Put settings in a file called `.env` next to `run.py` (copy
`.env.example`), or in the host's environment.

| Setting | Meaning | Default |
|---|---|---|
| `DATABASE_URL` | connection string of an online PostgreSQL database | none: local file |
| `TAKI_DB_POOL` | connections kept open to it | 5 |
| `TAKI_DATA_DIR` | folder of the local database file | `./data` |
| `TAKI_HOST`, `TAKI_PORT` | where to listen (`PORT` is honoured too) | `127.0.0.1`, `8000` |
| `TAKI_PUBLIC_URL` | the address people open, for links in emails | none |
| `TAKI_SECURE_COOKIES` | send the cookie over HTTPS only | 0 |
| `TAKI_WORKERS` | server processes | 1 |
| `TAKI_TRUSTED_PROXIES` | proxies whose forwarded address is believed | `127.0.0.1` |
| `TAKI_ALLOW_SIGNUP`, `TAKI_ALLOW_GUESTS` | new accounts / guest sessions | 1, 1 |
| `TAKI_SESSION_DAYS` | how long a sign-in lasts | 30 |
| `TAKI_SMTP_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `_FROM`, `_SECURITY` | mail server for reset links | none |
| `TAKI_ANTHROPIC_API_KEY`, `TAKI_GEMINI_API_KEY`, `TAKI_OPENAI_API_KEY` | a key of **yours** that signed-in users of this copy may use for the AI narrative, at your cost | none: each person uses their own |
| `TAKI_AI_PER_HOUR` | narratives per account per hour on such a shared key | 10 |
| `TAKI_DESKTOP_DOWNLOAD` | let visitors download the desktop version from this copy | 1 |

You do not need the AI settings. Leave them out and every person enters their own key in the
app. Only the `TAKI_` names are read, so a key that happens to be on the computer for another
program is never shared by accident; a shared key is never offered to guest sessions.

---

## 8. What is calculated, and how far to trust it

**Magnetic field** – Biot-Savart for long parallel conductors, complex-phasor sum over every
sub-conductor, RMS resultant. Earth return: none (free space), a perfect image, or the Deri
complex image for a soil resistivity.

**Electric field** – Maxwell potential coefficients with the method of images; the charge on each
conductor is solved from its voltage, radius and bundle (geometric-mean equivalent radius).

**Circuits** – every circuit carries its own balanced three-phase currents and voltages. One taken
out of service has no current and sits at earth potential; its conductors stay in the
electric-field solution, where earthed wires beside live ones raise the field a little close to
the line and lower it further out. The current the live circuits induce in an earthed circuit is
not modelled.

**Along the span** – conductors hang in a parabola between the towers, so the field is strongest
at mid-span, where compliance is assessed. With *Sag follows the span*, the design sag and the
thermal sag scale with (span / 300 m)², from the 300 m span the tower data is given for.

**Shields** – a boundary-element solution on the real cross-section. Sheets carry eddy currents
and magnetisation; panels bonded together share one circuit; round conductors (loops, screening
wires) carry their real resistance; a series capacitor cancels part of a loop's reactance. The
electric field treats the shield as an earthed or floating conductor. Nothing is scaled by a
percentage: every number is a solution for that geometry, which is why a shield can raise the
field beside it while lowering it inside.

**Inside a building** – the average is an area integral over the cross-section through the
building, 1 m clear of its walls, floor and roof (17 × 9 points, trapezoidal weights). Up to
version 4.1 it was a plain mean of 45 points, which counted the edges too heavily; shield
percentages therefore moved by a few points in 4.2 (a walls-only screen that read −18 % now
reads about −22 %).

**Field lines** – all the currents run along the line, so the flux density is the curl of a
potential with one component, and a field line is a line of constant potential. Taki sends the
complex potential once (with the currents induced in the shield when there is one) and the
browser draws its contours at any instant of the cycle. The lines are exact: they never cross and
never stop in mid-air. In the *Show weak field* view they are spaced to reach the buildings, so
their density is not the field strength; *Equal flux* puts the same flux between neighbours.

**Electric field lines** – the electric field is that of a line charge on every conductor with
its image in the ground, plus the charge induced on a shield when there is one. A line starts on
positive charge and ends on negative charge, so it has two ends, and the lines are traced from
the wires: the number leaving a wire is in proportion to its charge at that instant. The field
of the wires is summed exactly in the browser; the field of the charge on the shield is sent on
a grid. The dotted equipotentials are contours of the potential, on which an earthed sheet sits
at zero. Lines that would run only between the ground and an unearthed sheet are not drawn.

**Verified** (Validation page, and `python -m pytest`):

| Check | Agreement |
|---|---|
| single wire, RMS resultant, perfect-earth image, conductor potential | exact |
| shield vs exact infinite slab: aluminium, steel, magnetic sheet | within 2 % |
| a custom layout vs the same shape as a built-in arrangement | identical |
| closed shell vs thin-cylinder formulas: conducting, magnetic | within 0.1 % |
| passive loop current vs circuit theory, with and without a series capacitor | within 1 % |
| field-line potential: its curl against the solved field, conducting and magnetic sheets | within 0.001 % |
| the four-circuit tower against the geometry and currents its source published | within 0.001 µT |
| magnetic field vs the original Taki solver, at 100 % load | identical |

**Not verified, or outside the model:**

* It is a 2-D cross-section. Angle towers, terminations, line crossings and the end walls of a
  shield are not modelled. For a compact enclosure this makes the shield result an upper estimate.
* Shield results assume ideal construction unless you say otherwise: use the coverage and
  unbonded-seam settings to represent doors, windows and joints. Unbonded seams can take a room
  from over 95 % reduction to under 40 %.
* The complex-image earth model has not been compared with measurements here.
* Tower presets and currents are representative, not as-built.
* The shield solver is verified against exact solutions (the table above). It has **not** been
  compared with measurements in a building that was actually shielded.
* The comparison with published data covers one source (Fikry et al. 2022), which is itself a
  simulation. It published tower geometry for two of its five towers; only those can be compared
  like for like, and Taki reads √2 times that source, uniformly (a peak / RMS convention).
* The ground-clearance figure is an indicative rule (5.6 m plus 10 mm per kV to earth above
  22 kV). The line owner's own clearances govern.
* The Malaysian entry in the standards list carries ICNIRP 1998 values and is flagged *verify*:
  the document number used by earlier versions could not be confirmed.
* The AI narrative was built without a real key for any of the three services. The requests
  follow each service's published format and are tested against replies recorded in that format.
  From the development machine only Anthropic's service could be reached, and only as far as a
  rejected dummy key; Google's and OpenAI's could not be reached at all. Model names change
  often: if a default has been withdrawn, *Load my models* lists the ones your key can use.
* The Docker image was not built on the development machine (no registry access); the same
  steps were checked through a clean `start.sh` install.

---

## 9. What changed

### In version 4.3

* **Desktop version**: Taki as a program on one computer, with its own window, no sign-in and no
  internet once installed (section 2). The web version hands it out as a download.
* **Install from the browser**: the web version can be installed as an app from Chrome, Edge or
  Safari.
* **Export all, import**: every project with its scenarios in one file.
* The built interface is now kept by the browser between visits, so pages open faster.
* No calculated number changed.

### In version 4.2.1

* **Electric field lines** on the *Field lines* page, with equipotentials, without and with the
  shield, played through the cycle.
* **Where the slice is cut**: the field map shows one span from the side and the cross-section
  can be moved anywhere along it.
* Two drawing mistakes put right: arrowheads on the magnetic field lines sat between the lines,
  and on a field map away from mid-span the wire dots stayed at their mid-span height. The fields
  themselves were right in both cases.

### In version 4.2

* **Circuits one by one** on multi-circuit towers (voltage, current, loading, phase order, in or
  out of service), and a 275/132 kV four-circuit tower.
* **Sag follows the span** switch; the lowest conductor and an indicative ground clearance.
* **One figure for a shield everywhere**: the average inside the building. The averaging itself
  was corrected (section 8), so percentages differ from 4.1 by a few points.
* **Fair comparisons**: each arrangement is placed for the building instead of inheriting the
  last settings; free-standing shields can be moved along the line.
* **Field lines** drawn from the vector potential and animated in the browser.
* **Field map**: a colour scale that spans the picture, so a shielded space shows up; a
  *True scale* switch; hover text that can be read on any colour.
* **Top bar** says where each peak is and what the shield figure refers to, and never cuts a
  read-out off.
* **AI narrative** with Claude, Gemini or ChatGPT, each person with their own key.
* **Report**: no with-shield columns when there is no shield, each reference listed once, tables
  kept whole on a page, numbers kept with their units, clearer field maps.
* **Database**: `check-database`, a pasted `psql '...'` line is understood, and databases created
  without an encoding work.

### From the earlier Streamlit versions

Everything the Streamlit app did is still here. These results differ, on purpose (the app shows
before-and-after numbers for your own project under *Settings → What changed*):

| | Before | Now |
|---|---|---|
| **Loading** | changed only the sag; current stayed at 100 % | operating current = rated × loading |
| **Electric field** | every conductor solved as a 15 mm wire, bundles ignored | each tower's own radius and bundle; about 40–60 % higher on the presets |
| **Shield** | infinite-sheet formula applied behind the shield | finite shield solved on its geometry; much lower, realistic magnetic reductions |
| **Shield placement** | a wall between line and building | around the building first; fourteen arrangements, each placed freely |
| **Standards** | some entries merged or unverifiable; 50 Hz limits at 60 Hz | re-checked, split, frequency-dependent; margin uses the tighter of B and E |
| **Along the span** | mid-span section extruded | conductor height varies along the span |
| **Receptors** | sampled on the facade | 1 m inside, plus the average and worst point over the interior |

At 100 % loading with no shield the magnetic field is identical to the original, and scenario
files saved by the Streamlit versions still import.

---

## 10. Project layout

```
run.py                  start the server; housekeeping commands
start.bat / start.sh    one-step start (sets up .venv on first run)
connect-database.*      connect an online database
check-database.*        confirm which database is in use and that it answers
requirements.txt        Python packages
.env.example            every setting, commented
Dockerfile, render.yaml container image and Render blueprint

desktop.py              the desktop version: what its icon runs
install-desktop.bat     its installer for Windows (fetches Python, then runs tools/desktop_setup.py)
start-desktop.sh        the desktop version on macOS and Linux
requirements-desktop.txt  what it needs (no database driver)
requirements-desktop.lock the exact versions it installs, with their hashes

engine/                 the physics; no web code
  physics.py earth.py     line fields and earth models
  lines.py site.py        towers, circuits, loading, sag; a resolved project with cached solutions
  shield_engine.py        materials, arrangements, geometry
  shield_bem.py           the boundary-element shield solver
  field_lines.py          the vector potential whose contours are the magnetic field lines;
                          charges and potential for the electric ones
  standards.py            exposure standards
  validation.py benchmarks.py   self-checks, datasets, error metrics
  report.py report_figures.py   PDF / Word / text writers and their figures
  ai_report.py            the optional narrative: Claude, Gemini or ChatGPT
  references.py libraries.py    bibliography, building and soil data

server/                 the web server
  main.py                 the API (FastAPI) and the built site
  service.py              what each page asks for, as JSON
  twin_service.py report_service.py validation_service.py
  auth.py db.py mailer.py accounts, storage (SQLite or PostgreSQL), email
  manage.py               the commands behind run.py
  desktop.py              the desktop version: launcher, window, when to stop
  desktop_package.py      the desktop download, built from the files this copy runs on
  static/                 the built web interface

tools/
  desktop_setup.py        what the Windows installer does once it has a Python: copy, install,
                          check, shortcuts; and the uninstaller
  make_lock.py            writes requirements-desktop.lock
  make_icons.py           draws the icons from the logo
  wheels/                 pip itself, carried along for the installer

web/                    source of the interface (React, TypeScript, three.js, Plotly)
tests/                  about 230 tests: physics, circuits, standards, shields, pages, reports,
                        the AI requests (no network), accounts, database, the desktop version
```

---

## 11. Working on the code

```
pip install -r requirements-dev.txt
python -m pytest                          under a minute
```

The tests never read your `.env`, your `data` folder or a database address in the environment,
so they cannot touch a real installation.

The account and database tests also run against PostgreSQL when a scratch database is named
(every table in it is dropped first):

```
TAKI_TEST_DATABASE_URL=postgresql://user@127.0.0.1:5432/taki_test python -m pytest
```

The interface is rebuilt with Node 20 or newer:

```
cd web
npm install
npm run build        writes server/static
npm run dev          live reload on :5173, with the API on :8000
```

`http://localhost:8000/api/docs` lists every API route.

**The desktop version.** `python run.py desktop --window none` starts it without a window and
prints its address; `--data-dir` keeps its data away from yours. After changing
`requirements-desktop.txt`, or to move to newer libraries, run `python tools/make_lock.py`
(`pip install uv` first), install the new lock file into a fresh environment and run the tests
there before handing it on. The installer's batch file cannot be run where there is no Windows.
The tests check it for the mistakes that usually break one (line ends, jumps without a label,
unquoted paths) and walk it through every situation it has to cope with, using a small stand-in
for `cmd.exe` (`tests/batch_sim.py`) and folder names with spaces, brackets and ampersands in
them. Everything it hands over to is Python and is tested as such. The icons are redrawn with
`python tools/make_icons.py` (`pip install pillow`) only if the logo changes.
