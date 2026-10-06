// 3-D digital twin page: toolbar, the WebGL stage with its overlays, the
// section / iso controls, and the list of pinned points.

import { useEffect, useMemo, useRef, useState } from 'react';
import { Camera, Check, ChevronDown, ChevronUp, Crosshair, Layers as LayersIcon, Maximize2, RotateCcw, Trash2 } from 'lucide-react';
import { Button, ColorBar, MenuButton, NumberInput, Segmented, Spinner } from '@/components/ui';
import { fmt } from '@/lib/format';
import { useDebounced, useRemote } from '@/lib/hooks';
import { useStore } from '@/lib/store';
import type { PointRow } from '@/lib/types';
import { rampCss } from '@/lib/colors';
import { OVER, type Quantity, type ScaleMode, type View } from '@/twin/fieldTex';
import { scaleFor, TwinScene, type HoverInfo, type LayerKey, type TwinData, type TwinOptions, type TwinSection, type TwinVolume, type ViewName } from '@/twin/TwinScene';
import { PointsTable } from './MeasurePage';

const LAYERS: [LayerKey, string, string][] = [
  ['ground', 'Ground map', 'Field at the measurement height, drawn on the ground along the whole span'],
  ['section', 'Section', 'Field in a vertical plane across the corridor; move it with the slider'],
  ['contours', 'Contours', 'Iso-lines on the maps: the limit (red), your iso level (violet) and round values'],
  ['glow', 'Field glow', 'Volume rendering of the field around the conductors'],
  ['iso', 'Iso-surface', '3-D surface where the field equals the iso level'],
  ['lines', 'Lines', 'Towers, insulators and conductors'],
  ['buildings', 'Buildings', 'Buildings and their receptor points'],
  ['shield', 'Shield', 'The shielding structure'],
  ['row', 'ROW', 'Right-of-way band'],
  ['labels', 'Labels', 'Names and values in the scene'],
];

const DEFAULT_LAYERS: Record<LayerKey, boolean> = { ground: true, section: true, contours: true, glow: false, iso: false, lines: true, buildings: true, shield: true, row: true, labels: true };

function loadPrefs(): Partial<{ layers: Record<LayerKey, boolean>; scale: ScaleMode; glow: number }> {
  try { return JSON.parse(localStorage.getItem('taki.twin') || '{}'); } catch { return {}; }
}

export default function TwinPage() {
  const config = useStore((s) => s.config)!;
  const sol = useStore((s) => s.sol);
  const theme = useStore((s) => s.theme);
  const setConfig = useStore((s) => s.setConfig);
  const setPins = useStore((s) => s.setPins);
  const setTwinShot = useStore((s) => s.setTwinShot);
  const twinShot = useStore((s) => s.twinShot);
  const toast = useStore((s) => s.toast);

  const prefs = useMemo(loadPrefs, []);
  const [quantity, setQuantity] = useState<Quantity>('B');
  const [view, setView] = useState<View>('with');
  const [scale, setScale] = useState<ScaleMode>(prefs.scale ?? 'peak');
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({ ...DEFAULT_LAYERS, ...(prefs.layers ?? {}) });
  const [sectionZ, setSectionZ] = useState<number | null>(null);
  const [glow, setGlow] = useState(prefs.glow ?? 0.5);
  const [isoE, setIsoE] = useState(1);
  const [failed, setFailed] = useState<string | null>(null);
  const [showPins, setShowPins] = useState(true);
  const [legendOpen, setLegendOpen] = useState(() => window.innerHeight > 860);
  const [, force] = useState(0);

  const host = useRef<HTMLDivElement>(null);
  const overlay = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const tip = useRef<HTMLDivElement>(null);
  const tw = useRef<TwinScene | null>(null);

  const scene = useRemote<TwinData>('/twin', {}, { delay: 160 });
  const d = scene.data;
  const z = sectionZ ?? d?.zc_default ?? 0;
  const zDeb = useDebounced(z, 110);
  const section = useRemote<TwinSection>('/twin/section', { z: +zDeb.toFixed(1) }, { enabled: layers.section, delay: 40 });
  const volume = useRemote<TwinVolume>('/twin/volume', {}, { enabled: layers.glow || layers.iso, delay: 200 });
  const pts = useRemote<{ rows: PointRow[] }>('/points', {}, { withPoints: true, delay: 120 });

  const shieldOn = !!d?.shield.on;
  const effView: View = shieldOn ? view : 'without';
  const isoLevel = quantity === 'B' ? config.twin.iso_level_uT : isoE;
  const opts: TwinOptions = useMemo(() => ({ quantity, view: effView, scale, layers, sectionZ: z, isoLevel, glow }), [quantity, effView, scale, layers, z, isoLevel, glow]);
  const optsRef = useRef(opts); optsRef.current = opts;

  useEffect(() => { try { localStorage.setItem('taki.twin', JSON.stringify({ layers, scale, glow })); } catch { /* ignore */ } }, [layers, scale, glow]);

  // create the scene once
  useEffect(() => {
    if (!host.current || !overlay.current) return;
    let t: TwinScene;
    try { t = new TwinScene(host.current, overlay.current, optsRef.current, useStore.getState().theme === 'dark'); }
    catch (e: any) { setFailed(e?.message || 'WebGL is not available in this browser.'); return; }
    tw.current = t;
    t.onPick = (p) => {
      const st = useStore.getState();
      const pins = st.config?.points ?? [];
      st.setPins([...pins, { x: p.x, y: p.y, z: p.z, label: p.where === 'building' ? 'on building' : '' }]);
    };
    t.onHover = (h) => showTip(h);
    return () => { t.dispose(); tw.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { if (d && tw.current) { tw.current.setData(d); force((n) => n + 1); } }, [d]);
  useEffect(() => { if (section.data && tw.current && d && section.data.hash === d.hash) { tw.current.setSection(section.data); force((n) => n + 1); } }, [section.data, d]);
  useEffect(() => { if (tw.current) tw.current.setVolume(volume.data && d && volume.data.hash === d.hash ? volume.data : null); }, [volume.data, d]);
  useEffect(() => { tw.current?.setOptions(opts); }, [opts]);
  useEffect(() => { tw.current?.setPins(pts.data?.rows ?? []); }, [pts.data, quantity]);
  useEffect(() => { tw.current?.setTheme(theme === 'dark'); }, [theme]);

  const showTip = (h: HoverInfo | null) => {
    const el = tip.current, st = stage.current;
    if (!el || !st) return;
    if (!h) { el.style.display = 'none'; return; }
    const r = st.getBoundingClientRect();
    const o = optsRef.current;
    const unit = o.quantity === 'B' ? 'µT' : 'kV/m';
    const v0 = o.quantity === 'B' ? h.b0 : h.e0, vS = o.quantity === 'B' ? h.bS : h.eS;
    const other0 = o.quantity === 'B' ? h.e0 : h.b0, otherU = o.quantity === 'B' ? 'kV/m' : 'µT';
    let html = `<div style="color:var(--steel)">x ${h.x.toFixed(1)} · y ${h.y.toFixed(1)} · z ${h.z.toFixed(1)} m</div>`;
    if (v0 !== null && vS !== null) {
      html += `<div><b>${o.quantity} ${fmt(v0)} ${unit}</b>${h.shielded && Math.abs(vS - v0) > 1e-4 * v0 ? ` → <span style="color:var(--teal)">${fmt(vS)}</span> <span style="color:var(--steel)">(${vS <= v0 ? '−' : '+'}${Math.abs(100 * (1 - vS / v0)).toFixed(0)}%)</span>` : ''}</div>`;
      if (other0 !== null) html += `<div style="color:var(--steel)">${o.quantity === 'B' ? 'E' : 'B'} ${fmt(other0)} ${otherU}</div>`;
    } else {
      html += `<div style="color:var(--steel)">${h.where === 'building' ? 'on the building' : 'section updating…'}</div>`;
    }
    html += `<div style="color:var(--steel);font-family:var(--font-ui)">click to pin${v0 === null ? ' and read the exact value' : ''}</div>`;
    el.innerHTML = html;
    el.style.display = 'block';
    // beside the pointer, kept inside the stage and off the key and the info box
    const tw = el.offsetWidth || 220, th = el.offsetHeight || 80;
    const px = h.clientX - r.left, py = h.clientY - r.top;
    const spots: [number, number][] = [[px + 14, py + 14], [px - tw - 14, py + 14], [px + 14, py - th - 14], [px - tw - 14, py - th - 14]];
    const blocked = [...st.querySelectorAll<HTMLElement>('.twin-legend, .twin-info')].map((n) => n.getBoundingClientRect());
    const clear = ([x, y]: [number, number]) => x >= 4 && y >= 4 && x + tw <= r.width - 4 && y + th <= r.height - 4
      && !blocked.some((b) => x + r.left < b.right && x + r.left + tw > b.left && y + r.top < b.bottom && y + r.top + th > b.top);
    const [x, y] = spots.find(clear) ?? [Math.max(4, Math.min(px + 14, r.width - tw - 4)), Math.max(4, Math.min(py + 14, r.height - th - 4))];
    el.style.left = `${x}px`;
    el.style.top = `${y}px`;
  };

  const capture = () => {
    if (!tw.current) return;
    try { setTwinShot(tw.current.capture()); toast('Captured this view. It will be included in the report.'); }
    catch { toast('Could not capture the view.', 'error'); }
  };
  const fullscreen = () => { const el = stage.current; if (!el) return; if (document.fullscreenElement) void document.exitFullscreen(); else void el.requestFullscreen?.(); };
  const go = (v: ViewName) => tw.current?.setView(v);
  const toggle = (k: LayerKey) => setLayers((l) => ({ ...l, [k]: !l[k] }));

  // legend numbers
  const unit = quantity === 'B' ? 'µT' : 'kV/m';
  const limit = d ? (quantity === 'B' ? d.limits.b : d.limits.e) : null;
  const peak = tw.current?.getGroundPeak(quantity) || (d ? (quantity === 'B' ? d.peak_b : d.peak_e) : 0);
  const sc = scaleFor(peak, limit, scale, tw.current?.getSectionMax(quantity) ?? null);
  const span = d?.span ?? 150;
  const rows = pts.data?.rows ?? [];

  if (failed) {
    return (
      <div className="page flush"><div className="twin-fallback"><div>
        <h3>The 3-D view could not start</h3>
        <p className="small mt-8">{failed}</p>
        <p className="small">Every result is still available on the Field map, Lateral profile and Measure points pages. The 3-D twin needs WebGL 2, which most browsers have switched on by default.</p>
      </div></div></div>
    );
  }

  return (
    <div className="page flush">
      <div className="twin">
        <div className="twin-bar">
          <div className="grp"><span className="lbl">Field</span>
            <Segmented size="sm" value={quantity} onChange={setQuantity} options={[{ value: 'B', label: 'Magnetic B' }, { value: 'E', label: 'Electric E' }]} /></div>
          <div className="grp" title="What the colours on the ground and on the section stand for"><span className="lbl">Colours show</span>
            <Segmented size="sm" value={effView} onChange={setView} options={[
              { value: 'without', label: 'Field, no shield', title: 'The field as it is without any shield' },
              { value: 'with', label: 'Field, with shield', disabled: !shieldOn, title: shieldOn ? 'The field with the shield in place' : 'Switch a shield on in the inputs first' },
              { value: 'diff', label: 'What the shield changes', disabled: !shieldOn, title: 'Not a field value: where the shield lowers the field (teal) and where it raises it (red), in percent' },
            ]} /></div>
          <div className="grp"><span className="lbl">Scale</span>
            <Segmented size="sm" value={scale} onChange={setScale} options={[
              { value: 'peak', label: 'Peak', title: 'Colours span 0 to the ground-level peak' },
              { value: 'limit', label: 'Limit', disabled: !limit, title: limit ? 'Colours span 0 to the tightest selected limit' : 'No limit selected for this field' },
              { value: 'log', label: 'Log', title: 'Three decades, logarithmic' },
            ]} /></div>
          <div className="grp"><span className="lbl">View</span>
            <div className="seg sm">
              <button onClick={() => go('iso')}>3-D</button><button onClick={() => go('front')} title="Looking along the line">Front</button>
              <button onClick={() => go('side')} title="Looking across the line">Side</button><button onClick={() => go('top')} title="Plan view">Top</button>
            </div>
            <Button size="sm" variant="ghost" icon onClick={() => go('iso')} title="Reset the camera" aria-label="Reset the camera"><RotateCcw size={14} /></Button>
          </div>
          <MenuButton align="left" button={(_o, toggleMenu) => (
            <Button size="sm" onClick={toggleMenu} title="Choose what is drawn"><LayersIcon size={13} />Layers · {LAYERS.filter(([k]) => layers[k]).length}/{LAYERS.length}<ChevronDown size={12} /></Button>
          )}>{() => (<>
            <div className="head"><b>What is drawn</b>Tick to show, untick to hide.</div>
            {LAYERS.map(([k, label, title]) => (
              <button key={k} onClick={() => toggle(k)} role="menuitemcheckbox" aria-checked={layers[k]} style={{ alignItems: 'flex-start' }}>
                <span style={{ width: 14, flex: 'none', marginTop: 2 }}>{layers[k] && <Check size={13} />}</span>
                <span>{label}<span className="tiny muted" style={{ display: 'block', maxWidth: 250, whiteSpace: 'normal' }}>{title}</span></span>
              </button>
            ))}
          </>)}</MenuButton>
          <span className="grow" />
          <Button size="sm" onClick={capture} title="Save this view for the report"><Camera size={13} />{twinShot ? 'Re-capture' : 'Capture for report'}</Button>
          <Button size="sm" variant="ghost" icon onClick={fullscreen} title="Full screen" aria-label="Full screen"><Maximize2 size={14} /></Button>
        </div>

        <div className="twin-stage" ref={stage}>
          <div ref={host} style={{ position: 'absolute', inset: 0 }} />
          <div ref={overlay} className="twin-labels" />
          {d && (
            <div className="twin-overlay twin-info">
              <b>{d.lines.length} line{d.lines.length === 1 ? '' : 's'} · {(2 * d.span).toFixed(0)} m span · {d.ground_short}</b><br />
              <b>Colours:</b> {effView === 'diff' ? `what the shield changes in ${quantity}, in percent (teal = lower, red = higher).` : `the ${quantity === 'B' ? 'magnetic' : 'electric'} field ${effView === 'with' ? 'with the shield in place' : shieldOn ? 'as it is without the shield' : '(no shield is switched on)'}.`}{' '}
              Ground map: {quantity} at {d.meas_height} m above ground along the span, strongest at mid-span where the conductors hang lowest.
              {layers.section && <> Section: {quantity} in the plane z = {z.toFixed(0)} m.</>}
              {shieldOn && effView !== 'without' && <> Shield acts over z = {(d.shield.zc - d.shield.zh).toFixed(0)}…{(d.shield.zc + d.shield.zh).toFixed(0)} m.</>}
            </div>
          )}
          {d && (
            <div className="twin-overlay twin-legend">
              {effView === 'diff'
                ? <ColorBar diff dark={theme === 'dark'} lo="−70% lower" hi="+70% higher" label={`Change in ${quantity} from the shield`} />
                : <ColorBar lo={scale === 'log' ? fmt(sc.max / 1000) : '0'} hi={fmt(sc.max)} unit={unit} label={`${quantity === 'B' ? 'Magnetic flux density' : 'Electric field'} (RMS)`} />}
              {effView !== 'diff' && scale !== 'log' && (
                <div className="colorbar mt-4" title="Values above the top of the scale, mostly close to the conductors">
                  <div className="legend-bar" style={{ background: rampCss(OVER), height: 6 }} />
                  <div className="ends"><span>above scale ×1</span><span>×100</span></div>
                </div>
              )}
              {effView !== 'diff' && <div className="tiny muted mt-4">{sc.basis === 'limit' ? `Top of scale = limit. Peak is ${limit ? ((100 * peak) / limit).toFixed(peak / (limit || 1) < 0.1 ? 1 : 0) : '—'}% of it.` : sc.basis === 'log' ? 'Logarithmic, three decades.' : `Top of scale = ground-level peak${limit ? ` (${((100 * peak) / limit).toFixed(peak / limit < 0.1 ? 1 : 0)}% of the limit)` : ''}.`}</div>}
              <button type="button" className="lg-toggle" onClick={() => setLegendOpen((o) => !o)}>{legendOpen ? 'Hide the key' : 'Show the key'}</button>
              {legendOpen && <>
              {layers.contours && effView !== 'diff' && <>
                {limit ? <div className="lg-row"><span className="lg-line" style={{ borderColor: 'var(--red)' }} />Limit {fmt(limit)} {unit}{peak < limit ? ' (not reached at ground)' : ''}</div> : null}
                <div className="lg-row"><span className="lg-line" style={{ borderColor: 'var(--violet)' }} />Iso level {fmt(isoLevel)} {unit}</div>
              </>}
              {layers.lines && <div className="lg-row">
                {(['A', 'B', 'C'] as const).map((p) => <span key={p} className="row gap-4"><span className="lg-line" style={{ borderColor: `var(--phase-${p.toLowerCase()})` }} />{p}</span>)}
                <span>phases</span>
              </div>}
              {shieldOn && layers.shield && <div className="lg-row"><span className="lg-box" style={{ background: 'color-mix(in srgb, var(--teal) 45%, transparent)', border: '1px solid var(--teal-bright)' }} />Shield{d.shield.mesh ? ' (mesh)' : ''}</div>}
              {layers.row && <div className="lg-row"><span className="lg-box" style={{ background: 'var(--blue-tint)', border: '1px dashed var(--blue)' }} />Right-of-way ±{d.row} m</div>}
              <div className="lg-row"><span className="swatch" style={{ background: 'var(--violet)' }} />Pinned point · <span className="swatch" style={{ background: 'var(--blue-bright)' }} /> receptor</div>
              </>}
            </div>
          )}
          <div className="twin-overlay twin-hint">Drag to orbit · scroll to zoom · right-drag to pan · click the ground, the section or a building to pin a point</div>
          <div ref={tip} className="twin-overlay twin-tip" />
          {!d && <div className="twin-load"><Spinner />{scene.error ?? 'Building the site…'}</div>}
          {d && (scene.loading || (layers.section && section.loading) || ((layers.glow || layers.iso) && volume.loading && !volume.data)) && <div className="busy-bar" />}
        </div>

        <div className="twin-foot">
          <div className="ctl" title="Position of the field section along the line (0 = mid-span)">
            <span className="lbl">Section z</span>
            <input type="range" min={-span} max={span} step={Math.max(1, Math.round(span / 40))} value={z} disabled={!layers.section} onChange={(e) => setSectionZ(parseFloat(e.target.value))} aria-label="Section position" />
            <b>{z > 0 ? '+' : z < 0 ? '−' : ''}{Math.abs(z).toFixed(0)} m</b>
            <Button size="sm" variant="ghost" onClick={() => setSectionZ(0)} disabled={!layers.section}>Mid-span</Button>
            {d && d.buildings.length > 0 && <Button size="sm" variant="ghost" disabled={!layers.section} onClick={() => setSectionZ(Math.max(-span, Math.min(span, d.buildings[0].z)))}>At building</Button>}
          </div>
          <div className="row" title="Level drawn as the violet contour and as the 3-D iso-surface">
            <span className="lbl">Iso level</span>
            <div style={{ width: 104 }}>
              {quantity === 'B'
                ? <NumberInput value={config.twin.iso_level_uT} min={0.01} max={5000} step={0.1} unit="µT" onChange={(v) => setConfig((c) => { c.twin.iso_level_uT = v; }, { history: false })} />
                : <NumberInput value={isoE} min={0.001} max={500} step={0.1} unit="kV/m" onChange={setIsoE} />}
            </div>
            {limit ? <Button size="sm" variant="ghost" onClick={() => (quantity === 'B' ? setConfig((c) => { c.twin.iso_level_uT = limit; }, { history: false }) : setIsoE(limit))}>= limit</Button> : null}
          </div>
          {layers.glow && (
            <div className="row" style={{ minWidth: 190 }}>
              <span className="lbl">Glow</span>
              <input type="range" min={0} max={1} step={0.05} value={glow} onChange={(e) => setGlow(parseFloat(e.target.value))} aria-label="Glow strength" />
            </div>
          )}
          <Button size="sm" variant="ghost" onClick={() => setShowPins((s) => !s)}><Crosshair size={13} />{rows.length} point{rows.length === 1 ? '' : 's'}{showPins ? <ChevronDown size={13} /> : <ChevronUp size={13} />}</Button>
          {rows.length > 0 && <Button size="sm" variant="ghost" onClick={() => setPins([])} title="Remove every pinned point"><Trash2 size={13} />Clear</Button>}
        </div>

        {showPins && rows.length > 0 && (
          <div className="twin-pins">
            <PointsTable rows={rows} onRemove={(i) => setPins(config.points.filter((_, k) => k !== i))} onLabel={(i, l) => setPins(config.points.map((p, k) => (k === i ? { ...p, label: l } : p)))} />
          </div>
        )}
        {sol?.shield.no_geometry && <div className="note" style={{ borderRadius: 0 }}>The shield is switched on but this configuration needs a building to attach to, so nothing is drawn.</div>}
      </div>
    </div>
  );
}
