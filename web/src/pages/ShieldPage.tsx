import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Check, Shield as ShieldIcon, Wand2 } from 'lucide-react';
import { Plot } from '@/components/Plot';
import { Accordion, Busy, Button, Card, ErrorNote, Field, Kv, Metric, Note, NumberInput, PageHead, Pill, Segmented, Select, Switch } from '@/components/ui';
import { barFigure, fieldMapFigure, profileFigure } from '@/lib/charts';
import { change, dB, fmt, sci } from '@/lib/format';
import { useRemote } from '@/lib/hooks';
import { useStore } from '@/lib/store';
import type { GridOut, SweepRow } from '@/lib/types';
import { Loading, ReceptorTable, useDeco, useDecodedGrid } from './common';

interface Models { receptor: string; basis: 'inside' | 'point'; probe: string; point: number[]; rows: SweepRow[] }
interface Assist { receptor: string; basis: 'inside' | 'point'; probe: string; point: number[]; b0: number; target: number; attached: boolean; current_height: number; los_height: number | null; status: string; thickness_mm?: number | null; height_m?: number | null; best_material?: { id: string; label: string; bS: number } | null; current: SweepRow }

function ZoneMetric({ label, v0, vS, unit, sub }: { label: string; v0: number; vS: number; unit: string; sub: string }) {
  const red = v0 > 0 ? 100 * (1 - vS / v0) : 0;
  return (
    <Metric rule tone={red >= 0.5 ? 'accent' : red <= -0.5 ? 'bad' : ''} label={label} value={vS < v0 * 1e-3 ? '≈ 0' : fmt(vS)} unit={unit}
            sub={<>{change(red)} · was {fmt(v0)} {unit} · {sub}</>} />
  );
}

export default function ShieldPage() {
  const sol = useStore((s) => s.sol);
  const config = useStore((s) => s.config)!;
  const lib = useStore((s) => s.library);
  const setConfig = useStore((s) => s.setConfig);
  const setInspector = useStore((s) => s.setInspector);
  const [q, setQ] = useState<'B' | 'E'>('B');
  const [view, setView] = useState<'without' | 'with' | 'diff'>('with');
  const [target, setTarget] = useState<number | null>(null);
  const receptor = Math.min(config.shield.target_building, Math.max(0, config.buildings.length - 1));
  const z = sol?.shield.zc ?? 0;
  const grid = useRemote<GridOut>('/grid', { z }, { enabled: !!sol?.shield.on });
  const g = useDecodedGrid(grid.data);
  const wire = !!sol?.shield.is_wire;
  const models = useRemote<Models>('/shield/models', { receptor }, { enabled: !!sol && !wire });
  const assist = useRemote<Assist>('/shield/assistant', { receptor, target_b: target }, { enabled: !!sol && !wire, delay: 350 });
  const deco = useDeco({ z });
  const mapFig = useMemo(() => {
    if (!g || !sol) return null;
    return fieldMapFigure({ x: g.x, y: g.y, z0: q === 'B' ? g.b0 : g.e0, zS: q === 'B' ? g.bS : g.eS }, { quantity: q, view, log: true, deco: { ...deco, walls: view === 'without' ? null : deco.walls, refPoint: sol.shield.ref_point } });
  }, [g, q, view, deco, sol]);
  const profFig = useMemo(() => (sol ? profileFigure(sol, { shield: true }) : null), [sol]);
  const modelFig = useMemo(() => {
    const rows = models.data?.rows.filter((r) => r.available !== false);
    if (!rows?.length) return null;
    return barFigure(rows.map((r) => r.label.split(' (')[0]), rows.map((r) => r.bS), { ytitle: models.data?.basis === 'inside' ? 'B inside, average (µT)' : 'B at the point (µT)', baseline: rows[0].b0, baselineLabel: `unshielded ${fmt(rows[0].b0)} µT`, unit: 'µT' });
  }, [models.data]);
  if (!sol) return <div className="page"><Loading /></div>;
  const shd = sol.shield, an = shd.analytical, sh = config.shield;
  const physical = shd.model === 'physical' || wire;
  const a = assist.data;
  const zone = shd.protected;
  const closed = ['enclosure', 'envelope', 'room'].includes(shd.preset);
  const ideal = closed && shd.coverage_pct >= 99.5 && shd.bonded && !shd.mesh && physical;

  return (
    <div className="page">
      <PageHead title="Shield design" lede="Design the shield around the building and see what it does inside it, where it helps, and how sure the number is. Nothing here changes the compliance result, which always uses the unshielded field.">
        <Switch checked={sh.enabled} onChange={(v) => setConfig((c) => { c.shield.enabled = v; })} label={sh.enabled ? 'Shield on' : 'Shield off'} />
        <Button size="sm" onClick={() => setInspector(true, 'shield')}><ShieldIcon size={13} />Edit shield</Button>
      </PageHead>

      {!sh.enabled && <Note kind="info" className="mb-12">The shield is switched off. Turn it on to see its effect; the comparisons below already use your current design.</Note>}
      {shd.no_geometry && <Note kind="bad" className="mb-12">This arrangement goes on a building, and there is no building. Add one on the Site tab.</Note>}

      {shd.on && (
        <>
          <div className="row wrap gap-4 mb-12 small">
            <Pill tone="teal">{shd.label}</Pill>
            {wire ? <><Pill>{shd.material.label.split(' (')[0]} conductor</Pill><Pill>{shd.wire_mm2} mm² · ⌀ {fmt(2 * shd.wire_radius_mm, 3)} mm</Pill><Pill>{shd.wires.length} conductors</Pill></>
                  : <><Pill>{shd.material.label}</Pill><Pill>{shd.thickness_mm} mm × {shd.layers}</Pill><Pill>coverage {shd.coverage_pct}%</Pill></>}
            <Pill>{shd.grounded ? 'earthed' : 'unearthed'}</Pill><Pill>{shd.bonded ? (wire ? 'closed loop' : 'bonded seams') : (wire ? 'open (no loop)' : 'unbonded seams')}</Pill>
            <Pill tone="blue">{wire ? 'Physical model' : shd.model_label}</Pill>
          </div>

          {zone && (
            <Card className="mb-12 card-top" title={<>Inside {zone.label}</>} sub="average and worst point over the protected space, 1 m clear of the walls">
              <div className="grid c4">
                <ZoneMetric label="B · average" v0={zone.b.avg0} vS={zone.b.avgS} unit="µT" sub="magnetic" />
                <ZoneMetric label="B · worst point" v0={zone.b.max0} vS={zone.b.maxS} unit="µT" sub="magnetic" />
                <ZoneMetric label="E · average" v0={zone.e.avg0} vS={zone.e.avgS} unit="kV/m" sub="electric" />
                <ZoneMetric label="E · worst point" v0={zone.e.max0} vS={zone.e.maxS} unit="kV/m" sub="electric" />
              </div>
              {ideal && <Note className="mt-8">These figures are for an ideal shell: continuous sheet, every seam bonded, no doors, windows or service openings. Treat them as the ceiling. Set a realistic <b>coverage</b> and seam condition in the inputs to see what openings cost; in practice they decide the result.</Note>}
              {zone.b.maxS > zone.b.max0 * 1.05 && <Note className="mt-8">The worst point is higher than without the shield. A sheet concentrates the field at its open edges and corners; here that is inside the protected space. Closing the open side (floor or roof) removes it.</Note>}
              {shd.probe && Math.abs(shd.probe.b_red_pct - zone.b.reduction_pct) > 15 && (
                <Note kind="info" className="mt-8">
                  <b>Why the average, and not one point.</b> {shd.room ? 'At the centre of the room' : '1 m inside the wall facing the line'} the magnetic field goes from {fmt(shd.probe.b0)} to {fmt(shd.probe.bS)} µT ({change(shd.probe.b_red_pct)}), while the average over the whole space changes by {change(zone.b.reduction_pct)}. Right behind a shielded wall the field drops sharply; further in, and near the open edges, it does not. The average is what the people or equipment inside get, so it is the figure Taki puts first everywhere.
                </Note>
              )}
            </Card>
          )}

          <div className="grid c4 mb-12">
            <Metric rule tone={sol.peak_b_shield > sol.peak_b * 1.05 ? 'warn' : ''} label="Peak B on the profile" value={fmt(sol.peak_b_shield)} unit="µT"
                    sub={sol.peak_b_shield > sol.peak_b * 1.05 ? `was ${fmt(sol.peak_b)} µT · higher at the shield's edge` : `was ${fmt(sol.peak_b)} µT`}
                    title="Highest B on the lateral profile with the shield in place. A conducting sheet concentrates the field at its edges, so the profile can peak right beside it." />
            {wire
              ? <Metric rule label="Induced loop current" value={fmt(shd.loop_current_a ?? 0)} unit="A" sub={shd.compensation_pct > 0 ? `${shd.compensation_pct}% series-compensated` : 'no compensation'} />
              : <Metric rule label="Skin depth" value={shd.skin_depth_mm ? fmt(shd.skin_depth_mm) : '—'} unit="mm" sub={`sheet is ${fmt(shd.thickness_mm)} mm${shd.layer2 ? ` · 2nd layer ${shd.layer2.split(' (')[0]}` : ''}`} />}
            {physical && shd.floating_kv
              ? <Metric rule tone="warn" label="Induced voltage" value={fmt(shd.floating_kv)} unit="kV" sub="unearthed · touch hazard" />
              : <Metric rule label={physical ? 'Current to earth' : 'Leakage ceiling'} value={physical ? fmt((shd.earth_ma_per_m ?? 0) * (2 * shd.zh)) : an.ceiling.toFixed(0)} unit={physical ? 'mA' : 'dB'} sub={physical ? 'capacitive, whole shield' : `B: ${an.limited_by_b} · E: ${an.limited_by_e}`} />}
            <Metric rule label="Losses in the shield" value={physical ? sci((shd.loss_w_per_m ?? 0) * (2 * shd.zh)) : '—'} unit="W" sub={shd.is_wire ? 'resistive heating, whole length' : 'eddy-current heating, whole length'} />
          </div>
        </>
      )}

      {!wire && (
        <Card title="The same shield under each model" sub={models.data ? `${models.data.basis === 'inside' ? 'average ' : ''}${models.data.receptor}` : ''} className="mb-12">
          <ErrorNote error={models.error} />
          <div className="grid split" style={{ position: 'relative' }}>
            <Busy on={models.loading} />
            <div className="table-wrap">
              <table className="tbl">
                <thead><tr><th>Model</th><th className="num">B (µT)</th><th className="num">B change</th><th className="num">E (kV/m)</th><th className="num">E change</th></tr></thead>
                <tbody>
                  {models.data?.rows.map((r) => (
                    <tr key={r.model} className={r.model === shd.model ? 'sel' : undefined}>
                      <td>{r.label}{r.model === shd.model && <> <Pill tone="blue">in use</Pill></>}{r.available === false && <div className="tiny muted">no entry for this material; shows the analytical value</div>}</td>
                      <td className="num">{r.bS < r.b0 * 1e-3 ? '≈ 0' : fmt(r.bS)}</td><td className={`num ${r.b_red_pct >= 0 ? 'good' : 'bad'}`}>{change(r.b_red_pct, 1)}</td>
                      <td className="num">{r.eS < r.e0 * 1e-3 ? '≈ 0' : fmt(r.eS)}</td><td className={`num ${r.e_red_pct >= 0 ? 'good' : 'bad'}`}>{change(r.e_red_pct, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>{modelFig ? <Plot data={modelFig.data} layout={modelFig.layout} height={210} toolbar={false} /> : <Loading />}</div>
          </div>
          <Note kind="info" className="mt-8">
            <b>How to read this.</b> The physical model solves this shield as built: the eddy currents in it, flux shunting in magnetic materials, and the field that gets round its edges and through its gaps. {(() => {
              const ph = models.data?.rows.find((r) => r.model === 'physical'), an2 = models.data?.rows.find((r) => r.model === 'analytical');
              if (!ph || !an2) return null;
              if (Math.abs(an2.b_red_pct) < 0.5 && Math.abs(ph.b_red_pct) >= 0.5)
                return <>The analytical model applies the infinite-sheet attenuation ({(an2.sheet_se_b ?? 0).toFixed(0)} dB for this sheet) only where the shield blocks the line of sight to the conductors. {models.data?.basis === 'inside' ? 'Most of the building' : 'This point'} still sees them, so that model credits nothing here, while the solved currents change B by {change(ph.b_red_pct, 0)}. </>;
              if (an2.b_red_pct > ph.b_red_pct + 5)
                return <>The analytical model is the infinite-sheet formula applied in the shield's shadow; for the 50/60 Hz magnetic field it is an upper bound ({change(an2.b_red_pct, 0)} here against {change(ph.b_red_pct, 0)} solved), because a real shield is finite and its currents must close within it. </>;
              const lo = Math.min(an2.bS, ph.bS), hi = Math.max(an2.bS, ph.bS);
              return <>Here the two give much the same reduction ({change(an2.b_red_pct, 1)} analytical, {change(ph.b_red_pct, 1)} solved){lo > 0 && hi / lo > 1.5 ? <>, though the little that is left differs: {fmt(an2.bS)} against {fmt(ph.bS)} µT</> : null}. </>;
            })()}The empirical model is the literature percentage Taki started with. Use the physical result for design.
          </Note>
        </Card>
      )}

      {shd.on && (
        <div className="grid c2 mb-12">
          <div className="plot-card" style={{ position: 'relative' }}>
            <Busy on={grid.loading} />
            <div className="head"><h3>Where the shield helps</h3><span className="sub">section through the shield, z = {z} m</span>
              <div className="tools">
                <Segmented size="sm" value={q} onChange={setQ} options={[{ value: 'B', label: 'B' }, { value: 'E', label: 'E' }]} />
                <Segmented size="sm" value={view} onChange={setView} options={[{ value: 'without', label: 'Without' }, { value: 'with', label: 'With' }, { value: 'diff', label: 'Difference' }]} />
              </div>
            </div>
            {mapFig ? <Plot data={mapFig.data} layout={mapFig.layout} height={360} filename="taki-shield-map" /> : <Loading />}
          </div>
          <div className="plot-card">
            <div className="head"><h3>Profile with and without</h3><span className="sub">{sol.corridor.meas_height} m above ground</span></div>
            {profFig && <Plot data={profFig.data} layout={profFig.layout} height={360} filename="taki-shield-profile" />}
          </div>
        </div>
      )}

      <div className="grid split mb-12">
        <Card title="Every building" sub="the average over the inside, and one probe point 1 m inside the wall facing the line">
          <ReceptorTable rows={sol.receptors} />
          <p className="small muted mt-8">A shield acts on the building it is built around. One further along the line, outside its length, is not protected by it.</p>
        </Card>
        {wire ? (
          <Card title="Conductor measures" sub="what to expect">
            <ul className="small" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.65 }}>
              {shd.preset === 'passive-loop' ? <>
                <li>The loop carries {fmt(shd.loop_current_a ?? 0)} A, induced by the line. Nothing is connected to it.</li>
                <li>Published schemes put the loop under the phase conductors and a little wider than the line. “Place it under the line” in the inputs does that.</li>
                <li>Series compensation raises the loop current and the reduction further out, and raises the field directly under the line. Look at the whole profile, not one point.</li>
                <li>The loop is solved as a closed circuit along the modelled length; the short end connections are not modelled.</li>
              </> : <>
                <li>Earthed wires end the electric field lines above the building, so the field underneath falls sharply.</li>
                <li>They carry almost no current, so the magnetic field is practically unchanged.</li>
                <li>More wires, closer together and higher above the roof, screen better.</li>
              </>}
            </ul>
          </Card>
        ) : (
          <Card title={<span className="row gap-4"><Wand2 size={14} />Design assistant</span>} sub={a ? `for ${a.receptor}` : ''}>
            <ErrorNote error={assist.error} />
            <Field label={a?.basis === 'point' ? 'Target B at the point' : 'Target for the average B inside'} help={a ? `Without a shield: ${fmt(a.b0)} µT. Current design: ${fmt(a.current.bS)} µT.` : undefined}>
              <NumberInput value={target ?? a?.target ?? 0} onChange={setTarget} min={0.001} max={2000} step={0.05} unit="µT" />
            </Field>
            {a && (
              <div className="mt-12 col gap-8" style={{ position: 'relative' }}>
                <Busy on={assist.loading} />
                {a.status === 'already' && <Note kind="good"><Check size={12} /> The unshielded field is already at or below the target.</Note>}
                {a.los_height !== null && (
                  <div className="row between small"><span>Height that blocks the line of sight from every circuit</span>
                    <span className="row gap-4"><b className="mono">{a.los_height.toFixed(1)} m</b>
                      <Button size="sm" onClick={() => setConfig((c) => { c.shield.height_m = Math.ceil(a.los_height!); })}>Use {Math.ceil(a.los_height)} m</Button></span></div>
                )}
                {a.status !== 'already' && <>
                  {!a.attached && <div className="row between small"><span>Lowest wall that reaches the target (current sheet)</span>
                    {a.height_m ? <span className="row gap-4"><b className="mono">{a.height_m} m</b><Button size="sm" onClick={() => setConfig((c) => { c.shield.height_m = a.height_m!; })}>Use</Button></span> : <span className="muted">none up to 50 m</span>}</div>}
                  <div className="row between small"><span>Thinnest sheet that reaches the target (current arrangement)</span>
                    {a.thickness_mm ? <span className="row gap-4"><b className="mono">{a.thickness_mm} mm</b><Button size="sm" onClick={() => setConfig((c) => { c.shield.thickness_mm = a.thickness_mm!; })}>Use</Button></span> : <span className="muted">none up to 100 mm</span>}</div>
                  {a.best_material && <div className="row between small"><span>Best library material in this arrangement</span>
                    <span className="row gap-4"><b>{a.best_material.label}</b><span className="mono muted">{fmt(a.best_material.bS)} µT</span>
                      <Button size="sm" onClick={() => setConfig((c) => { c.shield.material_id = a.best_material!.id; })}>Use</Button></span></div>}
                  {a.status === 'not_reachable' && <Note>Neither thickness nor height reaches that target here. The limit is the arrangement: close the shield round the building (walls, roof and floor), shield one room, or accept a higher target. Compare → Measures shows every option side by side.</Note>}
                </>}
                <p className="tiny muted">The target is judged on the field {a.basis === 'inside' ? `averaged ${a.receptor}` : a.receptor}. The line-of-sight height is for the probe point ({a.probe}). The search uses the {shd.model_label.split(' (')[0].toLowerCase()} model.</p>
              </div>
            )}
          </Card>
        )}
      </div>

      {!wire && (
        <div className="grid c2">
          <Card title="Material and sheet">
            <Kv k="Material" v={`${shd.material.label} · ${shd.material.quality} data`} />
            {shd.layer2 && <Kv k="Second layer" v={shd.layer2} />}
            <Kv k="Conductivity σ" v={`${sci(shd.material.sigma)} S/m`} />
            <Kv k="Relative permeability µr" v={fmt(shd.material.mu_r, 4)} />
            <Kv k="Skin depth" v={shd.skin_depth_mm ? `${fmt(shd.skin_depth_mm)} mm at ${sol.corridor.freq} Hz` : '—'} />
            <Kv k="Thickness ÷ skin depth" v={shd.skin_depth_mm ? (shd.thickness_mm / shd.skin_depth_mm).toFixed(2) : '—'} />
            {physical && shd.on && <>
              <Kv k="Largest induced sheet current" v={`${fmt(shd.max_sheet_current_a_per_m ?? 0)} A/m`} />
              <Kv k="Eddy-current loss" v={`${sci(shd.loss_w_per_m ?? 0)} W per metre`} />
              <Kv k="Boundary elements" v={String(shd.elements ?? 0)} />
            </>}
            <p className="small muted mt-8">{shd.material.mechanisms} {shd.material.limitations}</p>
            {lib && <p className="tiny muted">Material data and sources are in the Research library.</p>}
          </Card>
          <Card title="Infinite-sheet breakdown" sub="Schelkunoff A + R + B (analytical model)">
            <div className="grid c3">
              <Metric small label="Absorption A" value={an.absorption.toFixed(1)} unit="dB" />
              <Metric small label="Reflection (H)" value={an.reflection_h.toFixed(1)} unit="dB" />
              <Metric small label="Reflection (E)" value={an.reflection_e.toFixed(0)} unit="dB" />
              <Metric small label="Multi-reflection B" value={an.multi_refl.toFixed(1)} unit="dB" />
              <Metric small label="Leakage ceiling" value={an.ceiling.toFixed(0)} unit="dB" />
              <Metric small label="Sheet SE (B / E)" value={`${an.se_b.toFixed(0)} / ${an.se_e.toFixed(0)}`} unit="dB" />
            </div>
            <p className="small muted mt-8">These are properties of an infinite sheet {fmt(shd.source_distance_m, 3)} m from the line. They describe the material, not this shield: a real one lets the field round its edges and through its openings long before the sheet itself does.</p>
          </Card>
        </div>
      )}

      <div className="mt-16">
        <Accordion title="Shielding arrangements, and where each is used">
          <ul className="small" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
            <li><b>Around the building: walls and roof.</b> Sheet on the two side walls and the roof, earthed. Very good for the electric field; the open floor limits the magnetic result.</li>
            <li><b>Complete envelope.</b> Walls, roof and floor bonded into one shell. A closed shell is what makes low-frequency magnetic shielding work, because the induced currents can circulate all the way round.</li>
            <li><b>Shielded room.</b> The same closed shell round one room. The standard solution for sensitive equipment and laboratories, usually aluminium or copper with a steel layer.</li>
            <li><b>Walls only.</b> Sheet on the walls with the roof left open. Good for the electric field arriving from the side; the open top lets the magnetic field in.</li>
            <li><b>Perimeter wall, roof only, facade only, floor only.</b> Partial measures. They help on the side they cover and let the field in round the rest.</li>
            <li><b>Gaps.</b> Every sheet round the building can sit on its surfaces or stand off them: set the gap from the walls and the height above the roof. A larger shell is further from the occupants but needs more material.</li>
            <li><b>Barrier wall between line and building.</b> Free-standing, along the line. Screens the electric field; for the magnetic field it is the weakest of the sheet options.</li>
            <li><b>Passive loop.</b> Two conductors strung along the line and bonded into a loop, optionally with a series capacitor. Works at the source, so it helps every building on that side.</li>
            <li><b>Earthed screening wires.</b> A canopy of earthed wires over the building, for the electric field only.</li>
            <li><b>Custom layout.</b> Plates placed by coordinates, for anything the arrangements above do not cover: an L-shaped screen, a canopy on one side, a partial cage.</li>
            <li><b>At the line itself.</b> Taller towers, low-reactance phasing of double circuits and compact conductor spacing lower the field everywhere. Try them on the Lines tab; Compare → Measures puts them beside the shields.</li>
          </ul>
        </Accordion>
        <Accordion title="Published work on this arrangement">
          <StudyList ids={lib?.shield_presets.find((x) => x.id === shd.preset)?.refs ?? []} />
        </Accordion>
        <Accordion title="What the physical model does and does not capture">
          <ul className="small" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
            <li><b>Magnetic field.</b> The shield is cut into thin-shell boundary elements carrying eddy currents and magnetisation, driven by the field of every conductor. The field getting round edges is part of the solution, so it can rise beside the shield as well as fall inside it.</li>
            <li><b>Electric field.</b> The shield is a conductor in the line's electrostatic problem: held at earth potential if earthed, floating at a solved voltage if not.</li>
            <li><b>Construction.</b> Coverage below 100% and unbonded seams are real gaps between panels. Bonded panels share one circuit; a closed shell carries a circulating current, which is why it shields far better than open sheets.</li>
            <li><b>Verified</b> against exact solutions: an infinite slab (aluminium, steel, pure magnetic sheet) and a closed cylindrical shell (conducting and magnetic), all within a few percent. See Validation.</li>
            <li><b>Not captured.</b> The model is a cross-section: the two end walls of a building's shield, steel saturation, a separate rebar grid, and penetrations by pipes and cables are outside it. For a compact enclosure this makes the result an upper estimate.</li>
          </ul>
        </Accordion>
        <Accordion title="Why the electric and magnetic fields respond so differently">
          <p className="small" style={{ margin: 0 }}>At 50/60 Hz the electric field is easy to screen: any earthed conductor, including a wet concrete wall or a line of trees, sits at a fixed potential and ends the field lines. The magnetic field is hard: it needs induced currents that are large compared with the sheet's resistance (thick, wide sheets of aluminium or copper joined into closed loops), or a high-permeability path that carries the flux (steel). That is why a concrete wall can cut the electric field sharply and leave the magnetic field untouched.</p>
        </Accordion>
      </div>
    </div>
  );
}

/** The library entries behind an arrangement, with what each one found. */
function StudyList({ ids }: { ids: string[] }) {
  const lib = useStore((s) => s.library);
  const { pid } = useParams();
  const refs = ids.map((id) => lib?.references.find((r) => r.id === id)).filter((r): r is NonNullable<typeof r> => !!r);
  if (!refs.length) return <p className="small muted" style={{ margin: 0 }}>No study in the library is tied to this arrangement.</p>;
  return (
    <>
      <ul className="small" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.6 }}>
        {refs.map((r) => (
          <li key={r.id} style={{ marginBottom: 6 }}>
            <b>{r.authors.split(',')[0].split(' and ')[0]}{/,| and /.test(r.authors) ? ' et al.' : ''} ({r.year}).</b> {r.title}. <span className="muted">{r.venue}</span>
            {r.findings && <div className="muted">{r.findings}</div>}
          </li>
        ))}
      </ul>
      <p className="small mt-8" style={{ marginBottom: 0 }}><Link to={`/p/${pid}/library`}>Open the research library</Link> for the full records, links and what could and could not be checked for each source.</p>
    </>
  );
}
