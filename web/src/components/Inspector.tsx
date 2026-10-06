// The inspector: every input of the project, available beside every page so a
// change can be watched in whatever view is open.

import { Building2, Copy, Info, Plus, RotateCcw, RotateCw, Shield, SlidersHorizontal, Trash2, Zap } from 'lucide-react';
import { api } from '@/lib/api';
import { useStore, type InspectorTab } from '@/lib/store';
import type { BuildingCfg, CircuitCfg, Config, LineCfg, ShieldCfg } from '@/lib/types';
import { amps, fmt, sci } from '@/lib/format';
import { Accordion, Button, Eyebrow, Field, Note, NumberInput, Pill, Segmented, Select, SliderField, Switch, TextInput, cx } from './ui';

export function Inspector() {
  const tab = useStore((s) => s.inspectorTab);
  const set = useStore((s) => s.setInspector);
  const config = useStore((s) => s.config);
  const sol = useStore((s) => s.sol);
  const tabs: { id: InspectorTab; label: string; icon: React.ReactNode }[] = [
    { id: 'lines', label: 'Lines', icon: <Zap size={15} /> },
    { id: 'site', label: 'Site', icon: <Building2 size={15} /> },
    { id: 'shield', label: 'Shield', icon: <Shield size={15} /> },
    { id: 'standards', label: 'Standards', icon: <SlidersHorizontal size={15} /> },
  ];
  if (!config) return null;
  return (
    <aside className="inspector" aria-label="Project inputs">
      <div className="inspector-tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? 'active' : undefined} onClick={() => set(true, t.id)}>
            {t.icon}{t.label}
          </button>
        ))}
      </div>
      <div className="inspector-body">
        {sol?.warnings?.length ? <div className="mb-12">{sol.warnings.map((w, i) => <Note key={i}>{w}</Note>)}</div> : null}
        {tab === 'lines' && <LinesPanel />}
        {tab === 'site' && <SitePanel />}
        {tab === 'shield' && <ShieldPanel />}
        {tab === 'standards' && <StandardsPanel />}
      </div>
    </aside>
  );
}

// ------------------------------------------------------------------ Lines
type CircuitInfo = { id: number; label: string; voltage_kv: number; current_a: number; low_order: 'ABC' | 'CBA' };

function LinesPanel() {
  const config = useStore((s) => s.config)!;
  const lib = useStore((s) => s.library)!;
  const sol = useStore((s) => s.sol);
  const setConfig = useStore((s) => s.setConfig);
  const n = config.lines.length;

  const patch = (i: number, p: Partial<LineCfg>) => setConfig((c) => { Object.assign(c.lines[i], p); });
  const patchCustom = (i: number, p: Partial<LineCfg['custom']>) => setConfig((c) => { Object.assign(c.lines[i].custom, p); });
  const patchCircuit = (i: number, k: number, p: Partial<CircuitCfg>) => setConfig((c) => { Object.assign(c.lines[i].circuits[k], p); });
  const fresh = (c: Config) => {
    const side = c.lines.length % 2 === 1 ? 1 : -1;
    const far = Math.max(0, ...c.lines.map((l) => Math.abs(l.x_offset)));
    return { ...structuredClone(lib.default_line), name: `Line ${c.lines.length + 1}`, x_offset: side * (far + 30) };
  };
  const add = () => setConfig((c) => { c.lines.push(fresh(c)); });
  const remove = (i: number) => setConfig((c) => { c.lines.splice(i, 1); });
  // "Number of lines": add parallel lines on alternate sides, or drop the last ones
  const setCount = (k: number) => setConfig((c) => {
    while (c.lines.length > k) c.lines.pop();
    while (c.lines.length < k) c.lines.push(fresh(c));
  });
  const duplicate = (i: number) => setConfig((c) => {
    const copy = structuredClone(c.lines[i]);
    copy.name = `${copy.name} copy`; copy.x_offset = copy.x_offset + 30;
    c.lines.splice(i + 1, 0, copy);
  });
  /** The circuits of a line's tower, as the tower defines them. */
  const circuitsOf = (ln: LineCfg): CircuitInfo[] => {
    if (ln.preset === 'custom') {
      const one = { voltage_kv: ln.custom.voltage_kv, current_a: ln.custom.current_a };
      return ln.custom.layout === 'double-vertical'
        ? [{ id: 1, label: 'left', low_order: 'ABC', ...one }, { id: 2, label: 'right', low_order: 'CBA', ...one }]
        : [{ id: 1, label: '', low_order: 'ABC', ...one }];
    }
    return lib.tower_presets.find((p) => p.name === ln.preset)?.circuits ?? [];
  };
  /** One explicit entry per circuit, from what the line is using now. */
  const explicit = (ln: LineCfg, info: CircuitInfo[], fromTower = false): CircuitCfg[] => info.map((k) => ({
    on: true,
    voltage_kv: !fromTower && ln.preset !== 'custom' && ln.voltage_kv > 0 ? ln.voltage_kv : k.voltage_kv,
    current_a: !fromTower && ln.preset !== 'custom' && ln.current_a > 0 ? ln.current_a : k.current_a,
    load_pct: ln.load_pct,
    phase_order: ln.arrangement === 'ABC-CBA' ? k.low_order : 'ABC',
  }));
  const pickTower = (i: number, v: string) => {
    if (v === 'custom') { patch(i, { preset: v, current_a: 0, voltage_kv: 0, circuits: [] }); return; }
    const info = lib.tower_presets.find((p) => p.name === v)?.circuits ?? [];
    const mixed = new Set(info.map((k) => `${k.voltage_kv}/${k.current_a}`)).size > 1;
    // a tower with two voltage levels opens with each circuit set on its own, so nothing is hidden
    if (mixed) patch(i, { preset: v, current_a: 0, voltage_kv: 0, circuits: explicit({ ...config.lines[i], preset: v }, info, true) });
    else patch(i, { preset: v, circuits: [] });
  };

  return (
    <>
      <div className="section">
        <div className="row between mb-8">
          <Eyebrow className="mb-0">Transmission lines</Eyebrow>
          <Button size="sm" onClick={add} disabled={n >= 4} title={n >= 4 ? 'Up to four lines share a corridor' : 'Add a parallel line'}><Plus size={13} />Add line</Button>
        </div>
        <p className="small muted">A line here is one row of towers. On a tower that carries more than one circuit, each circuit can have its own voltage, current, loading and phase order, or be taken out of service. Every field superposes.</p>
        <Field label="Number of lines" className="mb-12">
          <Segmented value={String(n)} onChange={(v) => setCount(Number(v))} options={[1, 2, 3, 4].map((k) => ({ value: String(k), label: String(k) }))} />
        </Field>
        {config.lines.map((ln, i) => {
          const preset = lib.tower_presets.find((p) => p.name === ln.preset);
          const custom = ln.preset === 'custom';
          const out = sol?.lines[i];
          const info = circuitsOf(ln);
          const multi = info.length > 1;
          const separate = multi && ln.circuits.length === info.length;
          const mixedTower = new Set(info.map((k) => `${k.voltage_kv}/${k.current_a}`)).size > 1;
          const ratedA = custom ? ln.custom.current_a : (ln.current_a > 0 ? ln.current_a : preset?.current_a ?? 0);
          const kv = custom ? ln.custom.voltage_kv : (ln.voltage_kv > 0 ? ln.voltage_kv : preset?.voltage_kv ?? 0);
          const setRated = (v: number) => custom ? patchCustom(i, { current_a: v }) : patch(i, { current_a: v });
          const setKv = (v: number) => custom ? patchCustom(i, { voltage_kv: v }) : patch(i, { voltage_kv: v });
          const overridden = !custom && (ln.current_a > 0 || ln.voltage_kv > 0);
          const live = separate ? ln.circuits.filter((c) => c.on) : [];
          const meta = separate
            ? `${[...new Set(live.map((c) => fmt(c.voltage_kv || kv, 3)))].join('/') || '—'} kV · ${live.length} of ${info.length} live`
            : `${mixedTower && !overridden ? [...new Set(info.map((k) => fmt(k.voltage_kv, 3)))].join(' / ') : fmt(kv, 3)} kV · ${amps((ratedA * ln.load_pct) / 100)} A${multi ? ' each' : ''}`;
          return (
            <Accordion key={i} defaultOpen={i === 0 || n <= 2} title={<span>{ln.name || `Line ${i + 1}`}</span>} meta={meta}>
              <Field label="Name"><TextInput value={ln.name} onChange={(v) => patch(i, { name: v })} maxLength={40} /></Field>
              <Field label="Tower" help={custom ? 'Define the geometry below.' : preset?.description}>
                <Select value={ln.preset} onChange={(v) => pickTower(i, v)}
                        options={[...lib.tower_presets.map((p) => ({ value: p.name, label: p.name })), { value: 'custom', label: 'Custom geometry…' }]} />
              </Field>

              {custom && <CustomTower ln={ln} onChange={(p) => { patchCustom(i, p); if (p.layout && p.layout !== ln.custom.layout) patch(i, { circuits: [] }); }} />}

              {multi && (
                <Field label={`Circuits on this tower (${info.length})`} className="mt-8"
                       help={separate ? 'Each circuit below has its own voltage, current, loading and phase order.' : 'Every circuit carries the voltage, current and loading set below.'}>
                  <Segmented value={separate ? 'sep' : 'same'} onChange={(v) => patch(i, { circuits: v === 'sep' ? explicit(ln, info) : [] })}
                             options={[{ value: 'same', label: 'Same settings' }, { value: 'sep', label: 'Set separately' }]} />
                </Field>
              )}

              {separate ? ln.circuits.map((c, k) => {
                const opA = (c.current_a * c.load_pct) / 100;
                return (
                  <div className="card surface tight mt-8" key={k}>
                    <div className="row between">
                      <b className="small">Circuit {info[k].id}{info[k].label ? ` · ${info[k].label}` : ''}</b>
                      <Switch checked={c.on} onChange={(v) => patchCircuit(i, k, { on: v })} label={c.on ? 'In service' : 'Out of service'} />
                    </div>
                    {c.on ? <>
                      <div className="fields-2 mt-8">
                        <Field label="Voltage (L-L)"><NumberInput value={c.voltage_kv} onChange={(v) => patchCircuit(i, k, { voltage_kv: v })} min={1} max={1200} step={1} unit="kV" /></Field>
                        <Field label="Rated current"><NumberInput value={c.current_a} onChange={(v) => patchCircuit(i, k, { current_a: v })} min={1} max={10000} step={50} unit="A" /></Field>
                      </div>
                      <SliderField label="Loading" value={c.load_pct} onChange={(v) => patchCircuit(i, k, { load_pct: v })} min={0} max={120} step={5} unit="%"
                                   help={<>Operating current ≈ <b className="mono">{amps(opA)} A</b></>} />
                      <Field label="Phase order, top to bottom">
                        <Segmented size="sm" value={c.phase_order} onChange={(v) => patchCircuit(i, k, { phase_order: v })} options={[{ value: 'ABC', label: 'A · B · C' }, { value: 'CBA', label: 'C · B · A' }]} />
                      </Field>
                    </> : <p className="help small muted mt-4" style={{ marginBottom: 0 }}>De-energised and earthed: it carries no current and sits at zero potential. Its conductors still shape the electric field: a little higher close to the line, lower further out on this side.</p>}
                  </div>
                );
              }) : <>
                <Field label="Voltage class" help="Fills the voltage and an indicative thermal current. Edit either afterwards.">
                  <Select value={''} onChange={(v) => {
                    const vc = lib.voltage_classes.find((x) => x.label === v);
                    if (!vc) return;
                    if (custom) patchCustom(i, { voltage_kv: vc.kv, current_a: vc.current_a, radius_mm: +(vc.radius_m * 1000).toFixed(2), bundle_n: vc.bundle });
                    else patch(i, { voltage_kv: vc.kv, current_a: vc.current_a });
                  }} options={[{ value: '', label: 'Quick set…' }, ...lib.voltage_classes.map((v) => ({ value: v.label, label: `${v.label} · ${v.current_a} A` }))]} />
                </Field>
                <div className="fields-2 mt-8">
                  <Field label="Voltage (L-L)"><NumberInput value={kv} onChange={setKv} min={1} max={1200} step={1} unit="kV" /></Field>
                  <Field label="Rated current" hint={multi ? 'each circuit' : undefined}><NumberInput value={ratedA} onChange={setRated} min={1} max={10000} step={50} unit="A" /></Field>
                </div>
                {mixedTower && !overridden && <p className="help small muted mt-4">This tower carries {[...new Set(info.map((k) => k.voltage_kv))].join(' and ')} kV circuits, each at its own rating. Typing a value here applies it to every circuit; choose “Set separately” to keep them different.</p>}
                {overridden && (
                  <button className="btn ghost sm mt-4" onClick={() => patch(i, { current_a: 0, voltage_kv: 0 })}><RotateCcw size={12} />Use the tower's own {mixedTower ? 'ratings' : `${preset?.voltage_kv} kV / ${preset?.current_a} A`}</button>
                )}
                <SliderField label="Loading" value={ln.load_pct} onChange={(v) => patch(i, { load_pct: v })} min={0} max={120} step={5} unit="%"
                             help={<>Operating current ≈ <b className="mono">{amps(mixedTower && !overridden ? out?.operating_a ?? 0 : (ratedA * ln.load_pct) / 100)} A</b>{multi ? (mixedTower && !overridden ? ' on the heaviest circuit' : ' per circuit') : ''} · {out?.loading_context ?? ''}. Loading sets the current and the thermal sag.</>} />
                {multi && (
                  <Field label="Phase arrangement of the circuits" help="ABC-CBA (low-reactance) reverses the phase order on the opposite circuit, so the circuits partly cancel each other's field.">
                    <Segmented value={ln.arrangement} onChange={(v) => patch(i, { arrangement: v })} options={[{ value: 'ABC-ABC', label: 'ABC-ABC' }, { value: 'ABC-CBA', label: 'ABC-CBA' }]} />
                  </Field>
                )}
              </>}

              <SliderField label="Centreline offset" value={ln.x_offset} onChange={(v) => patch(i, { x_offset: v })} min={-100} max={100} step={1} unit="m" />
              <SliderField label="Phase offset" value={ln.phase_offset_deg} onChange={(v) => patch(i, { phase_offset_deg: v })} min={-180} max={180} step={5} unit="°"
                           help="Rotates every phasor on this line, for parallel circuits that are out of step." />
              <SliderField label="Conductor height adjustment" value={ln.height_adjust_m ?? 0} onChange={(v) => patch(i, { height_adjust_m: v })} min={-5} max={20} step={0.5} unit="m"
                           help={<>Raises or lowers every conductor of this line, as taller or shorter towers would.{out ? <> Lowest conductor at mid-span now: <b className="mono">{fmt(out.min_height_m, 3)} m</b>.</> : null}</>} />
              <div className="row mt-12">
                <Button size="sm" onClick={() => duplicate(i)} disabled={n >= 4}><Copy size={12} />Duplicate</Button>
                <Button size="sm" variant="danger" onClick={() => remove(i)} disabled={n <= 1}><Trash2 size={12} />Remove</Button>
              </div>
            </Accordion>
          );
        })}
      </div>
      <div className="section">
        <Eyebrow>Sag and span</Eyebrow>
        <SliderField label="Thermal sag at 100% load" value={config.corridor.max_sag_m} onChange={(v) => setConfig((c) => { c.corridor.max_sag_m = v; })} min={0} max={5} step={0.1} unit="m"
                     help="Extra mid-span sag from conductor heating. It grows with the square of the loading." />
        <SliderField label="Span length" value={config.corridor.span_m} onChange={(v) => setConfig((c) => { c.corridor.span_m = v; })} min={100} max={600} step={10} unit="m"
                     help="Tower to tower. Fields are reported at mid-span, where the conductors are lowest." />
        <div className="mt-12">
          <Switch checked={!!config.corridor.sag_follows_span} onChange={(v) => setConfig((c) => { c.corridor.sag_follows_span = v; })} label="Sag follows the span" />
          <p className="help small muted mt-4">
            {config.corridor.sag_follows_span
              ? <>On: the towers keep their height and the sag grows with the square of the span, from the {lib.reference_span_m} m the tower data is given for. At {config.corridor.span_m} m the sag is <b className="mono">×{fmt(Math.pow(config.corridor.span_m / lib.reference_span_m, 2), 3)}</b>, so a longer span hangs lower and reads higher.</>
              : <>Off: the mid-span heights stay as entered whatever the span, so the readings at mid-span do not change with it. The span then only sets how quickly the field falls towards the towers. Switch this on to let a longer span sag more.</>}
          </p>
        </div>
        {sol?.clearance && (
          <div className={cx('note mt-8', sol.clearance.ok ? 'info' : 'bad')}>
            Lowest conductor at mid-span: <b className="mono">{fmt(sol.clearance.min_height_m, 3)} m</b> above ground{config.lines.length > 1 ? ` (${sol.clearance.line})` : ''}.
            {' '}{sol.clearance.ok ? 'Indicative minimum' : 'That is below the indicative minimum of'} <b className="mono">{fmt(sol.clearance.required_m, 3)} m</b>{sol.clearance.ok ? ' for this voltage.' : ` for ${sol.clearance.tightest_line}.`}
            <span className="tiny muted" style={{ display: 'block', marginTop: 2 }}>5.6 m plus 10 mm per kV to earth above 22 kV. The line owner's standard is the one that counts.</span>
          </div>
        )}
      </div>
    </>
  );
}

function CustomTower({ ln, onChange }: { ln: LineCfg; onChange: (p: Partial<LineCfg['custom']>) => void }) {
  const lib = useStore((s) => s.library)!;
  const c = ln.custom;
  const dbl = c.layout === 'double-vertical';
  const vert = c.layout !== 'horizontal';
  return (
    <div className="card surface tight mt-8">
      <Field label="Layout">
        <Select value={c.layout} onChange={(v) => onChange({ layout: v })} options={Object.entries(lib.custom_layouts).map(([value, label]) => ({ value: value as any, label }))} />
      </Field>
      <div className="fields-2 mt-8">
        <Field label="Top attachment height"><NumberInput value={c.attach_height_m} onChange={(v) => onChange({ attach_height_m: v })} min={6} max={90} step={0.5} unit="m" /></Field>
        <Field label="Design sag"><NumberInput value={c.design_sag_m} onChange={(v) => onChange({ design_sag_m: v })} min={0} max={25} step={0.5} unit="m" /></Field>
        {c.layout !== 'vertical' && c.layout !== 'double-vertical' && <Field label="Phase spacing"><NumberInput value={c.phase_spacing_m} onChange={(v) => onChange({ phase_spacing_m: v })} min={0.5} max={25} step={0.5} unit="m" /></Field>}
        {vert && <Field label="Vertical spacing"><NumberInput value={c.vertical_spacing_m} onChange={(v) => onChange({ vertical_spacing_m: v })} min={0.5} max={20} step={0.5} unit="m" /></Field>}
        {dbl && <Field label="Circuit spacing"><NumberInput value={c.circuit_spacing_m} onChange={(v) => onChange({ circuit_spacing_m: v })} min={2} max={40} step={0.5} unit="m" /></Field>}
        <Field label="Bundle"><Select value={c.bundle_n} onChange={(v) => onChange({ bundle_n: v })} options={[1, 2, 3, 4].map((n) => ({ value: n, label: n === 1 ? 'Single' : `${n} sub-conductors` }))} /></Field>
        {c.bundle_n > 1 && <Field label="Bundle spacing"><NumberInput value={c.bundle_spacing_m} onChange={(v) => onChange({ bundle_spacing_m: v })} min={0.1} max={1} step={0.05} unit="m" /></Field>}
        <Field label="Sub-conductor radius"><NumberInput value={c.radius_mm} onChange={(v) => onChange({ radius_mm: v })} min={2} max={40} step={0.1} unit="mm" /></Field>
        <Field label="Tower drawing"><Select value={c.tower_style} onChange={(v) => onChange({ tower_style: v })} options={[{ value: 'lattice', label: 'Lattice' }, { value: 'monopole', label: 'Monopole' }]} /></Field>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------- Site
function SitePanel() {
  const config = useStore((s) => s.config)!;
  const lib = useStore((s) => s.library)!;
  const setConfig = useStore((s) => s.setConfig);
  const cor = config.corridor;
  const g = lib.ground_models.find((m) => m.id === cor.ground_model)!;
  const setCor = (p: Partial<Config['corridor']>) => setConfig((c) => { Object.assign(c.corridor, p); });
  const patchB = (i: number, p: Partial<BuildingCfg>) => setConfig((c) => { Object.assign(c.buildings[i], p); });
  const addB = () => setConfig((c) => {
    const b = structuredClone(lib.default_building);
    b.name = `Building ${c.buildings.length + 1}`;
    b.distance = 25 + c.buildings.length * 20;
    c.buildings.push(b);
  });

  return (
    <>
      <div className="section">
        <Eyebrow>Corridor</Eyebrow>
        <SliderField label="Right-of-way half-width" value={cor.row_half_width} onChange={(v) => setCor({ row_half_width: v })} min={5} max={90} step={1} unit="m" hint="±" />
        <div className="fields-2 mt-8">
          <Field label="System frequency">
            <Segmented value={String(cor.freq_hz) as '50' | '60'} onChange={(v) => setCor({ freq_hz: Number(v) })} options={[{ value: '50', label: '50 Hz' }, { value: '60', label: '60 Hz' }]} />
          </Field>
          <Field label="Measurement height"><NumberInput value={cor.meas_height} onChange={(v) => setCor({ meas_height: v })} min={0.5} max={3} step={0.1} unit="m" /></Field>
        </div>
        <p className="help small muted mt-4">Peak fields and compliance are read on the lateral profile at this height. 1.0 m is the usual reference.</p>
      </div>

      <div className="section">
        <Eyebrow>Earth return</Eyebrow>
        <Field label="Ground model" help={<>{g.limit.replace('rho', 'ρ').replace('->', '→').replace('infinity', '∞')} · {g.description}</>}>
          <Select value={cor.ground_model} onChange={(v) => setCor({ ground_model: v })} options={lib.ground_models.map((m) => ({ value: m.id, label: m.label }))} />
        </Field>
        {!g.validated && <Note className="mt-8">Not yet validated against reference data. Bracket any result you report with the two exact limits (see Earth sensitivity).</Note>}
        {cor.ground_model === 'complex_image' && (
          <div className="mt-8">
            <Field label="Soil type">
              <Select value={cor.soil_type} onChange={(v) => { const s = lib.soil_types.find((x) => x.id === v); setCor({ soil_type: v, earth_rho: s ? s.resistivity : cor.earth_rho }); }}
                      options={lib.soil_types.map((s) => ({ value: s.id, label: `${s.name} (${s.range} Ω·m)` }))} />
            </Field>
            <Field label="Earth resistivity"><NumberInput value={cor.earth_rho} onChange={(v) => setCor({ earth_rho: v })} min={0.1} max={100000} step={10} unit="Ω·m" /></Field>
          </div>
        )}
        <div className="mt-12">
          <Switch checked={cor.bundle_eq} onChange={(v) => setCor({ bundle_eq: v })} label="E field: bundle-equivalent radius" />
          <p className="help small muted mt-4">A bundled phase behaves like one larger conductor. Switching this off under-predicts E for bundled lines (it reproduces Taki v2).</p>
        </div>
      </div>

      <div className="section">
        <div className="row between mb-8">
          <Eyebrow className="mb-0">Buildings</Eyebrow>
          <Button size="sm" onClick={addB} disabled={config.buildings.length >= 6}><Plus size={13} />Add building</Button>
        </div>
        {config.buildings.length === 0 && <p className="small muted">No buildings. Add one to read the field at a receptor.</p>}
        {config.buildings.map((b, i) => {
          const bt = lib.building_types.find((t) => t.name === b.type);
          const mat = lib.building_materials.find((m) => m.key === b.material);
          return (
            <Accordion key={i} defaultOpen={config.buildings.length === 1} title={b.name || `Building ${i + 1}`} meta={`${b.type} · ${b.distance} m ${b.side}`}>
              <Field label="Name"><TextInput value={b.name} onChange={(v) => patchB(i, { name: v })} maxLength={40} /></Field>
              <Field label="Type" help={bt?.occupancy}>
                <div className="tile-grid">
                  {lib.building_types.map((t) => (
                    <button key={t.name} className={cx('tile', b.type === t.name && 'on')} onClick={() => patchB(i, { type: t.name, roof: t.roof as any })}>{t.name}<small>{t.sensitivity === 'high' ? 'sensitive receptor' : t.sensitivity === 'equipment' ? 'sensitive equipment' : `${t.sensitivity} sensitivity`}</small></button>
                  ))}
                </div>
              </Field>
              {bt && (b.width !== bt.width || b.depth !== bt.depth || b.height !== bt.height) && (
                <button className="btn ghost sm mt-4" onClick={() => patchB(i, { width: bt.width, depth: bt.depth, height: bt.height, roof: bt.roof as any })}><RotateCcw size={12} />Use typical {bt.name.toLowerCase()} size ({bt.width}×{bt.depth}×{bt.height} m)</button>
              )}
              <div className="fields-2 mt-8">
                <Field label="Shape"><Select value={b.shape} onChange={(v) => patchB(i, { shape: v })} options={Object.entries(lib.building_shapes).map(([value, label]) => ({ value: value as any, label }))} /></Field>
                <Field label="Roof"><Select value={b.roof} onChange={(v) => patchB(i, { roof: v })} options={Object.entries(lib.roof_types).map(([value, label]) => ({ value: value as any, label }))} /></Field>
              </div>
              <div className="fields-3 mt-8">
                <Field label={b.shape === 'cylinder' ? 'Diameter' : 'Width'}><NumberInput value={b.width} onChange={(v) => patchB(i, { width: v })} min={4} max={200} step={1} unit="m" /></Field>
                <Field label="Depth"><NumberInput value={b.depth} onChange={(v) => patchB(i, { depth: v })} min={4} max={200} step={1} unit="m" /></Field>
                <Field label="Height"><NumberInput value={b.height} onChange={(v) => patchB(i, { height: v })} min={3} max={150} step={1} unit="m" /></Field>
              </div>
              <div className="fields-2 mt-8" style={{ alignItems: 'start' }}>
                <Field label="Storey height" help={`≈ ${Math.max(1, Math.round(b.height / (b.floor_h ?? bt?.floor_h ?? 3.2)))} floor${Math.round(b.height / (b.floor_h ?? bt?.floor_h ?? 3.2)) > 1 ? 's' : ''} · drawing only`}>
                  <NumberInput value={b.floor_h ?? bt?.floor_h ?? 3.2} onChange={(v) => patchB(i, { floor_h: v })} min={2.4} max={12} step={0.1} unit="m" />
                </Field>
                {b.shape !== 'cylinder' && <Button size="sm" style={{ marginTop: 22 }} onClick={() => patchB(i, { width: b.depth, depth: b.width })} title="Swap width and depth: the building turned a quarter turn"><RotateCw size={12} />Turn 90°</Button>}
              </div>
              <SliderField label="Near wall from centreline" value={b.distance} onChange={(v) => patchB(i, { distance: v })} min={2} max={150} step={1} unit="m" />
              <div className="fields-2 mt-8">
                <Field label="Side of the line"><Segmented value={b.side} onChange={(v) => patchB(i, { side: v })} options={[{ value: 'left', label: 'Left (−x)' }, { value: 'right', label: 'Right (+x)' }]} /></Field>
                <Field label="Along the line (z)"><NumberInput value={b.z_offset} onChange={(v) => patchB(i, { z_offset: v })} min={-300} max={300} step={5} unit="m" /></Field>
              </div>
              <p className="help small muted mt-4">z = 0 is mid-span, where the conductors are lowest. Windows, doors and rooftop plant in the 3-D view are there to make the building recognisable; the field calculation uses its outline at this position, and the fabric estimate below.</p>
              <Field label="Building fabric (empirical estimate)" help={mat?.mechanism}>
                <Select value={b.material} onChange={(v) => patchB(i, { material: v, b_pct: null, e_pct: null })} options={lib.building_materials.map((m) => ({ value: m.key, label: m.label }))} />
              </Field>
              {mat && mat.key !== 'none' && (
                <>
                  <SliderField label="B reduction assumed" value={b.b_pct ?? mat.b_pct} onChange={(v) => patchB(i, { b_pct: v })} min={mat.b_range[0]} max={mat.b_range[1]} step={1} unit="%" />
                  <SliderField label="E reduction assumed" value={b.e_pct ?? mat.e_pct} onChange={(v) => patchB(i, { e_pct: v })} min={mat.e_range[0]} max={mat.e_range[1]} step={1} unit="%" />
                </>
              )}
              <div className="row mt-12"><Button size="sm" variant="danger" onClick={() => setConfig((c) => { c.buildings.splice(i, 1); if (c.shield.target_building >= c.buildings.length) c.shield.target_building = 0; })}><Trash2 size={12} />Remove building</Button></div>
            </Accordion>
          );
        })}
      </div>
    </>
  );
}

// ----------------------------------------------------------------- Shield
function ShieldPanel() {
  const config = useStore((s) => s.config)!;
  const lib = useStore((s) => s.library)!;
  const sol = useStore((s) => s.sol);
  const setConfig = useStore((s) => s.setConfig);
  const toast = useStore((s) => s.toast);
  const sh = config.shield;
  const set = (p: Partial<ShieldCfg>) => setConfig((c) => { Object.assign(c.shield, p); });
  const preset = lib.shield_presets.find((p) => p.id === sh.preset) ?? lib.shield_presets[0];
  const attached = preset.attached;
  const wires = preset.wires;
  const isMesh = sh.mesh || preset.mesh;
  const mat = lib.shield_materials.find((m) => m.id === sh.material_id);
  const off = !sh.enabled;
  const emp = mat?.empirical_key ? lib.building_materials.find((m) => m.key === mat.empirical_key) : null;
  const delta = mat ? (config.corridor.freq_hz >= 55 ? mat.skin_depth_60_mm : mat.skin_depth_50_mm) : null;
  const target = config.buildings[Math.min(sh.target_building, config.buildings.length - 1)];
  const closed = ['enclosure', 'envelope', 'room'].includes(sh.preset);
  const custom = !!preset.custom;

  const barrier = !attached && !wires && !custom;
  // Free-standing measures are placed from the site: a barrier beside the building, a loop where it
  // lowers the field inside it most, screening wires over it.
  const place = async (id: string, say = false) => {
    try {
      const r = await api.post<{ changes: Partial<ShieldCfg>; note?: string }>('/shield/suggest', { config: { ...config, shield: { ...sh, preset: id } }, preset: id });
      set({ preset: id, ...r.changes });
      if (r.note && (say || id !== 'screen-wires')) toast(r.note);
    } catch { set({ preset: id }); }
  };
  /** Plates to start a custom layout from: the arrangement on screen, or one wall beside the building. */
  const seedPlates = (): Partial<ShieldCfg> => {
    const s = sol?.shield;
    if (s?.on && s.walls.length && !s.is_wire) {
      return { custom_plates: s.walls.slice(0, 16).map((w) => w.map((v) => +v.toFixed(2))), length_m: Math.max(4, +(2 * s.zh).toFixed(1)), z_center_m: +s.zc.toFixed(1) };
    }
    const b = config.buildings[Math.min(sh.target_building, config.buildings.length - 1)];
    const sgn = b?.side === 'left' ? -1 : 1;
    const x = sgn * Math.max(5, (b?.distance ?? 25) - 5);
    return { custom_plates: [[x, 0, x, 10]], z_center_m: b?.z_offset ?? 0 };
  };
  const choose = (id: string) => {
    const p = lib.shield_presets.find((x) => x.id === id)!;
    if (p.custom) { set(sh.custom_plates.length ? { preset: id } : { preset: id, ...seedPlates() }); return; }
    if (id === sh.preset) return;
    if (p.wires) { void place(id); return; }
    // a barrier wall chosen for the first time is put beside the building; swapping one kind of
    // barrier for another keeps where it stands
    if (!p.attached && !barrier && config.buildings.length) { void place(id); return; }
    set({ preset: id });
  };
  const families: [string, typeof lib.shield_presets][] = [
    ['Around the building', lib.shield_presets.filter((p) => p.attached)],
    ['Between the line and the building', lib.shield_presets.filter((p) => !p.attached && !p.custom)],
    ['Your own layout', lib.shield_presets.filter((p) => p.custom)],
  ];
  /** Where a free-standing shield sits along the line. */
  const alongLine = (
    <div className="fields-2 mt-8" style={{ alignItems: 'start' }}>
      <Field label="Centre along the line (z)" help="0 = mid-span"><NumberInput value={sh.z_center_m ?? 0} onChange={(v) => set({ z_center_m: v })} min={-1000} max={1000} step={1} unit="m" /></Field>
      {target && <Button size="sm" style={{ marginTop: 22 }} disabled={Math.abs((sh.z_center_m ?? 0) - target.z_offset) < 1e-6} onClick={() => set({ z_center_m: target.z_offset })} title={`Centre it on ${target.name}`}>At the building</Button>}
    </div>
  );

  return (
    <>
      <div className="section">
        <div className="row between">
          <Eyebrow className="mb-0">Shielding</Eyebrow>
          <Switch checked={sh.enabled} onChange={(v) => set({ enabled: v })} label={sh.enabled ? 'On' : 'Off'} />
        </div>
        <p className="small muted mt-8">A shield around the building you want to protect, with a real size and material. It is drawn on every view and never changes the compliance result, which uses the unshielded field.</p>
        {sol?.shield.no_geometry && <Note kind="bad">This arrangement goes on a building. Add a building on the Site tab.</Note>}
      </div>

      <div className="section">
        <Eyebrow>Arrangement</Eyebrow>
        {config.buildings.length > 0 && (
          <Field label="Building to protect">
            <Select value={Math.min(sh.target_building, config.buildings.length - 1)} onChange={(v) => set({ target_building: v })} options={config.buildings.map((b, i) => ({ value: i, label: `${b.name} · ${b.distance} m ${b.side}` }))} />
          </Field>
        )}
        <Field label="Where the shield goes" help={<>{preset.label}: {preset.hint}.</>}>
          <select className="select" value={sh.preset} onChange={(e) => choose(e.target.value)} aria-label="Shield arrangement">
            {families.map(([title, items]) => (
              <optgroup key={title} label={title}>
                {items.map((p) => <option key={p.id} value={p.id}>{p.short}</option>)}
              </optgroup>
            ))}
          </select>
        </Field>

        <div className="mt-12">
          {sh.preset === 'surround-wall' && <>
            <SliderField label="Wall height" value={sh.height_m} onChange={(v) => set({ height_m: v })} min={1} max={40} step={0.5} unit="m" />
            <SliderField label="Gap between wall and building" value={sh.standoff_m} onChange={(v) => set({ standoff_m: v })} min={0.5} max={15} step={0.5} unit="m" />
          </>}
          {['enclosure', 'envelope', 'walls'].includes(sh.preset) && <>
            <SliderField label="Gap between the sheet and the walls" value={sh.gap_m} onChange={(v) => set({ gap_m: v })} min={0} max={15} step={0.25} unit="m"
                         help="0 = fixed to the building. With a gap it is a free-standing shield round the building, and it runs past the ends of the building by the same gap." />
            {sh.preset !== 'walls' && <SliderField label="Height above the roof" value={sh.roof_gap_m} onChange={(v) => set({ roof_gap_m: v })} min={0} max={15} step={0.25} unit="m" />}
          </>}
          {sh.preset === 'roof' && <>
            <SliderField label="Height above the roof" value={sh.roof_gap_m} onChange={(v) => set({ roof_gap_m: v })} min={0} max={15} step={0.25} unit="m" help="0 = on the roof. Raised, it is a canopy over the building." />
            <SliderField label="Overhang beyond the walls" value={sh.gap_m} onChange={(v) => set({ gap_m: v })} min={0} max={15} step={0.25} unit="m" />
          </>}
          {sh.preset === 'panel' && <>
            <SliderField label="Height covered" value={sh.height_m} onChange={(v) => set({ height_m: v })} min={1} max={Math.max(3, target?.height ?? 40)} step={0.5} unit="m" help="From the ground up, on the wall that faces the line." />
            <SliderField label="Gap between the sheet and the wall" value={sh.gap_m} onChange={(v) => set({ gap_m: v })} min={0} max={15} step={0.25} unit="m" help="0 = fixed to the facade. With a gap it stands in front of it, towards the line." />
          </>}
          {sh.preset === 'floor' && <SliderField label="Floor level above ground" value={sh.floor_level_m} onChange={(v) => set({ floor_level_m: v })} min={0.2} max={Math.max(0.2, (target?.height ?? 10) - 0.5)} step={0.1} unit="m" help="0.2 m is the ground slab. Raise it to shield the floor of an upper storey." />}
          {custom && <PlateEditor plates={sh.custom_plates} onChange={(v) => set({ custom_plates: v })} length={sh.length_m} z={sh.z_center_m ?? 0} span={config.corridor.span_m}
                                  onLength={(v) => set({ length_m: v })} onZ={(v) => set({ z_center_m: v })} buildingZ={target?.z_offset ?? null} buildingName={target?.name ?? ''} />}
          {sh.preset === 'room' && <>
            <div className="fields-3">
              <Field label="Width"><NumberInput value={sh.room_width_m} onChange={(v) => set({ room_width_m: v })} min={1.5} max={target?.width ?? 100} step={0.5} unit="m" /></Field>
              <Field label="Depth"><NumberInput value={sh.room_depth_m} onChange={(v) => set({ room_depth_m: v })} min={1.5} max={target?.depth ?? 100} step={0.5} unit="m" /></Field>
              <Field label="Height"><NumberInput value={sh.room_height_m} onChange={(v) => set({ room_height_m: v })} min={1.8} max={target?.height ?? 40} step={0.1} unit="m" /></Field>
            </div>
            <div className="fields-2 mt-8">
              <Field label="From the facing wall"><NumberInput value={sh.room_offset_m} onChange={(v) => set({ room_offset_m: v })} min={0.3} max={target?.width ?? 100} step={0.5} unit="m" /></Field>
              <Field label="Floor level"><NumberInput value={sh.room_floor_m} onChange={(v) => set({ room_floor_m: v })} min={0.2} max={target?.height ?? 40} step={0.5} unit="m" /></Field>
            </div>
            <p className="help small muted mt-4">A room lined on all six sides: the usual way to protect one sensitive space (equipment room, laboratory, bedroom) without cladding the whole building.</p>
          </>}
          {barrier && <>
            <Field label="Side of the line">
              <Segmented value={sh.side} onChange={(v) => set({ side: v })} options={[{ value: 'left', label: 'Left' }, { value: 'right', label: 'Right' }, { value: 'both', label: 'Both' }]} />
            </Field>
            <SliderField label="Distance from centreline" value={sh.distance_m} onChange={(v) => set({ distance_m: v })} min={1} max={100} step={0.5} unit="m" />
            <SliderField label="Height" value={sh.height_m} onChange={(v) => set({ height_m: v })} min={1} max={40} step={0.5} unit="m" />
            <SliderField label="Length along the line" value={sh.length_m} onChange={(v) => set({ length_m: v })} min={10} max={Math.max(60, config.corridor.span_m)} step={5} unit="m" />
            {alongLine}
            {target && <Button size="sm" className="mt-8" onClick={() => place(sh.preset, true)} title="Tries positions between the line and the building, as tall as the building, and keeps the one that leaves the lowest average field inside it">Place it beside {target.name}</Button>}
            <p className="help small muted mt-8">A wall only helps a building it stands beside: keep its length and its centre along the line over the building.</p>
          </>}
          {sh.preset === 'passive-loop' && <>
            <Field label="Loop layout">
              <Segmented value={sh.loop_vertical ? 'v' : 'h'} onChange={(v) => set({ loop_vertical: v === 'v' })} options={[{ value: 'h', label: 'Side by side' }, { value: 'v', label: 'One above the other' }]} />
            </Field>
            <SliderField label="Centre, from the line centreline" value={sh.distance_m} onChange={(v) => set({ distance_m: v })} min={0} max={60} step={0.5} unit="m" />
            {sh.distance_m >= 0.5 && <Field label="Side of the line"><Segmented value={sh.side} onChange={(v) => set({ side: v })} options={[{ value: 'left', label: 'Left' }, { value: 'right', label: 'Right' }, { value: 'both', label: 'Both' }]} /></Field>}
            <SliderField label={sh.loop_vertical ? 'Lower conductor height' : 'Height'} value={sh.height_m} onChange={(v) => set({ height_m: v })} min={2} max={60} step={0.5} unit="m" />
            <SliderField label="Spacing between the two conductors" value={sh.loop_spacing_m} onChange={(v) => set({ loop_spacing_m: v })} min={1} max={60} step={0.5} unit="m" />
            <SliderField label="Series-capacitor compensation" value={sh.loop_compensation_pct} onChange={(v) => set({ loop_compensation_pct: v })} min={0} max={95} step={5} unit="%"
                         help="A capacitor in series with the loop cancels part of its reactance, so more current is induced. Too much over-corrects: watch the field directly under the line." />
            <SliderField label="Length along the line" value={sh.length_m} onChange={(v) => set({ length_m: v })} min={20} max={Math.max(60, config.corridor.span_m)} step={5} unit="m" />
            {alongLine}
            <Button size="sm" className="mt-8" onClick={() => place('passive-loop', true)} title="Tries about 200 positions and compensation levels that keep clear of the conductors, and keeps the one with the lowest field in the protected building">Find the best placement</Button>
            <p className="help small muted mt-8">Two conductors strung parallel to the line and bonded at both ends. The line induces a current in the loop that partly cancels its field. Where it sits decides everything: a loop lowers the field in one place and raises it in another, and a badly placed one makes the building worse. Clearances to the live conductors must be agreed with the line owner.</p>
          </>}
          {sh.preset === 'screen-wires' && <>
            <Field label="Side of the line"><Segmented value={sh.side} onChange={(v) => set({ side: v })} options={[{ value: 'left', label: 'Left' }, { value: 'right', label: 'Right' }, { value: 'both', label: 'Both' }]} /></Field>
            <SliderField label="First wire, from the centreline" value={sh.distance_m} onChange={(v) => set({ distance_m: v })} min={0} max={100} step={0.5} unit="m" />
            <SliderField label="Width of the row" value={sh.screen_width_m} onChange={(v) => set({ screen_width_m: v })} min={2} max={120} step={1} unit="m" />
            <SliderField label="Height of the wires" value={sh.height_m} onChange={(v) => set({ height_m: v })} min={2} max={60} step={0.5} unit="m" />
            <SliderField label="Number of wires" value={sh.wire_count} onChange={(v) => set({ wire_count: Math.round(v) })} min={2} max={24} step={1} />
            <SliderField label="Length along the line" value={sh.length_m} onChange={(v) => set({ length_m: v })} min={10} max={Math.max(60, config.corridor.span_m)} step={5} unit="m" />
            {alongLine}
            {target && <Button size="sm" className="mt-8" onClick={() => place('screen-wires').then(() => toast(`Wires placed over ${target.name}.`))}>Place them over {target.name}</Button>}
            <p className="help small muted mt-8">A canopy of earthed wires. It screens the electric field well and does very little for the magnetic field.</p>
          </>}
        </div>
      </div>

      <div className="section">
        <Eyebrow>{wires ? 'Conductor' : 'Material'}</Eyebrow>
        {!wires && (
          <Field label="Model" help={
            sh.model === 'physical' ? 'Solves the real shield: eddy currents, flux shunting in steel and the field wrapping round edges and openings; the shield as an earthed or floating conductor for the electric field.'
              : sh.model === 'analytical' ? 'Infinite-sheet formula (Schelkunoff A + R + B) applied to the geometric shadow. For the magnetic field this is an upper bound.'
                : 'Taki’s literature-based percentage applied to the geometric shadow.'}>
            <Segmented value={sh.model} onChange={(v) => set({ model: v })} options={[
              { value: 'physical', label: 'Physical' }, { value: 'analytical', label: 'Analytical' }, { value: 'empirical', label: 'Empirical' }]} />
          </Field>
        )}
        <div className="mat-list mt-8" style={wires ? { maxHeight: 150 } : undefined}>
          {lib.shield_materials.filter((m) => !wires || ['aluminium', 'copper', 'galvsteel', 'mildsteel'].includes(m.id)).map((m) => (
            <button key={m.id} className={cx('mat-item', sh.material_id === m.id && 'on')} onClick={() => set({ material_id: m.id })}>
              <span>{m.label}</span><span className="cat">{m.category}{m.quality === 'assumed' ? ' · nominal' : ''}</span>
            </button>
          ))}
          {!wires && <button className={cx('mat-item', sh.material_id === 'custom' && 'on')} onClick={() => set({ material_id: 'custom' })}><span>Custom material…</span><span className="cat">your values</span></button>}
        </div>
        {sh.material_id === 'custom' && !wires ? (
          <div className="card surface tight mt-8">
            <Field label="Name"><TextInput value={sh.custom_material.label} onChange={(v) => set({ custom_material: { ...sh.custom_material, label: v } })} maxLength={40} /></Field>
            <div className="fields-2 mt-8">
              <Field label="Conductivity σ"><NumberInput value={sh.custom_material.sigma} onChange={(v) => set({ custom_material: { ...sh.custom_material, sigma: v } })} min={0} max={1e9} step={1e5} unit="S/m" /></Field>
              <Field label="Relative permeability µr"><NumberInput value={sh.custom_material.mu_r} onChange={(v) => set({ custom_material: { ...sh.custom_material, mu_r: v } })} min={0.1} max={1e6} step={1} /></Field>
            </div>
            <p className="help small muted mt-4">Your values are used as given and are marked as user-supplied in reports.</p>
          </div>
        ) : mat && (
          <div className="card surface tight mt-8 small">
            <div className="row wrap gap-4 mb-8">
              <Pill>σ {sci(mat.sigma)} S/m</Pill><Pill>µr {fmt(mat.mu_r, 4)}</Pill>
              {!wires && delta && Number.isFinite(delta) && <Pill>skin depth {fmt(delta, 3)} mm</Pill>}
              <Pill tone={mat.quality === 'verified' ? 'green' : 'amber'}>{mat.quality === 'verified' ? 'verified data' : 'nominal data'}</Pill>
            </div>
            {!wires && <><div>{mat.mechanisms}</div><div className="muted mt-4">{mat.limitations}</div></>}
          </div>
        )}
        {wires ? (
          <Field label="Conductor cross-section" className="mt-12" help={`Equivalent to a round conductor of ${fmt(2 * Math.sqrt(sh.wire_mm2 / Math.PI), 3)} mm diameter.`}>
            <Select value={[50, 95, 150, 240, 400, 630, 1000].includes(sh.wire_mm2) ? sh.wire_mm2 : 400} onChange={(v) => set({ wire_mm2: v })} options={[50, 95, 150, 240, 400, 630, 1000].map((a) => ({ value: a, label: `${a} mm²` }))} />
          </Field>
        ) : <>
          <div className="fields-2 mt-12">
            <Field label="Thickness"><NumberInput value={sh.thickness_mm} onChange={(v) => set({ thickness_mm: v })} min={0.01} max={1500} step={0.5} unit="mm" /></Field>
            <Field label="Layers"><Select value={sh.layers} onChange={(v) => set({ layers: v })} options={[1, 2, 3].map((n) => ({ value: n, label: String(n) }))} /></Field>
          </div>
          {sh.layers > 1 && <>
            <Field label="Second layer material" help="Combining a good conductor (aluminium, copper) with a magnetic steel is the standard way to build a low-frequency shielded room: one layer carries eddy currents, the other carries the flux.">
              <Select value={sh.layer2_material_id ?? ''} onChange={(v) => set({ layer2_material_id: v || null })}
                      options={[{ value: '', label: 'Same as the first layer' }, ...lib.shield_materials.filter((m) => m.id !== sh.material_id).map((m) => ({ value: m.id, label: m.label }))]} />
            </Field>
            <Field label="Layer spacing" help="Spaced layers are solved as separate sheets in the physical model."><NumberInput value={sh.layer_spacing_m} onChange={(v) => set({ layer_spacing_m: v })} min={0.02} max={3} step={0.05} unit="m" /></Field>
          </>}
          {sh.model === 'empirical' && (emp ? (
            <div className="mt-8">
              <SliderField label="B reduction assumed" value={sh.emp_b_pct ?? emp.b_pct} onChange={(v) => set({ emp_b_pct: v })} min={emp.b_range[0]} max={emp.b_range[1]} step={1} unit="%" />
              <SliderField label="E reduction assumed" value={sh.emp_e_pct ?? emp.e_pct} onChange={(v) => set({ emp_e_pct: v })} min={emp.e_range[0]} max={emp.e_range[1]} step={1} unit="%" />
            </div>
          ) : <Note className="mt-8">This material has no entry in the empirical model, so the analytical formula is used for it.</Note>)}
        </>}
      </div>

      <div className="section">
        <Eyebrow>Construction</Eyebrow>
        {!wires && <SliderField label="Coverage" value={sh.coverage_pct} onChange={(v) => set({ coverage_pct: v })} min={30} max={100} step={1} unit="%"
                     help="The share of the surface that is actually sheet. Below 100% the shield is built from panels with real gaps: use it for windows, doors and unclad strips." />}
        <div className="col gap-12 mt-12">
          <Switch checked={sh.grounded} onChange={(v) => set({ grounded: v })} label="Earthed" />
          <Switch checked={sh.bonded} onChange={(v) => set({ bonded: v })} label={wires ? 'Bonded at both ends (closed loop)' : 'Bonded seams'} />
          {!wires && <Switch checked={!!isMesh} onChange={(v) => set({ mesh: v })} disabled={!!preset.mesh} label="Mesh / perforated" />}
        </div>
        {isMesh && !wires && (
          <div className="fields-2 mt-8">
            <Field label="Aperture"><NumberInput value={sh.aperture_mm} onChange={(v) => set({ aperture_mm: v })} min={0.5} max={200} step={0.5} unit="mm" /></Field>
            <Field label="Pitch"><NumberInput value={sh.pitch_mm} onChange={(v) => set({ pitch_mm: v })} min={1} max={400} step={0.5} unit="mm" /></Field>
          </div>
        )}
        {closed && sh.coverage_pct >= 99.5 && sh.bonded && !isMesh && sh.model === 'physical' && (
          <Note className="mt-8">This is an ideal shell: continuous sheet, every seam bonded, no openings. A real building has doors, windows and service entries, and they decide the result. Lower the coverage or switch off bonded seams to see how much.</Note>
        )}
        <p className="help small muted mt-8"><Info size={11} style={{ verticalAlign: -1 }} /> {wires ? 'Without bonding at both ends there is no closed loop, so no compensating current can flow.' : 'An unearthed shield screens the electric field less and picks up an induced voltage. Unbonded seams stop eddy currents circulating from panel to panel.'}</p>
      </div>
      {off && <p className="small muted mt-12">The shield is off. You can design it here and switch it on when ready.</p>}
    </>
  );
}

/**
 * Custom layout: every plate is a straight sheet seen end-on, from (x1, y1) to (x2, y2)
 * in the cross-section, running along the line for the given length.
 */
function PlateEditor({ plates, onChange, length, z, span, onLength, onZ, buildingZ, buildingName }: {
  plates: number[][]; onChange: (p: number[][]) => void; length: number; z: number; span: number;
  onLength: (v: number) => void; onZ: (v: number) => void; buildingZ: number | null; buildingName: string;
}) {
  const MAX = 16;
  const edit = (i: number, k: number, v: number) => onChange(plates.map((p, j) => (j === i ? p.map((c, m) => (m === k ? v : c)) : p)));
  const add = () => {
    const last = plates[plates.length - 1];
    // continue from the end of the last plate, so a run of plates joins up
    onChange([...plates, last ? [last[2], last[3], last[2] + 5, last[3]] : [20, 0, 20, 10]]);
  };
  const cols = { display: 'grid', gridTemplateColumns: '14px repeat(4, minmax(0, 1fr)) 26px', gap: 4, alignItems: 'center' } as const;
  return (
    <>
      <p className="help small muted" style={{ marginTop: 0 }}>Place the sheets yourself. Each plate is seen end-on, from (x₁, y₁) to (x₂, y₂): x is the distance from the line's centreline (negative = left of it), y the height above ground.</p>
      <div style={cols} className="tiny muted mt-8"><span /><span>x₁ (m)</span><span>y₁ (m)</span><span>x₂ (m)</span><span>y₂ (m)</span><span /></div>
      {plates.map((p, i) => (
        <div key={i} style={{ ...cols, marginTop: 4 }}>
          <span className="tiny muted mono">{i + 1}</span>
          <NumberInput value={p[0]} onChange={(v) => edit(i, 0, v)} min={-500} max={500} step={0.5} />
          <NumberInput value={p[1]} onChange={(v) => edit(i, 1, v)} min={0} max={200} step={0.5} />
          <NumberInput value={p[2]} onChange={(v) => edit(i, 2, v)} min={-500} max={500} step={0.5} />
          <NumberInput value={p[3]} onChange={(v) => edit(i, 3, v)} min={0} max={200} step={0.5} />
          <Button size="sm" variant="ghost" icon onClick={() => onChange(plates.filter((_, j) => j !== i))} aria-label={`Remove plate ${i + 1}`}><Trash2 size={12} /></Button>
        </div>
      ))}
      {!plates.length && <p className="small muted mt-8">No plates yet.</p>}
      <div className="row mt-8">
        <Button size="sm" onClick={add} disabled={plates.length >= MAX} title={plates.length >= MAX ? `Up to ${MAX} plates` : 'Add a plate starting where the last one ends'}><Plus size={12} />Add plate</Button>
        {plates.length > 0 && <Button size="sm" variant="ghost" onClick={() => onChange([])}>Clear</Button>}
      </div>
      <SliderField label="Length along the line" value={length} onChange={onLength} min={2} max={Math.max(60, span)} step={1} unit="m" />
      <div className="fields-2 mt-8" style={{ alignItems: 'start' }}>
        <Field label="Centre along the line (z)"><NumberInput value={z} onChange={onZ} min={-1000} max={1000} step={1} unit="m" /></Field>
        {buildingZ !== null && <Button size="sm" style={{ marginTop: 22 }} disabled={Math.abs(z - buildingZ) < 1e-6} onClick={() => onZ(buildingZ)} title={`Centre the plates on ${buildingName}`}>At the building</Button>}
      </div>
      <p className="help small muted mt-8">Plates that touch are drawn as one shape. With “Bonded seams” on, all the plates act as one circuit; off, each is on its own. Keep them clear of the live conductors.</p>
    </>
  );
}

// -------------------------------------------------------------- Standards
function StandardsPanel() {
  const config = useStore((s) => s.config)!;
  const lib = useStore((s) => s.library)!;
  const setConfig = useStore((s) => s.setConfig);
  const f60 = config.corridor.freq_hz >= 55;
  const toggle = (id: string) => setConfig((c) => {
    c.standards = c.standards.includes(id) ? c.standards.filter((s) => s !== id) : [...c.standards, id];
  });
  const groups: [string, string, (s: (typeof lib.standards)[number]) => boolean][] = [
    ['Exposure limits · general public', 'Reference levels and legal limits.', (s) => s.kind === 'limit' && s.population === 'general public'],
    ['Precautionary values', 'Stricter planning or attention values. Exceeding one is a planning flag, not a breach of an exposure limit.', (s) => s.kind === 'precautionary'],
    ['Occupational', 'For workers under a managed exposure regime only.', (s) => s.population === 'occupational'],
  ];
  return (
    <>
      {groups.map(([title, help, pick]) => (
        <div className="section" key={title}>
          <Eyebrow>{title}</Eyebrow>
          <p className="small muted">{help}</p>
          <div className="col gap-4">
            {lib.standards.filter(pick).map((s) => {
              const on = config.standards.includes(s.id);
              const b = f60 ? s.b60 : s.b50, e = f60 ? s.e60 : s.e50;
              return (
                <label key={s.id} className={cx('mat-item', on && 'on')} style={{ alignItems: 'flex-start', cursor: 'pointer' }} title={s.notes}>
                  <input type="checkbox" checked={on} onChange={() => toggle(s.id)} style={{ marginTop: 3 }} />
                  <span style={{ minWidth: 0 }}>
                    <span style={{ fontWeight: 600 }}>{s.name}</span>
                    <span className="mono tiny muted" style={{ display: 'block' }}>
                      B {b === null ? '—' : `${fmt(b, 3)} µT`} · E {e === null ? '—' : `${fmt(e, 3)} kV/m`}{s.needs_verification ? ' · verify' : ''}
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      ))}
      <div className="section">
        <p className="small muted">Limits are shown at {config.corridor.freq_hz} Hz. Several fall with frequency. Compliance always uses the unshielded peak field. Entries marked “verify” were transcribed from secondary sources: check the primary document before certifying.</p>
        {config.standards.length === 0 && <Note kind="bad">Select at least one standard to assess compliance.</Note>}
      </div>
    </>
  );
}
