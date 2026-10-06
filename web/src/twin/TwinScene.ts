// The 3-D digital twin: a three.js scene of the corridor (towers, sagging
// conductors, buildings, shield, right-of-way) with the computed field drawn
// on the ground, on a movable section plane, and as a volume. Every value
// comes from the server; this class only draws and interpolates.

import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';
import { LineSegments2 } from 'three/examples/jsm/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/examples/jsm/lines/LineSegmentsGeometry.js';
import { b64f32, b64u8 } from '@/lib/decode';
import type { LineOut, PointRow, ShieldOut } from '@/lib/types';
import { buildBuilding, buildShield, buildTower, conductorPaths, palette, towerHeights, type Palette, type TowerParts, type TwinBuilding } from './builders';
import { maxOf, niceLevels, paintField, sample, type Contour, type Quantity, type ScaleMode, type View } from './fieldTex';
import { encodeLevel, glowMaterial, isoMaterial, rawColor, volumeTexture } from './volume';

export interface TwinData {
  hash: string; span: number; row: number; meas_height: number; freq: number; ground_short: string;
  x0: number; x1: number; y_top: number; lines: LineOut[]; buildings: TwinBuilding[]; shield: ShieldOut;
  limits: { b: number | null; e: number | null; name: string | null }; zc_default: number; peak_b: number; peak_e: number;
  ground: { nx: number; nz: number; z: number[]; B0: string; BS: string; E0: string; ES: string };
}
export interface TwinSection { hash: string; z: number; x0: number; x1: number; y0: number; y1: number; nx: number; ny: number; shield_here: boolean; B0: string; BS: string; E0: string; ES: string }
export interface TwinVolume { hash: string; nx: number; ny: number; nz: number; x0: number; x1: number; y0: number; y1: number; z0: number; z1: number; b_lo: number; b_hi: number; e_lo: number; e_hi: number; B0: string; BS: string; E0: string; ES: string }

export type LayerKey = 'ground' | 'section' | 'glow' | 'iso' | 'contours' | 'lines' | 'buildings' | 'shield' | 'row' | 'labels';
export interface TwinOptions {
  quantity: Quantity; view: View; scale: ScaleMode; layers: Record<LayerKey, boolean>;
  sectionZ: number; isoLevel: number; glow: number;
}
export type ViewName = 'iso' | 'front' | 'side' | 'top';

export interface HoverInfo {
  x: number; y: number; z: number; where: 'ground' | 'section' | 'building';
  b0: number | null; bS: number | null; e0: number | null; eS: number | null; shielded: boolean; clientX: number; clientY: number;
}

interface Decoded { nx: number; ny: number; B0: Float32Array; BS: Float32Array; E0: Float32Array; ES: Float32Array }
interface Label { el: HTMLDivElement; pos: THREE.Vector3; group: string }

const EXT_FRAC = 0.3;

export function scaleFor(peak: number, limit: number | null, mode: ScaleMode, sectionMax: number | null) {
  if (mode === 'limit' && limit) return { max: limit, decades: 3, basis: 'limit' as const };
  if (mode === 'log') return { max: Math.max(sectionMax ?? 0, peak * 30), decades: 3, basis: 'log' as const };
  return { max: peak > 0 ? peak : 1, decades: 3, basis: 'peak' as const };
}

function hexRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.replace('#', ''), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export class TwinScene {
  onHover: ((h: HoverInfo | null) => void) | null = null;
  onPick: ((p: { x: number; y: number; z: number; where: string }) => void) | null = null;

  private host: HTMLElement;
  private overlay: HTMLElement;
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera;
  private controls: OrbitControls;
  private pal: Palette;
  private dark: boolean;

  private staticGroup = new THREE.Group();
  private layerGroups: Partial<Record<LayerKey, THREE.Object3D[]>> = {};
  private pinGroup = new THREE.Group();
  private lineMats: LineMaterial[] = [];
  private pickables: THREE.Object3D[] = [];

  private data: TwinData | null = null;
  private ground: Decoded | null = null;
  private section: (Decoded & { z: number; x0: number; x1: number; y0: number; y1: number; shield: boolean }) | null = null;
  private vol: TwinVolume | null = null;
  private volTex: Partial<Record<'B0' | 'BS' | 'E0' | 'ES', THREE.Data3DTexture>> = {};
  private sectionMaxB: number | null = null;
  private sectionMaxE: number | null = null;

  private groundCanvas = document.createElement('canvas');
  private groundTex: THREE.CanvasTexture;
  private groundMesh: THREE.Mesh;
  private sectionCanvas = document.createElement('canvas');
  private sectionTex: THREE.CanvasTexture;
  private sectionMesh: THREE.Mesh;
  private sectionFrame: THREE.LineLoop;
  private glowMesh: THREE.Mesh;
  private isoMesh: THREE.Mesh;

  private opts: TwinOptions;
  private labels: Label[] = [];
  private pins: PointRow[] = [];
  private raf = 0;
  private dirty = true;
  private disposed = false;
  private ro: ResizeObserver;
  private pointer = { x: 0, y: 0, cx: 0, cy: 0, inside: false, moved: false, downX: 0, downY: 0, down: false };
  private tween: { t0: number; dur: number; p0: THREE.Vector3; p1: THREE.Vector3; q0: THREE.Vector3; q1: THREE.Vector3 } | null = null;
  private firstData = true;
  private sun: THREE.DirectionalLight;
  private hemi: THREE.HemisphereLight;

  constructor(host: HTMLElement, overlay: HTMLElement, opts: TwinOptions, dark: boolean) {
    this.host = host;
    this.overlay = overlay;
    this.opts = opts;
    this.dark = dark;
    this.pal = palette(dark);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    host.appendChild(this.renderer.domElement);

    this.camera = new THREE.PerspectiveCamera(36, 1, 0.5, 8000);
    this.camera.position.set(120, 80, 150);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.09;
    this.controls.maxPolarAngle = Math.PI / 2 - 0.015;
    this.controls.minDistance = 6;
    this.controls.maxDistance = 3000;
    this.controls.zoomToCursor = true;
    this.controls.addEventListener('change', () => { this.dirty = true; });
    this.controls.addEventListener('start', () => { this.tween = null; });

    this.hemi = new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.0);
    this.sun = new THREE.DirectionalLight(0xffffff, 1.7);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    this.sun.shadow.bias = -0.0004;
    this.sun.shadow.normalBias = 0.6;
    this.scene.add(this.hemi, this.sun, this.sun.target, this.staticGroup, this.pinGroup);

    // field surfaces (kept across rebuilds; re-shaped when the extents change)
    this.groundCanvas.width = 720; this.groundCanvas.height = 400;
    this.groundTex = new THREE.CanvasTexture(this.groundCanvas);
    this.sectionCanvas.width = 483; this.sectionCanvas.height = 243;
    this.sectionTex = new THREE.CanvasTexture(this.sectionCanvas);
    for (const t of [this.groundTex, this.sectionTex]) {
      t.colorSpace = THREE.SRGBColorSpace;
      t.minFilter = THREE.LinearFilter; t.magFilter = THREE.LinearFilter; t.generateMipmaps = false;
    }
    const quad = () => {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(12), 3));
      g.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 1], 2));
      g.setIndex([0, 1, 2, 0, 2, 3]);
      return g;
    };
    this.groundMesh = new THREE.Mesh(quad(), new THREE.MeshBasicMaterial({ map: this.groundTex, transparent: true, depthWrite: false, side: THREE.DoubleSide }));
    this.groundMesh.renderOrder = 2;
    this.sectionMesh = new THREE.Mesh(quad(), new THREE.MeshBasicMaterial({ map: this.sectionTex, transparent: true, depthWrite: false, side: THREE.DoubleSide }));
    this.sectionMesh.renderOrder = 4;
    const fg = new THREE.BufferGeometry();
    fg.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(12), 3));
    this.sectionFrame = new THREE.LineLoop(fg, new THREE.LineBasicMaterial({ color: this.pal.ink, transparent: true, opacity: 0.55 }));
    this.sectionFrame.renderOrder = 5;
    this.glowMesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), glowMaterial());
    this.glowMesh.renderOrder = 8;
    this.glowMesh.frustumCulled = false;
    this.isoMesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), isoMaterial());
    this.isoMesh.renderOrder = 7;
    this.isoMesh.frustumCulled = false;
    this.glowMesh.visible = this.isoMesh.visible = false;
    this.scene.add(this.groundMesh, this.sectionMesh, this.sectionFrame, this.isoMesh, this.glowMesh);

    const el = this.renderer.domElement;
    el.addEventListener('pointermove', this.onPointerMove);
    el.addEventListener('pointerdown', this.onPointerDown);
    el.addEventListener('pointerup', this.onPointerUp);
    el.addEventListener('pointerleave', this.onPointerLeave);
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(host);
    this.resize();
    this.loop();
  }

  // ------------------------------------------------------------------ data
  setData(d: TwinData) {
    const extentsChanged = !this.data || this.data.span !== d.span || this.data.x0 !== d.x0 || this.data.x1 !== d.x1;
    this.data = d;
    this.ground = { nx: d.ground.nx, ny: d.ground.nz, B0: b64f32(d.ground.B0), BS: b64f32(d.ground.BS), E0: b64f32(d.ground.E0), ES: b64f32(d.ground.ES) };
    this.rebuildStatic();
    this.placeFieldSurfaces();
    this.paintGround();
    this.applyVolume();
    this.applyLayers();
    if (this.firstData) { this.firstData = false; this.setView('iso', false); }
    else if (extentsChanged) this.setView('iso', true);
    this.dirty = true;
  }

  setSection(s: TwinSection) {
    this.section = { nx: s.nx, ny: s.ny, B0: b64f32(s.B0), BS: b64f32(s.BS), E0: b64f32(s.E0), ES: b64f32(s.ES), z: s.z, x0: s.x0, x1: s.x1, y0: s.y0, y1: s.y1, shield: s.shield_here };
    this.sectionMaxB = maxOf(this.section.B0);
    this.sectionMaxE = maxOf(this.section.E0);
    this.placeFieldSurfaces();
    this.paintSection();
    if (this.opts.scale === 'log') this.paintGround();
    this.applyLayers();
    this.dirty = true;
  }

  setVolume(v: TwinVolume | null) {
    for (const k of Object.keys(this.volTex) as (keyof typeof this.volTex)[]) this.volTex[k]?.dispose();
    this.volTex = {};
    this.vol = v;
    if (v) for (const k of ['B0', 'BS', 'E0', 'ES'] as const) this.volTex[k] = volumeTexture(b64u8(v[k]), v.nx, v.ny, v.nz);
    this.applyVolume();
    this.applyLayers();
    this.dirty = true;
  }

  setOptions(o: TwinOptions) {
    const p = this.opts;
    this.opts = o;
    const repaint = p.quantity !== o.quantity || p.view !== o.view || p.scale !== o.scale || p.isoLevel !== o.isoLevel || p.layers.contours !== o.layers.contours;
    if (repaint) { this.paintGround(); this.paintSection(); this.refreshBuildingLabels(); }
    if (p.sectionZ !== o.sectionZ) this.placeFieldSurfaces();
    this.applyVolume();
    this.applyLayers();
    this.dirty = true;
  }

  setPins(rows: PointRow[]) {
    this.pins = rows;
    this.rebuildPins();
    this.dirty = true;
  }

  setTheme(dark: boolean) {
    if (dark === this.dark) return;
    this.dark = dark;
    this.pal = palette(dark);
    (this.sectionFrame.material as THREE.LineBasicMaterial).color.set(this.pal.ink);
    if (this.data) { this.rebuildStatic(); this.paintGround(); this.paintSection(); this.applyVolume(); this.applyLayers(); this.rebuildPins(); }
    this.dirty = true;
  }

  getSectionMax(q: Quantity) { return q === 'B' ? this.sectionMaxB : this.sectionMaxE; }
  getGroundPeak(q: Quantity) { return this.ground ? maxOf(q === 'B' ? this.ground.B0 : this.ground.E0) : 0; }

  // ------------------------------------------------------------- the scene
  private clearStatic() {
    this.staticGroup.traverse((o) => {
      const m = o as THREE.Mesh;
      m.geometry?.dispose?.();
      const mats = Array.isArray(m.material) ? m.material : m.material ? [m.material] : [];
      for (const mt of mats) { (mt as any).map?.dispose?.(); mt.dispose(); }
    });
    this.staticGroup.clear();
    this.lineMats = [];
    this.pickables = [];
    this.layerGroups = {};
    for (const l of this.labels.filter((x) => x.group !== 'pin')) l.el.remove();
    this.labels = this.labels.filter((x) => x.group === 'pin');
  }

  private fat(positions: number[], color: string, width: number, opacity = 1): LineSegments2 | null {
    if (!positions.length) return null;
    const g = new LineSegmentsGeometry();
    g.setPositions(positions);
    const m = new LineMaterial({ color: new THREE.Color(color).getHex(), linewidth: width, transparent: opacity < 1, opacity, depthWrite: opacity >= 1 });
    m.resolution.set(this.host.clientWidth || 800, this.host.clientHeight || 600);
    this.lineMats.push(m);
    const l = new LineSegments2(g, m);
    l.frustumCulled = false;
    return l;
  }

  private addTo(layer: LayerKey, ...objs: (THREE.Object3D | null)[]) {
    for (const o of objs) {
      if (!o) continue;
      this.staticGroup.add(o);
      (this.layerGroups[layer] ??= []).push(o);
    }
  }

  private rebuildStatic() {
    const d = this.data!;
    const pal = this.pal;
    this.clearStatic();
    const span = d.span, ext = span * EXT_FRAC;
    const R = Math.max(span + ext, d.x1 - d.x0, 90);

    // lights follow the size of the site
    this.hemi.color.set(pal.dark ? '#8FA6C4' : '#FFFFFF');
    this.hemi.groundColor.set(pal.dark ? '#0B131D' : '#C9D3DA');
    this.hemi.intensity = pal.dark ? 0.9 : 1.15;
    this.sun.intensity = pal.dark ? 1.1 : 1.75;
    this.sun.position.set(-R * 0.55, R * 1.1, R * 0.75);
    this.sun.target.position.set(0, 0, 0);
    const sc = this.sun.shadow.camera;
    sc.left = -R * 1.2; sc.right = R * 1.2; sc.top = R * 1.2; sc.bottom = -R * 1.2; sc.near = 1; sc.far = R * 4;
    sc.updateProjectionMatrix();

    // ground and reference grid
    const groundMesh = new THREE.Mesh(new THREE.CircleGeometry(R * 5, 72), new THREE.MeshLambertMaterial({ color: pal.ground }));
    groundMesh.rotation.x = -Math.PI / 2;
    groundMesh.receiveShadow = true;
    this.staticGroup.add(groundMesh);
    const size = Math.ceil((R * 2.4) / 100) * 100;
    const minor = new THREE.GridHelper(size, size / 10, pal.grid, pal.grid);
    minor.position.y = 0.02;
    const major = new THREE.GridHelper(size, size / 50, pal.gridMajor, pal.gridMajor);
    major.position.y = 0.03;
    for (const gh of [minor, major]) { (gh.material as THREE.Material).transparent = true; (gh.material as THREE.Material).opacity = pal.dark ? 0.8 : 0.75; (gh.material as THREE.Material).depthWrite = false; }
    this.staticGroup.add(minor, major);
    this.scene.fog = new THREE.Fog(pal.dark ? '#111C2B' : '#EEF3F6', R * 3.2, R * 9);

    // right-of-way
    const rowGeo = new THREE.PlaneGeometry(2 * d.row, 2 * (span + ext));
    const row = new THREE.Mesh(rowGeo, new THREE.MeshBasicMaterial({ color: pal.row, transparent: true, opacity: pal.dark ? 0.1 : 0.07, depthWrite: false }));
    row.rotation.x = -Math.PI / 2;
    row.position.y = 0.05;
    row.renderOrder = 1;
    const rowEdges: number[] = [];
    for (const s of [-1, 1]) rowEdges.push(s * d.row, 0.08, -(span + ext), s * d.row, 0.08, span + ext);
    const eg = new THREE.BufferGeometry();
    eg.setAttribute('position', new THREE.Float32BufferAttribute(rowEdges, 3));
    const rowLine = new THREE.LineSegments(eg, new THREE.LineDashedMaterial({ color: pal.row, dashSize: 4, gapSize: 3, transparent: true, opacity: 0.75 }));
    rowLine.computeLineDistances();
    this.addTo('row', row, rowLine);

    // towers and conductors
    const parts: TowerParts = { lattice: [], arms: [], insul: [], meshes: [] };
    const KEYS = ['A', 'B', 'C', 'off'];
    const main: Record<string, number[]> = { A: [], B: [], C: [], off: [] }, stub: Record<string, number[]> = { A: [], B: [], C: [], off: [] };
    for (const ln of d.lines) {
      for (const z of [-span, span]) buildTower(ln, z, parts, pal);
      const p = conductorPaths(ln, span, ext);
      for (const k of KEYS) { main[k].push(...p.main[k]); stub[k].push(...p.stub[k]); }
    }
    this.addTo('lines', this.fat(parts.lattice, pal.steel, 1.25), this.fat(parts.arms, pal.pole, 3.2), this.fat(parts.insul, pal.insulator, 3.4), ...parts.meshes);
    const wire = (k: string) => (k === 'off' ? (pal.dark ? '#7C8896' : '#9AA3AA') : pal.phase[k]);   // out of service: grey
    for (const k of KEYS) this.addTo('lines', this.fat(main[k], wire(k), k === 'off' ? 1.6 : 2.3), this.fat(stub[k], wire(k), k === 'off' ? 1.2 : 1.6, 0.38));

    // buildings
    d.buildings.forEach((b, i) => {
      const g = buildBuilding(b, pal, i);
      if (d.shield.on && d.shield.room && i === d.shield.target_building) {
        // a shielded room is inside the building: make this one see-through so the room shows
        g.traverse((o) => {
          const m = o as THREE.Mesh;
          if (!m.isMesh) return;                       // keep the edge lines solid
          for (const mt of (Array.isArray(m.material) ? m.material : m.material ? [m.material] : []) as THREE.Material[]) {
            mt.transparent = true; mt.opacity = 0.2; mt.depthWrite = false;
          }
        });
      }
      this.addTo('buildings', g);
      g.traverse((o) => { if ((o as THREE.Mesh).isMesh) { o.userData.building = i; this.pickables.push(o); } });
      const probe = new THREE.Mesh(new THREE.SphereGeometry(0.55, 16, 12), new THREE.MeshBasicMaterial({ color: pal.dark ? '#4DA3FF' : '#0072B5', depthTest: false }));
      probe.position.set(b.probe[0], b.probe[1], b.probe[2]);
      probe.renderOrder = 9;
      this.addTo('buildings', probe);
    });

    // shield
    const shp = buildShield(d.shield, pal, span + ext);
    this.addTo('shield', shp.group, this.fat(shp.wires, pal.tealBright, 2.6), this.fat(shp.bonds, pal.teal, 2.0));

    this.buildLabels();
  }

  private buildLabels() {
    const d = this.data!;
    for (const ln of d.lines) {
      const h = towerHeights(ln);
      const live = ln.circuits.filter((k) => k.on);
      const kvs = [...new Set(live.map((k) => k.kv.toFixed(0)))];
      const what = ln.circuits.length > 1 && (ln.separate || kvs.length > 1 || live.length < ln.circuits.length)
        ? `${kvs.join('/') || '—'} kV · ${live.length} of ${ln.circuits.length} circuits live`
        : `${ln.kv.toFixed(0)} kV · ${ln.operating_a.toFixed(0)} A${ln.circuits.length > 1 ? ' per circuit' : ''}`;
      this.makeLabel(`<b>${esc(ln.name)}</b><span>${what}</span>`, 'line', new THREE.Vector3(ln.xc, h.top + 2, -d.span), 'static');
    }
    d.buildings.forEach((b, i) => this.makeLabel('', 'bldg', new THREE.Vector3(b.x0 + b.w / 2, b.h + 3.5, b.z), `b${i}`));
    this.refreshBuildingLabels();
    if (d.shield.on && d.shield.walls.length) {
      let x = 0, y = 0;
      for (const w of d.shield.walls) { x += (w[0] + w[2]) / 2; y = Math.max(y, w[1], w[3]); }
      if (d.shield.attached) y = -1.5;         // keep clear of the building's own label
      const what = d.shield.is_wire
        ? `<b>${d.shield.preset === 'passive-loop' ? 'Passive loop' : 'Screening wires'}</b><span>${d.shield.wires.length} × ${d.shield.wire_mm2} mm²${d.shield.loop_current_a ? ` · ${d.shield.loop_current_a.toFixed(0)} A` : ''}</span>`
        : `<b>${esc(d.shield.material.label.split(' (')[0])}${d.shield.layer2 ? ` + ${esc(d.shield.layer2.split(' (')[0])}` : ''}</b><span>${d.shield.thickness_mm.toFixed(d.shield.thickness_mm < 10 ? 1 : 0)} mm${d.shield.grounded ? ' · earthed' : ' · floating'}</span>`;
      this.makeLabel(what, 'shield',
        new THREE.Vector3(x / d.shield.walls.length, y + 1.5, Math.min(d.span, d.shield.zc + d.shield.zh)), 'static');
    }
    // lateral axis ticks along the near edge of the ground map
    const step = d.x1 - d.x0 > 220 ? 50 : d.x1 - d.x0 > 110 ? 20 : 10;
    for (let x = Math.ceil(d.x0 / step) * step; x <= d.x1 + 1e-6; x += step) {
      this.makeLabel(x === 0 ? '0 m' : `${x > 0 ? '+' : '−'}${Math.abs(x)}`, 'tick', new THREE.Vector3(x, 0, d.span + 4), 'static');
    }
    this.makeLabel(`ROW ±${d.row} m`, 'tick', new THREE.Vector3(d.row, 0, -d.span - 5), 'static');
  }

  private refreshBuildingLabels() {
    const d = this.data;
    if (!d) return;
    const q = this.opts.quantity, unit = q === 'B' ? 'µT' : 'kV/m';
    d.buildings.forEach((b, i) => {
      const l = this.labels.find((x) => x.group === `b${i}`);
      if (!l) return;
      // every building is labelled with the average over its inside, as on the other pages
      let v0 = q === 'B' ? b.b_in0 ?? b.b0 : b.e_in0 ?? b.e0, vS = q === 'B' ? b.b_inS ?? b.bS : b.e_inS ?? b.eS, what = 'inside ';
      const z = d.shield.on && i === d.shield.target_building ? d.shield.protected : null;
      if (z && d.shield.room) {                      // a shielded room is judged inside the room itself
        const s = q === 'B' ? z.b : z.e;
        v0 = s.avg0; vS = s.avgS; what = 'room ';
      }
      const changed = d.shield.on && Math.abs(vS - v0) > 1e-4 * Math.max(v0, 1e-9);
      const tiny = changed && vS < v0 * 1e-3;
      l.el.innerHTML = `<b>${esc(b.name)}</b><span>${what}${changed ? `${num(v0)} → <i>${tiny ? '≈ 0' : num(vS)}</i>` : num(v0)} ${unit}</span>`;
    });
  }

  private makeLabel(html: string, cls: string, pos: THREE.Vector3, group: string): Label {
    const el = document.createElement('div');
    el.className = `twin-label ${cls}`;
    el.innerHTML = html;
    this.overlay.appendChild(el);
    const l = { el, pos, group };
    this.labels.push(l);
    return l;
  }

  private rebuildPins() {
    this.pinGroup.traverse((o) => { const m = o as THREE.Mesh; m.geometry?.dispose?.(); (m.material as THREE.Material | undefined)?.dispose?.(); });
    this.pinGroup.clear();
    for (const l of this.labels.filter((x) => x.group === 'pin')) l.el.remove();
    this.labels = this.labels.filter((x) => x.group !== 'pin');
    const pal = this.pal;
    const stems: number[] = [];
    const q = this.opts.quantity;
    for (const r of this.pins) {
      const s = new THREE.Mesh(new THREE.SphereGeometry(0.75, 18, 14), new THREE.MeshBasicMaterial({ color: pal.violet, depthTest: false }));
      s.position.set(r.x, r.y, r.z);
      s.renderOrder = 10;
      this.pinGroup.add(s);
      stems.push(r.x, 0, r.z, r.x, r.y, r.z);
      const v0 = q === 'B' ? r.b0 : r.e0, vS = q === 'B' ? r.bS : r.eS;
      const changed = Math.abs(vS - v0) > 1e-4 * Math.max(v0, 1e-9);
      this.makeLabel(`<em>${r.n}</em><span>${changed ? `${num(v0)} → <i>${num(vS)}</i>` : num(v0)} ${q === 'B' ? 'µT' : 'kV/m'}</span>`, 'pin', new THREE.Vector3(r.x, r.y + 1.4, r.z), 'pin');
    }
    if (stems.length) {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(stems, 3));
      this.pinGroup.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: pal.violet, transparent: true, opacity: 0.7 })));
    }
    this.applyLayers();
  }

  // ---------------------------------------------------------------- fields
  private placeFieldSurfaces() {
    const d = this.data;
    if (!d) return;
    const g = this.groundMesh.geometry.getAttribute('position') as THREE.BufferAttribute;
    const y = 0.12;
    g.setXYZ(0, d.x0, y, -d.span); g.setXYZ(1, d.x1, y, -d.span); g.setXYZ(2, d.x1, y, d.span); g.setXYZ(3, d.x0, y, d.span);
    g.needsUpdate = true;
    this.groundMesh.geometry.computeBoundingSphere();
    const z = Math.max(-d.span, Math.min(d.span, this.opts.sectionZ));
    const y0 = this.section?.y0 ?? 0.3, y1 = this.section?.y1 ?? d.y_top;
    for (const geo of [this.sectionMesh.geometry, this.sectionFrame.geometry]) {
      const p = geo.getAttribute('position') as THREE.BufferAttribute;
      p.setXYZ(0, d.x0, y0, z); p.setXYZ(1, d.x1, y0, z); p.setXYZ(2, d.x1, y1, z); p.setXYZ(3, d.x0, y1, z);
      p.needsUpdate = true;
      geo.computeBoundingSphere();
    }
  }

  private contours(max: number, limit: number | null): Contour[] {
    if (!this.opts.layers.contours || this.opts.view === 'diff') return [];
    const pal = this.pal;
    const out: Contour[] = niceLevels(max / 200, max, 5).map((level) => ({ level, color: pal.dark ? [230, 237, 244] : [15, 27, 36], alpha: 0.42 }));
    if (limit) out.push({ level: limit, color: hexRgb(pal.red), bold: true });
    if (this.opts.isoLevel > 0) out.push({ level: this.opts.isoLevel, color: hexRgb(pal.violet), bold: true });
    return out;
  }

  private paintGround() {
    const d = this.data, g = this.ground;
    if (!d || !g) return;
    const q = this.opts.quantity;
    const a0 = q === 'B' ? g.B0 : g.E0, aS = q === 'B' ? g.BS : g.ES;
    const limit = q === 'B' ? d.limits.b : d.limits.e;
    const sc = scaleFor(maxOf(a0), limit, this.opts.scale, this.getSectionMax(q));
    const H = this.groundCanvas.height;
    const mask = new Uint8Array(H);
    if (d.shield.on) {
      for (let j = 0; j < H; j++) {
        const z = -d.span + (2 * d.span * (H - 1 - j)) / (H - 1);
        mask[j] = Math.abs(z - d.shield.zc) <= d.shield.zh + 1e-6 ? 1 : 0;
      }
    }
    paintField(this.groundCanvas, { nx: g.nx, ny: g.ny, a0, aS }, {
      view: this.opts.view, mode: this.opts.scale, max: sc.max, logDecades: sc.decades, dark: this.dark,
      alphaLo: 0.0, alphaHi: 0.9, contours: this.contours(sc.max, limit), rowMask: mask,
    });
    this.groundTex.needsUpdate = true;
  }

  private paintSection() {
    const d = this.data, s = this.section;
    if (!d || !s) return;
    const q = this.opts.quantity;
    const a0 = q === 'B' ? s.B0 : s.E0, aS = q === 'B' ? s.BS : s.ES;
    const limit = q === 'B' ? d.limits.b : d.limits.e;
    const sc = scaleFor(this.getGroundPeak(q), limit, this.opts.scale, this.getSectionMax(q));
    paintField(this.sectionCanvas, { nx: s.nx, ny: s.ny, a0, aS }, {
      view: this.opts.view, mode: this.opts.scale, max: sc.max, logDecades: sc.decades, dark: this.dark,
      alphaLo: 0.05, alphaHi: 0.8, contours: this.contours(sc.max, limit), shieldAll: true,
    });
    this.sectionTex.needsUpdate = true;
  }

  private applyVolume() {
    const d = this.data, v = this.vol;
    if (!d || !v) return;
    const q = this.opts.quantity;
    const lo = q === 'B' ? v.b_lo : v.e_lo, hi = q === 'B' ? v.b_hi : v.e_hi;
    const useShield = this.opts.view !== 'without' && d.shield.on ? 1 : 0;
    const peak = this.getGroundPeak(q) || hi / 100;
    for (const mesh of [this.glowMesh, this.isoMesh]) {
      mesh.scale.set(v.x1 - v.x0, v.y1 - v.y0, v.z1 - v.z0);
      mesh.position.set((v.x0 + v.x1) / 2, (v.y0 + v.y1) / 2, (v.z0 + v.z1) / 2);
      const u = (mesh.material as THREE.ShaderMaterial).uniforms;
      u.uVol0.value = this.volTex[q === 'B' ? 'B0' : 'E0'] ?? null;
      u.uVolS.value = this.volTex[q === 'B' ? 'BS' : 'ES'] ?? null;
      u.uMin.value.set(v.x0, v.y0, v.z0);
      u.uMax.value.set(v.x1, v.y1, v.z1);
      u.uDim.value.set(v.nx, v.ny, v.nz);
      u.uUseShield.value = useShield;
      u.uShieldZc.value = d.shield.zc;
      u.uShieldZh.value = d.shield.zh;
    }
    const gu = (this.glowMesh.material as THREE.ShaderMaterial).uniforms;
    gu.uT0.value = Math.max(0, encodeLevel(peak * 1.4, lo, hi));
    gu.uT1.value = Math.min(1, Math.max(gu.uT0.value + 0.08, encodeLevel(Math.min(hi, peak * 90), lo, hi)));
    gu.uStrength.value = 0.2 + 2.2 * this.opts.glow;
    gu.uColA.value.copy(rawColor(this.dark ? '#FFB454' : '#F29A2E'));
    gu.uColB.value.copy(rawColor(this.dark ? '#FFF6D6' : '#C53A1B'));
    const iu = (this.isoMesh.material as THREE.ShaderMaterial).uniforms;
    iu.uIso.value = encodeLevel(this.opts.isoLevel, lo, hi);
    iu.uIsoColor.value.copy(rawColor(this.pal.violet));
    iu.uOpacity.value = this.dark ? 0.42 : 0.46;
  }

  private applyLayers() {
    const L = this.opts.layers;
    for (const k of Object.keys(this.layerGroups) as LayerKey[]) for (const o of this.layerGroups[k] ?? []) o.visible = L[k];
    this.groundMesh.visible = L.ground && !!this.ground;
    this.sectionMesh.visible = this.sectionFrame.visible = L.section && !!this.section;
    const iso = (this.isoMesh.material as THREE.ShaderMaterial).uniforms.uIso.value;
    this.glowMesh.visible = L.glow && !!this.vol && !!this.volTex.B0;
    this.isoMesh.visible = L.iso && !!this.vol && !!this.volTex.B0 && iso > 0 && iso < 1;
    for (const l of this.labels) l.el.style.visibility = L.labels || l.group === 'pin' ? '' : 'hidden';
  }

  // ---------------------------------------------------------------- camera
  setView(name: ViewName, animate = true) {
    const d = this.data;
    if (!d) return;
    const D = Math.max(d.span * 1.7, (d.x1 - d.x0) * 1.3, 120);
    const cx = (d.x0 + d.x1) / 2;
    const top = Math.max(20, ...d.lines.map((l) => towerHeights(l).top));
    let p: THREE.Vector3, q: THREE.Vector3;
    if (name === 'front') { p = new THREE.Vector3(cx, top * 0.62, Math.max(d.span * 0.62, (d.x1 - d.x0) * 0.9)); q = new THREE.Vector3(cx, top * 0.4, 0); }
    else if (name === 'side') { p = new THREE.Vector3(d.x1 + D * 1.15, top * 1.1, 0.01); q = new THREE.Vector3(0, top * 0.35, 0); }
    else if (name === 'top') { p = new THREE.Vector3(cx, D * 2.25, 0.5); q = new THREE.Vector3(cx, 0, 0); }
    else { p = new THREE.Vector3(cx + D * 1.22, D * 0.56, D * 0.56); q = new THREE.Vector3(cx - D * 0.04, top * 0.2, 0); }
    if (!animate) {
      this.camera.position.copy(p); this.controls.target.copy(q); this.controls.update(); this.dirty = true;
      return;
    }
    this.tween = { t0: performance.now(), dur: 650, p0: this.camera.position.clone(), p1: p, q0: this.controls.target.clone(), q1: q };
  }

  resize() {
    const w = this.host.clientWidth, h = this.host.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    for (const m of this.lineMats) m.resolution.set(w, h);
    this.dirty = true;
  }

  // ------------------------------------------------------------ interaction
  private onPointerMove = (e: PointerEvent) => {
    const r = this.renderer.domElement.getBoundingClientRect();
    this.pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1;
    this.pointer.y = -((e.clientY - r.top) / r.height) * 2 + 1;
    this.pointer.cx = e.clientX; this.pointer.cy = e.clientY;
    this.pointer.inside = true; this.pointer.moved = true;
  };
  private onPointerDown = (e: PointerEvent) => { this.pointer.down = e.button === 0; this.pointer.downX = e.clientX; this.pointer.downY = e.clientY; };
  private onPointerUp = (e: PointerEvent) => {
    if (!this.pointer.down) return;
    this.pointer.down = false;
    if (Math.hypot(e.clientX - this.pointer.downX, e.clientY - this.pointer.downY) > 4) return;
    const h = this.probe();
    if (h && this.onPick) this.onPick({ x: +h.x.toFixed(2), y: +h.y.toFixed(2), z: +h.z.toFixed(2), where: h.where });
  };
  private onPointerLeave = () => { this.pointer.inside = false; this.onHover?.(null); };

  private raycaster = new THREE.Raycaster();
  private probe(): HoverInfo | null {
    const d = this.data, g = this.ground;
    if (!d || !g) return null;
    this.raycaster.setFromCamera(new THREE.Vector2(this.pointer.x, this.pointer.y), this.camera);
    const ray = this.raycaster.ray;
    let best: { dist: number; info: Omit<HoverInfo, 'clientX' | 'clientY'> } | null = null;
    const consider = (dist: number, info: Omit<HoverInfo, 'clientX' | 'clientY'>) => { if (!best || dist < best.dist) best = { dist, info }; };

    if (this.opts.layers.buildings && this.pickables.length) {
      const hit = this.raycaster.intersectObjects(this.pickables, false)[0];
      if (hit) consider(hit.distance, { x: hit.point.x, y: Math.max(0, hit.point.y), z: hit.point.z, where: 'building', b0: null, bS: null, e0: null, eS: null, shielded: false });
    }
    const s = this.section;
    const zs = Math.max(-d.span, Math.min(d.span, this.opts.sectionZ));
    if (this.opts.layers.section && s && Math.abs(ray.direction.z) > 1e-6) {
      const t = (zs - ray.origin.z) / ray.direction.z;
      if (t > 0) {
        const x = ray.origin.x + ray.direction.x * t, y = ray.origin.y + ray.direction.y * t;
        if (x >= s.x0 && x <= s.x1 && y >= s.y0 && y <= s.y1) {
          const fresh = Math.abs(s.z - zs) < 0.26;
          const fx = ((x - s.x0) / (s.x1 - s.x0)) * (s.nx - 1), fy = ((y - s.y0) / (s.y1 - s.y0)) * (s.ny - 1);
          consider(t, fresh
            ? { x, y, z: zs, where: 'section', b0: sample(s.B0, s.nx, s.ny, fx, fy), bS: sample(s.BS, s.nx, s.ny, fx, fy), e0: sample(s.E0, s.nx, s.ny, fx, fy), eS: sample(s.ES, s.nx, s.ny, fx, fy), shielded: s.shield }
            : { x, y, z: zs, where: 'section', b0: null, bS: null, e0: null, eS: null, shielded: false });
        }
      }
    }
    if (ray.direction.y < -1e-6) {
      const t = -ray.origin.y / ray.direction.y;
      const x = ray.origin.x + ray.direction.x * t, z = ray.origin.z + ray.direction.z * t;
      if (t > 0 && x >= d.x0 && x <= d.x1 && z >= -d.span && z <= d.span) {
        const fx = ((x - d.x0) / (d.x1 - d.x0)) * (g.nx - 1), fy = ((z + d.span) / (2 * d.span)) * (g.ny - 1);
        const sh = d.shield.on && Math.abs(z - d.shield.zc) <= d.shield.zh;
        const b0 = sample(g.B0, g.nx, g.ny, fx, fy), e0 = sample(g.E0, g.nx, g.ny, fx, fy);
        consider(t, { x, y: d.meas_height, z, where: 'ground', b0, bS: sh ? sample(g.BS, g.nx, g.ny, fx, fy) : b0, e0, eS: sh ? sample(g.ES, g.nx, g.ny, fx, fy) : e0, shielded: sh });
      }
    }
    const b = best as { dist: number; info: Omit<HoverInfo, 'clientX' | 'clientY'> } | null;
    return b ? { ...b.info, clientX: this.pointer.cx, clientY: this.pointer.cy } : null;
  }

  // ------------------------------------------------------------------ loop
  private loop = () => {
    if (this.disposed) return;
    this.raf = requestAnimationFrame(this.loop);
    if (this.tween) {
      const k = Math.min(1, (performance.now() - this.tween.t0) / this.tween.dur);
      const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      this.camera.position.lerpVectors(this.tween.p0, this.tween.p1, e);
      this.controls.target.lerpVectors(this.tween.q0, this.tween.q1, e);
      if (k >= 1) this.tween = null;
      this.dirty = true;
    }
    this.controls.update();
    if (this.pointer.moved && this.pointer.inside && !this.pointer.down) {
      this.pointer.moved = false;
      this.onHover?.(this.probe());
    }
    if (!this.dirty) return;
    this.dirty = false;
    this.render();
  };

  private render() {
    if (this.isoMesh.visible) {
      const u = (this.isoMesh.material as THREE.ShaderMaterial).uniforms;
      this.camera.updateMatrixWorld();
      u.uViewProj.value.multiplyMatrices(this.camera.projectionMatrix, this.camera.matrixWorldInverse);
      u.uLight.value.copy(this.sun.position).normalize();
    }
    this.renderer.render(this.scene, this.camera);
    this.layoutLabels();
  }

  private v = new THREE.Vector3();
  private layoutLabels() {
    const w = this.host.clientWidth, h = this.host.clientHeight;
    for (const l of this.labels) {
      this.v.copy(l.pos).project(this.camera);
      const on = this.v.z > -1 && this.v.z < 1 && Math.abs(this.v.x) < 1.1 && Math.abs(this.v.y) < 1.1;
      l.el.style.display = on ? '' : 'none';
      if (on) l.el.style.transform = `translate(-50%, -100%) translate(${((this.v.x * 0.5 + 0.5) * w).toFixed(1)}px, ${((-this.v.y * 0.5 + 0.5) * h).toFixed(1)}px)`;
    }
  }

  /** PNG of the current view on an opaque background, with the labels drawn in. */
  capture(): string {
    this.render();
    const src = this.renderer.domElement;
    const cv = document.createElement('canvas');
    cv.width = src.width; cv.height = src.height;
    const g = cv.getContext('2d')!;
    const grad = g.createLinearGradient(0, 0, 0, cv.height);
    if (this.dark) { grad.addColorStop(0, '#070D16'); grad.addColorStop(0.55, '#0F1B2C'); grad.addColorStop(1, '#17263B'); }
    else { grad.addColorStop(0, '#CFE0EE'); grad.addColorStop(0.45, '#E9F1F7'); grad.addColorStop(1, '#F4F7F9'); }
    g.fillStyle = grad;
    g.fillRect(0, 0, cv.width, cv.height);
    g.drawImage(src, 0, 0);
    if (this.opts.layers.labels) {
      const k = cv.width / (this.host.clientWidth || cv.width);
      g.textAlign = 'center';
      for (const l of this.labels) {
        if (l.el.style.display === 'none') continue;
        this.v.copy(l.pos).project(this.camera);
        const x = (this.v.x * 0.5 + 0.5) * cv.width, y = (-this.v.y * 0.5 + 0.5) * cv.height;
        const text = (l.el.textContent || '').trim();
        if (!text) continue;
        g.font = `${l.group === 'static' && l.el.classList.contains('tick') ? 500 : 600} ${Math.round(11 * k)}px Segoe UI, Helvetica, Arial, sans-serif`;
        const tw = g.measureText(text).width, pad = 5 * k, bh = 17 * k;
        if (!l.el.classList.contains('tick')) {
          g.fillStyle = this.dark ? 'rgba(15,24,35,0.88)' : 'rgba(255,255,255,0.9)';
          g.strokeStyle = this.dark ? '#33455A' : '#C5CCD2';
          g.lineWidth = k;
          g.beginPath();
          g.rect(x - tw / 2 - pad, y - bh - 2 * k, tw + 2 * pad, bh);
          g.fill(); g.stroke();
        }
        g.fillStyle = this.dark ? '#E6EDF4' : '#0F1B24';
        g.fillText(text, x, y - 7 * k);
      }
    }
    return cv.toDataURL('image/png');
  }

  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    this.ro.disconnect();
    const el = this.renderer.domElement;
    el.removeEventListener('pointermove', this.onPointerMove);
    el.removeEventListener('pointerdown', this.onPointerDown);
    el.removeEventListener('pointerup', this.onPointerUp);
    el.removeEventListener('pointerleave', this.onPointerLeave);
    this.controls.dispose();
    this.clearStatic();
    for (const l of this.labels) l.el.remove();
    this.labels = [];
    for (const k of Object.keys(this.volTex) as (keyof typeof this.volTex)[]) this.volTex[k]?.dispose();
    this.groundTex.dispose(); this.sectionTex.dispose();
    for (const m of [this.groundMesh, this.sectionMesh, this.glowMesh, this.isoMesh]) { m.geometry.dispose(); (m.material as THREE.Material).dispose(); }
    this.renderer.dispose();
    el.remove();
  }
}

function esc(s: string) { return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!)); }
function num(v: number): string {
  if (!Number.isFinite(v)) return '—';
  const a = Math.abs(v);
  if (a === 0) return '0';
  if (a >= 100) return v.toFixed(0);
  if (a >= 10) return v.toFixed(1);
  if (a >= 1) return v.toFixed(2);
  if (a >= 0.01) return v.toFixed(3);
  if (a >= 0.001) return v.toFixed(4);
  return v.toExponential(1);
}
