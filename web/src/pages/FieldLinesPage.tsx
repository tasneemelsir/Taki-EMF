import { useEffect, useMemo, useRef, useState } from 'react';
import { Pause, Play } from 'lucide-react';
import { Plot } from '@/components/Plot';
import { Busy, Button, ErrorNote, Note, PageHead, Segmented, Switch } from '@/components/ui';
import { electricLinesFigure, fieldLinesFigure, potentialAt, type PotentialGrid } from '@/lib/charts';
import { b64f32, linspace } from '@/lib/decode';
import { traceElectric, type EGrid, type ESource } from '@/lib/elines';
import { useElementSize, useRemote } from '@/lib/hooks';
import { useStore } from '@/lib/store';
import { Loading, useDeco } from './common';

interface FL {
  z: number; x0: number; x1: number; y0: number; y1: number; nx: number; ny: number; scale: number; softness?: number;
  a0_re: string; a0_im: string; aS_re: string | null; aS_im: string | null; shield_included: boolean; has_current: boolean;
}
// the electric counterpart: charges on the wires, the potential, and the field of the charge on the shield
interface EL {
  z: number; x0: number; x1: number; y0: number; y1: number; nx: number; ny: number; scale: number; softness: number;
  conductors: { x: number; y: number }[]; lam0: number[][]; lamS: number[][] | null; lam_ref: number;
  v0_re: string; v0_im: string; vS_re: string | null; vS_im: string | null;
  exS_re: string | null; exS_im: string | null; eyS_re: string | null; eyS_im: string | null;
  walls: number[][]; wires: number[][]; shield_included: boolean; has_voltage: boolean;
}
type Show = 'with' | 'without' | 'both';
type Quantity = 'B' | 'E';

export default function FieldLinesPage() {
  const sol = useStore((s) => s.sol);
  const [q, setQ] = useState<Quantity>('B');
  const [phase, setPhase] = useState(0);
  const [show, setShow] = useState<Show>('with');
  const [even, setEven] = useState(true);
  const [equi, setEqui] = useState(true);
  const [linesB, setLinesB] = useState(14);
  const [linesE, setLinesE] = useState(20);        // most electric lines run from wire to wire, so more are needed to see the rest
  const [playing, setPlaying] = useState(false);
  // one request gives the complex potential; every instant of the cycle is then drawn here
  const fl = useRemote<FL>('/fieldlines', {}, { delay: 150, enabled: q === 'B' });
  const el = useRemote<EL>('/efieldlines', {}, { delay: 150, enabled: q === 'E' });
  const d = fl.data, e = el.data;
  const active = q === 'B' ? d : e;
  const lines = q === 'B' ? linesB : linesE, setLines = q === 'B' ? setLinesB : setLinesE;

  const grids = useMemo(() => {
    if (!d) return null;
    const base = { x: linspace(d.x0, d.x1, d.nx), y: linspace(d.y0, d.y1, d.ny), nx: d.nx, ny: d.ny };
    const g0: PotentialGrid = { ...base, re: b64f32(d.a0_re), im: b64f32(d.a0_im) };
    const gS: PotentialGrid | null = d.aS_re && d.aS_im ? { ...base, re: b64f32(d.aS_re), im: b64f32(d.aS_im) } : null;
    return { g0, gS };
  }, [d]);
  const electric = useMemo(() => {
    if (!e) return null;
    const base = { x: linspace(e.x0, e.x1, e.nx), y: linspace(e.y0, e.y1, e.ny), nx: e.nx, ny: e.ny };
    const v0: PotentialGrid = { ...base, re: b64f32(e.v0_re), im: b64f32(e.v0_im) };
    const s0: ESource = { conds: e.conductors, lam: e.lam0, grid: null, walls: [], wires: [] };
    let vS: PotentialGrid | null = null, sS: ESource | null = null;
    if (e.lamS && e.vS_re && e.vS_im && e.exS_re && e.exS_im && e.eyS_re && e.eyS_im) {
      vS = { ...base, re: b64f32(e.vS_re), im: b64f32(e.vS_im) };
      const grid: EGrid = { x0: e.x0, x1: e.x1, y0: e.y0, y1: e.y1, nx: e.nx, ny: e.ny,
        exr: b64f32(e.exS_re), exi: b64f32(e.exS_im), eyr: b64f32(e.eyS_re), eyi: b64f32(e.eyS_im) };
      sS = { conds: e.conductors, lam: e.lamS, grid, walls: e.walls, wires: e.wires };
    }
    return { base, v0, s0, vS, sS };
  }, [e]);

  const hasShield = q === 'B' ? !!grids?.gS : !!electric?.sS;
  const z = active?.z ?? 0;
  const view: Show = hasShield ? show : 'without';
  const deco = useDeco({ z, shield: view !== 'without' });
  const timer = useRef<number>();
  useEffect(() => {
    if (!playing) return;
    timer.current = window.setInterval(() => setPhase((p) => (p + 6) % 360), 90);
    return () => window.clearInterval(timer.current);
  }, [playing]);

  const fig = useMemo(() => {
    if (!sol) return null;
    if (q === 'B') {
      if (!grids || !d || !(d.scale > 0)) return null;
      const main = view === 'without' ? grids.g0 : grids.gS!;
      return fieldLinesFigure(main, {
        z: potentialAt(main, phase, d.scale, even, d.softness), ref: view === 'both' ? potentialAt(grids.g0, phase, d.scale, even, d.softness) : null,
        even, scale: d.scale, lines, deco, yMax: sol.domain.y_max,
      });
    }
    if (!electric || !e || !e.has_voltage) return null;
    const box = { x0: e.x0, x1: e.x1, y1: sol.domain.y_max };
    const src = view === 'without' ? electric.s0 : electric.sS!;
    const pot = view === 'without' ? electric.v0 : electric.vS!;
    return electricLinesFigure(electric.base, {
      lines: traceElectric(src, phase, lines, e.lam_ref, box),
      ref: view === 'both' ? traceElectric(electric.s0, phase, lines, e.lam_ref, box) : null,
      eq: equi ? potentialAt(pot, phase, e.scale, true, e.softness) : null, eqLines: 10, deco, yMax: sol.domain.y_max,
    });
  }, [q, grids, d, electric, e, sol, view, phase, even, equi, lines, deco]);

  // the picture is to scale, so its height follows from its width
  const [card, cardSize] = useElementSize<HTMLDivElement>();
  const legend = q === 'E' || view === 'both' ? 18 : 0;      // the key sits above the picture and must not squeeze it
  const height = active && cardSize.w > 0 ? Math.round(Math.min(660, Math.max(300, ((cardSize.w - 68) * (sol?.domain.y_max ?? 40)) / (active.x1 - active.x0) + 64 + legend))) : 460;
  if (!sol) return <div className="page"><Loading /></div>;
  const physical = sol.shield.on && (sol.shield.model === 'physical' || sol.shield.is_wire);
  const nothing = q === 'B' ? (d && !(d.scale > 0)) : (e && !e.has_voltage);

  return (
    <div className="page wide">
      <PageHead title="Field lines" lede="The lines of the magnetic or the electric field at one instant of the AC cycle, with arrows for its direction. A three-phase field turns as the currents and voltages rise and fall: play the cycle to watch it. This is a picture of direction; the RMS magnitude used for compliance is on the other pages." />
      <ErrorNote error={q === 'B' ? fl.error : el.error} />
      <div className="row gap-8 mb-12" style={{ flexWrap: 'wrap' }}>
        <Segmented value={q} onChange={setQ} options={[
          { value: 'B', label: 'Magnetic B', title: 'Lines of the magnetic field, which the currents set up' },
          { value: 'E', label: 'Electric E', title: 'Lines of the electric field, which the voltages set up' }]} />
      </div>
      <div className="plot-card" style={{ position: 'relative' }} ref={card}>
        <Busy on={q === 'B' ? fl.loading : el.loading} />
        <div className="head">
          <h3>{q === 'B' ? 'Magnetic field lines' : 'Electric field lines'}</h3>
          <span className="sub">ωt = {phase}°{z ? ` · section through the shield, z = ${z} m` : ' · mid-span'}{view !== 'without' ? (q === 'B' ? ' · shield currents included' : ' · charge on the shield included') : ''}</span>
          <div className="tools" style={{ flexWrap: 'wrap', rowGap: 6 }}>
            {hasShield && <Segmented size="sm" value={view} onChange={setShow} options={[{ value: 'without', label: 'No shield' }, { value: 'with', label: 'With shield' }, { value: 'both', label: 'Both' }]} />}
            {q === 'B'
              ? <Segmented size="sm" value={even ? 'even' : 'flux'} onChange={(v) => setEven(v === 'even')} options={[
                { value: 'even', label: 'Show weak field', title: 'Lines are spaced so the weak field far from the line shows too. Their density is not the field strength.' },
                { value: 'flux', label: 'Equal flux', title: 'The same flux between neighbouring lines, so lines are closer where the field is stronger.' }]} />
              : <Switch checked={equi} onChange={setEqui} label="Equipotentials" title="Dotted lines of equal voltage. The field crosses them at right angles. They are spaced to show the weak field far from the line, where few field lines reach." />}
            <label className="row gap-4 tiny muted" title={q === 'B' ? 'How many lines are drawn' : 'How many lines leave the most highly charged wire at its peak'}>Lines<input type="range" min={6} max={30} step={1} value={lines} onChange={(ev) => setLines(Number(ev.target.value))} style={{ width: 80 }} aria-label="Number of lines" /></label>
            <Button size="sm" icon onClick={() => setPlaying((p) => !p)} aria-label={playing ? 'Pause' : 'Play through the cycle'} title={playing ? 'Pause' : 'Play through the cycle'}>{playing ? <Pause size={13} /> : <Play size={13} />}</Button>
            <input type="range" min={0} max={354} step={6} value={phase} onChange={(ev) => { setPlaying(false); setPhase(Number(ev.target.value)); }} style={{ width: 170 }} aria-label="Instant in the cycle" />
          </div>
        </div>
        {fig ? <Plot data={fig.data} layout={fig.layout} height={height} filename={q === 'B' ? 'taki-field-lines' : 'taki-electric-field-lines'} />
          : nothing ? <div className="empty small">{q === 'B' ? 'No current flows, so there is no magnetic field to draw.' : 'No circuit is energised, so there is no electric field to draw.'}</div>
            : <Loading label="Working out the field…" />}
      </div>
      {q === 'B' ? (
        <div className="grid c2 mt-8">
          <Note kind="info">
            <b>How to read it.</b> Each line follows the magnetic field; it never crosses another and always closes on itself. {even
              ? 'In this view the lines are spread out so you can also see the weak field near the buildings, so do not read the spacing as strength.'
              : 'In this view the same flux passes between any two neighbouring lines: where they crowd, the field is strong.'} The picture is drawn to scale.
          </Note>
          <Note kind="info">
            <b>Around a shield.</b> {physical
              ? 'Lines bend because of the currents the line induces in the sheet. On a steel sheet some lines end and start again further along: that flux is travelling inside the steel.'
              : sol.shield.on ? 'Field lines bend around the shield only with the physical model, which solves the currents induced in it. The analytical and empirical models scale the magnitude and carry no direction.'
                : 'Switch a shield on to see how its induced currents bend the lines away from the building.'}
          </Note>
        </div>
      ) : (
        <div className="grid c2 mt-8">
          <Note kind="info">
            <b>How to read it.</b> Each line follows the electric field from a wire that is positive at this instant to the ground, to an earthed shield, or to a wire that is negative. The same charge stands behind every line, so they crowd where the field is strong and few reach a building far from the line. The dotted lines are equipotentials, lines of equal voltage: the field always crosses them at right angles, and they are spaced to show the weak field too. The picture is drawn to scale.
          </Note>
          <Note kind="info">
            <b>Around a shield.</b> {physical
              ? 'An earthed sheet is at the voltage of the ground, so the field lines that reach it end on it and the equipotentials lift over it. Behind a sheet, and above all inside a closed earthed envelope, very little electric field is left. That is why the electric field is far easier to shield than the magnetic field.'
              : sol.shield.on ? 'Field lines end on the shield only with the physical model, which solves the charge induced on it. The analytical and empirical models scale the magnitude and carry no direction.'
                : 'Switch a shield on to see the field lines end on it and the equipotentials lift over it.'}
          </Note>
        </div>
      )}
    </div>
  );
}
