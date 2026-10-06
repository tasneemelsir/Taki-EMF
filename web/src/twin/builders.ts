// Geometry for the things that stand on the site: towers, conductors,
// buildings and the shield. Everything is in metres, x lateral, y up,
// z along the line (0 = mid-span).

import * as THREE from 'three';
import type { ConductorOut, LineOut, ShieldOut } from '@/lib/types';

export interface Palette {
  dark: boolean; ground: string; grid: string; gridMajor: string; steel: string; pole: string; insulator: string;
  phase: Record<string, string>; teal: string; tealBright: string; row: string; ink: string; edge: string;
  glass: string; glassLit: string; violet: string; red: string; roof: string; plant: string;
}

export function palette(dark: boolean): Palette {
  return dark ? {
    dark, ground: '#101B29', grid: '#1A293B', gridMajor: '#27405B', steel: '#A3B3C4', pole: '#B4C0CC', insulator: '#D2BC8E',
    phase: { A: '#F0685A', B: '#F2C230', C: '#5AA9F5' }, teal: '#38D6CB', tealBright: '#5FF0E6', row: '#4DA3FF', ink: '#E6EDF4',
    edge: '#05090F', glass: '#16263A', glassLit: '#F4CF7A', violet: '#B594E6', red: '#F2776E', roof: '#2A3646', plant: '#3A4656',
  } : {
    dark, ground: '#E8EDF0', grid: '#D6DEE4', gridMajor: '#BECAD3', steel: '#5B6770', pole: '#7E8A93', insulator: '#8A6F4E',
    phase: { A: '#C0392B', B: '#D9A400', C: '#004B87' }, teal: '#00857C', tealBright: '#00B8B0', row: '#004B87', ink: '#0F1B24',
    edge: '#0F1B24', glass: '#8FA9BE', glassLit: '#B9CBDA', violet: '#6B3FA0', red: '#B3261E', roof: '#A9B2B9', plant: '#8D979F',
  };
}

export interface TwinBuilding {
  name: string; type: string; shape: string; roof: string; x_near: number; x_far: number; x0: number; w: number; d: number; h: number;
  z: number; side: string; floor_h: number; glazing: number; plant: number; color: string; rooftop: string[]; sensitivity: string;
  probe: [number, number, number]; b0: number; bS: number; e0: number; eS: number;
  /** averaged over the inside of the building (b0 … eS are at the probe point) */
  b_in0?: number; b_inS?: number; e_in0?: number; e_inS?: number;
}

export interface TowerParts { lattice: number[]; arms: number[]; insul: number[]; meshes: THREE.Object3D[] }

const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));

function seg(out: number[], x1: number, y1: number, z1: number, x2: number, y2: number, z2: number) {
  out.push(x1, y1, z1, x2, y2, z2);
}

export function insulatorLength(kv: number) { return clamp(kv / 100 + 0.5, 1.2, 5); }

export function towerHeights(line: LineOut) {
  const ins = insulatorLength(line.kv);
  const yMax = Math.max(...line.conductors.map((c) => c.y_att));
  const body = yMax + ins + 0.8;
  return { ins, body, top: body + clamp(line.kv / 80, 2, 6) };
}

/** One tower of `line` at position z. Appends to the shared segment lists. */
export function buildTower(line: LineOut, z: number, parts: TowerParts, pal: Palette) {
  const xc = line.xc;
  const { ins, body: Hb, top: H } = towerHeights(line);
  const levels = new Map<number, ConductorOut[]>();
  for (const c of line.conductors) {
    const k = Math.round(c.y_att * 2) / 2;
    if (!levels.has(k)) levels.set(k, []);
    levels.get(k)!.push(c);
  }

  if (line.tower === 'monopole') {
    const rBot = clamp(H * 0.022, 0.45, 1.1), rTop = 0.26;
    const pole = new THREE.Mesh(
      new THREE.CylinderGeometry(rTop, rBot, Hb + 1.2, 14),
      new THREE.MeshStandardMaterial({ color: pal.pole, metalness: 0.35, roughness: 0.55 }));
    pole.position.set(xc, (Hb + 1.2) / 2, z);
    pole.castShadow = true;
    parts.meshes.push(pole);
    const pad = new THREE.Mesh(new THREE.CylinderGeometry(rBot * 1.9, rBot * 1.9, 0.35, 16), new THREE.MeshLambertMaterial({ color: pal.plant }));
    pad.position.set(xc, 0.17, z);
    parts.meshes.push(pad);
    for (const [, cs] of levels) {
      const yArm = cs[0].y_att + ins;
      for (const side of [-1, 1]) {
        const far = cs.filter((c) => (c.x - xc) * side > 0.5).sort((a, b) => (b.x - a.x) * side)[0];
        if (far) seg(parts.arms, xc, yArm - clamp(Math.abs(far.x - xc) * 0.16, 0.4, 1.4), z, far.x, yArm, z);
      }
      for (const c of cs) seg(parts.insul, c.x, yArm, z, c.x, c.y_att, z);
    }
    return;
  }

  // ---- lattice tower: four tapering legs, rings, X-bracing, cross-arms, peak
  const base = clamp(Hb * 0.105, 2.0, 5.5), top = clamp(line.kv / 400, 0.6, 1.2);
  const hw = (y: number) => base + (top - base) * clamp(y / Hb, 0, 1);
  const n = Math.max(4, Math.round(Hb / 5));
  const L = parts.lattice;
  const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
  for (let k = 0; k < n; k++) {
    const y0 = (Hb * k) / n, y1 = (Hb * (k + 1)) / n, a = hw(y0), b = hw(y1);
    for (let i = 0; i < 4; i++) {
      const [sx, sz] = corners[i], [tx, tz] = corners[(i + 1) % 4];
      seg(L, xc + sx * a, y0, z + sz * a, xc + sx * b, y1, z + sz * b);              // leg
      seg(L, xc + sx * b, y1, z + sz * b, xc + tx * b, y1, z + tz * b);              // ring
      seg(L, xc + sx * a, y0, z + sz * a, xc + tx * b, y1, z + tz * b);              // brace /
      seg(L, xc + tx * a, y0, z + tz * a, xc + sx * b, y1, z + sz * b);              // brace \
    }
  }
  for (const [sx, sz] of corners) seg(L, xc + sx * top, Hb, z + sz * top, xc, H, z);  // peak
  for (const [sx, sz] of corners) {                                                   // footings
    const f = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.5, 0.9), new THREE.MeshLambertMaterial({ color: pal.plant }));
    f.position.set(xc + sx * base, 0.25, z + sz * base);
    parts.meshes.push(f);
  }
  for (const [, cs] of levels) {
    const yArm = cs[0].y_att + ins;
    for (const side of [-1, 1]) {
      const far = cs.filter((c) => (c.x - xc) * side > hw(yArm) + 0.2).sort((a, b) => (b.x - a.x) * side)[0];
      if (!far) continue;
      const reach = Math.abs(far.x - xc);
      const rise = clamp(reach * 0.26, 1, 3.2);
      const a = hw(yArm), b = hw(yArm + rise);
      for (const sz of [-1, 1]) {
        seg(L, xc + side * a, yArm, z + sz * a, far.x, yArm, z);                      // bottom chord
        seg(L, xc + side * b, yArm + rise, z + sz * b, far.x, yArm, z);               // top chord
      }
      const mid = xc + side * (a + (reach - a) * 0.5);
      seg(L, mid, yArm, z, xc + side * (b + (reach - b) * 0.5), yArm + rise * 0.5, z); // web
    }
    for (const c of cs) seg(parts.insul, c.x, yArm, z, c.x, c.y_att, z);
  }
}

/** Conductor polylines (as segment pairs) by phase: the modelled span, and stubs into the next spans. */
export function conductorPaths(line: LineOut, span: number, ext: number) {
  // "off": conductors of a circuit that is out of service, drawn grey
  const main: Record<string, number[]> = { A: [], B: [], C: [], off: [] };
  const stub: Record<string, number[]> = { A: [], B: [], C: [], off: [] };
  const N = 44, M = 12;
  for (const c of line.conductors) {
    const subs = c.bundle.length ? c.bundle : [[0, 0]];
    const dy = c.y_att - c.y;
    for (const [ox, oy] of subs) {
      const x = c.x + ox;
      const key = c.on === false ? 'off' : c.phase;
      const m = main[key] ?? main.A;
      let py = c.y_att + oy, pz = -span;
      for (let i = 1; i <= N; i++) {
        const zz = -span + (2 * span * i) / N;
        const yy = c.y + dy * (zz / span) * (zz / span) + oy;
        m.push(x, py, pz, x, yy, zz);
        py = yy; pz = zz;
      }
      const s = stub[key] ?? stub.A;
      for (const sgn of [-1, 1]) {
        let qy = c.y_att + oy, qz = sgn * span;
        for (let i = 1; i <= M; i++) {
          const d = (ext * i) / M;
          const u = (d - span) / span;
          const yy = c.y + dy * u * u + oy;
          const zz = sgn * (span + d);
          s.push(x, qy, qz, x, yy, zz);
          qy = yy; qz = zz;
        }
      }
    }
  }
  return { main, stub };
}

// ---------------------------------------------------------------- buildings
function facadeTexture(color: string, glazing: number, pal: Palette, seed: number): THREE.CanvasTexture {
  const S = 256, cells = 4, cell = S / cells;
  const cv = document.createElement('canvas');
  cv.width = cv.height = S;
  const g = cv.getContext('2d')!;
  g.fillStyle = color;
  g.fillRect(0, 0, S, S);
  const ww = cell * clamp(0.3 + glazing * 0.62, 0.3, 0.9), wh = cell * clamp(0.34 + glazing * 0.42, 0.34, 0.78);
  let r = seed * 9301 + 49297;
  const rnd = () => { r = (r * 9301 + 49297) % 233280; return r / 233280; };
  for (let j = 0; j < cells; j++) {
    g.fillStyle = 'rgba(0,0,0,0.10)';
    g.fillRect(0, j * cell, S, 2);                                   // floor line
    for (let i = 0; i < cells; i++) {
      const x = i * cell + (cell - ww) / 2, y = j * cell + (cell - wh) / 2 + 2;
      const lit = pal.dark ? rnd() < 0.3 : rnd() < 0.5;
      g.fillStyle = lit ? pal.glassLit : pal.glass;
      g.fillRect(x, y, ww, wh);
      g.strokeStyle = 'rgba(0,0,0,0.28)';
      g.lineWidth = 1.5;
      g.strokeRect(x, y, ww, wh);
      if (ww > cell * 0.5) { g.beginPath(); g.moveTo(x + ww / 2, y); g.lineTo(x + ww / 2, y + wh); g.stroke(); }
    }
  }
  const t = new THREE.CanvasTexture(cv);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 4;
  return t;
}

function shade(hex: string, k: number): string {
  const c = new THREE.Color(hex);
  c.multiplyScalar(k);
  return `#${c.getHexString()}`;
}

function tinted(tex: THREE.CanvasTexture, rx: number, ry: number): THREE.MeshLambertMaterial {
  const t = tex.clone();
  t.repeat.set(Math.max(0.25, rx), Math.max(0.25, ry));
  t.needsUpdate = true;
  return new THREE.MeshLambertMaterial({ map: t });
}

function withEdges(mesh: THREE.Mesh, pal: Palette) {
  const e = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry, 20),
    new THREE.LineBasicMaterial({ color: pal.edge, transparent: true, opacity: pal.dark ? 0.55 : 0.3 }));
  mesh.add(e);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

export function buildBuilding(b: TwinBuilding, pal: Palette, index: number): THREE.Group {
  const g = new THREE.Group();
  g.name = `building:${index}`;
  const wallColor = pal.dark ? shade(b.color, 0.42) : b.color;
  const tex = facadeTexture(wallColor, b.glazing, pal, index + 3);
  const roofMat = new THREE.MeshLambertMaterial({ color: pal.roof });
  const cx = b.x0 + b.w / 2, cz = b.z;
  const fh = Math.max(2.4, b.floor_h || 3.2);
  const bay = 4;

  const block = (w: number, h: number, d: number, x: number, y0: number, z: number) => {
    const floors = Math.max(1, Math.round(h / fh)) / 4;
    const mx = tinted(tex, d / bay / 4, floors), mz = tinted(tex, w / bay / 4, floors);
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), [mx, mx, roofMat, roofMat, mz, mz]);
    m.position.set(x, y0 + h / 2, z);
    g.add(withEdges(m, pal));
    return m;
  };

  let wallH = b.h, rise = 0;
  if (b.roof === 'pitched') { rise = clamp(Math.min(b.w, b.d) * 0.22, 1.2, b.h * 0.34); wallH = b.h - rise; }
  if (b.roof === 'stepped') wallH = Math.max(fh, b.h - fh);
  let topW = b.w, topD = b.d, topX = cx, topZ = cz;

  if (b.shape === 'cylinder') {
    const r = Math.min(b.w, b.d) / 2;
    const floors = Math.max(1, Math.round(wallH / fh)) / 4;
    const side = tinted(tex, (2 * Math.PI * r) / bay / 4, floors);
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, wallH, 40), [side, roofMat, roofMat]);
    m.position.set(cx, wallH / 2, cz);
    g.add(withEdges(m, pal));
    topW = topD = r * 1.3;
  } else if (b.shape === 'lshape') {
    block(b.w, wallH, b.d * 0.5, cx, 0, cz - b.d * 0.25);
    const ww = b.w * 0.45;
    const wx = b.side === 'left' ? b.x0 + b.w - ww / 2 : b.x0 + ww / 2;
    block(ww, wallH, b.d * 0.5, wx, 0, cz + b.d * 0.25);
    topD = b.d * 0.5; topZ = cz - b.d * 0.25;
  } else if (b.shape === 'multistory') {
    const ph = Math.min(wallH * 0.3, 2 * fh);
    block(b.w, ph, b.d, cx, 0, cz);
    topW = b.w * 0.62; topD = b.d * 0.7;
    block(topW, wallH - ph, topD, cx, ph, cz);
  } else {
    block(b.w, wallH, b.d, cx, 0, cz);
  }

  if (b.roof === 'pitched' && b.shape !== 'cylinder') {
    const alongX = topW >= topD;
    const hw = topW / 2 + 0.4, hd = topD / 2 + 0.4;
    const P = alongX
      ? [[-hw, 0, -hd], [hw, 0, -hd], [hw, 0, hd], [-hw, 0, hd], [-hw, rise, 0], [hw, rise, 0]]
      : [[-hw, 0, -hd], [-hw, 0, hd], [hw, 0, hd], [hw, 0, -hd], [0, rise, -hd], [0, rise, hd]];
    const tri = [[0, 1, 5], [0, 5, 4], [3, 4, 5], [3, 5, 2], [0, 4, 3], [1, 2, 5]];
    const pos: number[] = [];
    for (const t of tri) for (const i of t) pos.push(P[i][0], P[i][1], P[i][2]);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.computeVertexNormals();
    const m = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ color: pal.dark ? '#4A3530' : '#9B5B48', side: THREE.DoubleSide }));
    m.position.set(topX, wallH, topZ);
    g.add(withEdges(m, pal));
  } else if (b.roof === 'stepped') {
    block(topW * 0.56, b.h - wallH, topD * 0.56, topX, wallH, topZ);
  } else if ((b.plant || b.rooftop?.length) && !/data|warehouse/i.test(b.type)) {
    const n = clamp((b.rooftop?.length || 1) + 1, 2, 4);
    for (let i = 0; i < n; i++) {
      const uw = clamp(topW * 0.12, 1.2, 4), ud = clamp(topD * 0.16, 1.2, 4), uh = 1.1 + 0.35 * (i % 2);
      const m = new THREE.Mesh(new THREE.BoxGeometry(uw, uh, ud), new THREE.MeshLambertMaterial({ color: pal.plant }));
      m.position.set(topX - topW * 0.3 + (topW * 0.6 * i) / Math.max(1, n - 1), wallH + uh / 2, topZ + (i % 2 ? 1 : -1) * topD * 0.18);
      g.add(withEdges(m, pal));
    }
  }

  // The +x wall carries the entrance and other type-specific details: it is the one the
  // default camera looks at (for a building on the right of the line, its street side).
  const sx = 1;
  const r = Math.min(b.w, b.d) / 2;
  const face: Face = {
    x: b.shape === 'cylinder' ? cx + r : b.x0 + b.w,
    z: b.shape === 'lshape' ? cz - b.d * 0.25 : cz,
    len: b.shape === 'cylinder' ? r * 0.9 : b.shape === 'lshape' ? b.d * 0.5 : b.d,
    sx, wallH, fh,
  };
  addDetails(g, b, pal, face, { x: topX, z: topZ, w: topW, d: topD, y: b.roof === 'pitched' ? wallH : b.h, rise });
  return g;
}

interface Face { x: number; z: number; len: number; sx: number; wallH: number; fh: number }
interface Top { x: number; z: number; w: number; d: number; y: number; rise: number }

/**
 * Details that make each building type recognisable: an entrance on the +x
 * wall, then balconies and a chimney (residential), a mast (office),
 * a canopy on columns and a flagpole (school), a helipad (hospital), chillers,
 * cooling towers and louvres (data centre), roller doors and a ridge vent
 * (warehouse). Drawing only - none of it enters the field calculation.
 */
function addDetails(g: THREE.Group, b: TwinBuilding, pal: Palette, f: Face, top: Top) {
  const solid = (color: string) => new THREE.MeshLambertMaterial({ color });
  const dark = solid(pal.dark ? '#0B1422' : '#33414E');
  const trim = solid(pal.dark ? '#5A6878' : '#EEF1F3');
  const metal = solid(pal.plant);
  const box = (w: number, h: number, d: number, x: number, y: number, z: number, mat: THREE.Material, edges = false) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    m.position.set(x, y, z);
    m.castShadow = true;
    g.add(edges ? withEdges(m, pal) : m);
    return m;
  };
  const cyl = (rTop: number, rBot: number, h: number, x: number, y: number, z: number, mat: THREE.Material, seg = 18) => {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(rTop, rBot, h, seg), mat);
    m.position.set(x, y, z);
    m.castShadow = true;
    g.add(m);
    return m;
  };
  const out = (d: number) => f.x + f.sx * d;                               // d metres proud of the wall
  const t = b.type.toLowerCase();
  const doorH = Math.min(2.4, f.wallH * 0.8);

  if (t.includes('warehouse')) {
    // roller doors with a dock strip, and a personnel door
    const n = clamp(Math.floor(f.len / 9), 1, 5), dw = Math.min(4.2, f.len / (n + 1)), dh = Math.min(4.6, f.wallH * 0.7);
    for (let i = 0; i < n; i++) {
      const z = f.z - f.len / 2 + (f.len * (i + 0.5)) / n;
      box(0.14, dh, dw, out(0.07), dh / 2, z, trim, true);
      for (let k = 1; k < 5; k++) box(0.16, 0.05, dw, out(0.08), (dh * k) / 5, z, dark);
      box(0.9, 0.5, dw + 0.8, out(0.45), 0.25, z, metal);
    }
    if (top.rise > 0) {
      const alongX = top.w >= top.d;
      box(alongX ? top.w * 0.7 : 1.0, 0.45, alongX ? 1.0 : top.d * 0.7, top.x, top.y + top.rise + 0.2, top.z, trim, true);
    }
    return;
  }

  // entrance: a glazed door under a small canopy
  const dw = t.includes('school') || t.includes('hospital') || t.includes('office') ? clamp(f.len * 0.16, 2.4, 6) : 1.2;
  box(0.12, doorH, dw, out(0.06), doorH / 2, f.z, dark);
  box(0.14, doorH, 0.08, out(0.07), doorH / 2, f.z, trim);
  const canopyD = t.includes('school') || t.includes('hospital') ? 3.2 : 1.1;
  box(canopyD, 0.18, dw + 1.2, out(canopyD / 2), doorH + 0.35, f.z, trim, true);
  if (canopyD > 2) for (const s of [-1, 1]) cyl(0.11, 0.11, doorH + 0.3, out(canopyD - 0.3), (doorH + 0.3) / 2, f.z + (s * (dw + 0.7)) / 2, trim, 10);

  if (t.includes('residential')) {
    // balconies above the ground floor, and a chimney on a pitched roof
    const floors = clamp(Math.round(f.wallH / f.fh), 1, 14);
    const cols = f.len >= 9 ? [-0.27, 0.27] : [0];
    for (let k = 1; k < floors; k++) for (const c of cols) {
      const z = f.z + c * f.len, y = k * f.fh;
      box(1.2, 0.14, 2.6, out(0.6), y, z, trim, true);
      box(0.05, 0.9, 2.6, out(1.18), y + 0.5, z, dark);
      for (const s of [-1, 1]) box(1.2, 0.9, 0.05, out(0.6), y + 0.5, z + s * 1.3, dark);
    }
    if (top.rise > 0) box(0.8, top.rise * 0.9 + 0.8, 0.8, top.x + top.w * 0.22, top.y + top.rise * 0.45 + 0.4, top.z + top.d * 0.18, solid(pal.dark ? '#3A2A26' : '#7C4A3A'), true);
  } else if (t.includes('office')) {
    cyl(0.07, 0.11, clamp(b.h * 0.22, 3, 9), top.x + top.w * 0.34, top.y + clamp(b.h * 0.22, 3, 9) / 2, top.z - top.d * 0.3, metal, 8);
  } else if (t.includes('school')) {
    const ph = clamp(b.h * 0.8, 5, 10);
    cyl(0.05, 0.07, ph, out(5), ph / 2, f.z + dw / 2 + 3, metal, 8);
    box(0.04, 0.7, 1.1, out(5), ph - 0.5, f.z + dw / 2 + 3.6, solid(pal.dark ? '#3E77B3' : '#004B87'));
  } else if (t.includes('hospital')) {
    // helipad on the highest roof
    const stepped = b.roof === 'stepped';
    const hw = stepped ? top.w * 0.56 : top.w, hd = stepped ? top.d * 0.56 : top.d;
    const pr = clamp(Math.min(hw, hd) * 0.36, 2, 7);
    cyl(pr, pr, 0.16, top.x, top.y + 0.08, top.z, solid(pal.dark ? '#27384A' : '#7F8C97'), 32);
    const ring = new THREE.Mesh(new THREE.RingGeometry(pr * 0.78, pr * 0.9, 40), new THREE.MeshBasicMaterial({ color: '#FFFFFF', side: THREE.DoubleSide }));
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(top.x, top.y + 0.18, top.z);
    g.add(ring);
    const white = new THREE.MeshBasicMaterial({ color: '#FFFFFF' });
    for (const s of [-1, 1]) box(pr * 0.12, 0.03, pr * 0.8, top.x + s * pr * 0.26, top.y + 0.18, top.z, white);
    box(pr * 0.52, 0.03, pr * 0.12, top.x, top.y + 0.18, top.z, white);
  } else if (t.includes('data')) {
    // louvre bands on the wall; a row of chillers and two cooling towers on the roof
    for (let k = 0; k < 3; k++) box(0.1, 0.35, f.len * 0.8, out(0.05), f.wallH * (0.45 + 0.17 * k), f.z, dark);
    const n = clamp(Math.floor(top.w / 6), 2, 8), uw = clamp(top.w / n * 0.62, 1.6, 4.2), ud = clamp(top.d * 0.2, 1.6, 4);
    for (let i = 0; i < n; i++) {
      const x = top.x - top.w / 2 + (top.w * (i + 0.5)) / n, z = top.z - top.d * 0.24;
      box(uw, 1.5, ud, x, top.y + 0.75, z, metal, true);
      for (const s of [-1, 1]) cyl(Math.min(uw, ud) * 0.2, Math.min(uw, ud) * 0.2, 0.12, x + (s * uw) / 4, top.y + 1.56, z, dark, 14);
    }
    const tr = clamp(Math.min(top.w, top.d) * 0.09, 1.1, 2.6);
    for (const s of [-1, 1]) {
      cyl(tr * 0.8, tr, tr * 1.9, top.x + s * top.w * 0.2, top.y + tr * 0.95, top.z + top.d * 0.24, metal, 22);
      cyl(tr * 0.62, tr * 0.62, 0.1, top.x + s * top.w * 0.2, top.y + tr * 1.9 + 0.02, top.z + top.d * 0.24, dark, 22);
    }
  }
}

// -------------------------------------------------------------------- shield
function meshPattern(pal: Palette): THREE.CanvasTexture {
  const cv = document.createElement('canvas');
  cv.width = cv.height = 64;
  const g = cv.getContext('2d')!;
  g.clearRect(0, 0, 64, 64);
  g.strokeStyle = pal.tealBright;
  g.lineWidth = 5;
  g.strokeRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(cv);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

export interface ShieldParts { group: THREE.Group; wires: number[]; bonds: number[] }

export function buildShield(s: ShieldOut, pal: Palette, zLimit: number): ShieldParts {
  const g = new THREE.Group();
  g.name = 'shield';
  const out: ShieldParts = { group: g, wires: [], bonds: [] };
  if (!s.on || !s.walls.length) return out;
  const z0 = Math.max(-zLimit, s.zc - s.zh), z1 = Math.min(zLimit, s.zc + s.zh);

  if (s.is_wire) {
    // Conductors: drawn as lines along the span, bonded at both ends, on slender poles.
    const posts: number[] = [];
    for (const [x, y] of s.wires) {
      out.wires.push(x, y, z0, x, y, z1);
      for (const z of [z0, z1]) posts.push(x, 0, z, x, y, z);
    }
    const chains: number[][][] = [];
    if (s.preset === 'passive-loop') for (let i = 0; i + 1 < s.wires.length; i += 2) chains.push([s.wires[i], s.wires[i + 1]]);
    else {
      const pos = s.wires.filter((w) => w[0] >= 0), neg = s.wires.filter((w) => w[0] < 0);
      for (const c of [pos, neg]) if (c.length > 1) chains.push([...c].sort((a, b) => a[0] - b[0]));
    }
    if (s.bonded) for (const c of chains) for (const z of [z0, z1]) for (let i = 0; i + 1 < c.length; i++) out.bonds.push(c[i][0], c[i][1], z, c[i + 1][0], c[i + 1][1], z);
    const pg = new THREE.BufferGeometry();
    pg.setAttribute('position', new THREE.Float32BufferAttribute(posts, 3));
    g.add(new THREE.LineSegments(pg, new THREE.LineBasicMaterial({ color: pal.steel, transparent: true, opacity: 0.7 })));
    return out;
  }

  const pattern = s.mesh ? meshPattern(pal) : null;
  const pos: number[] = [], uv: number[] = [], edge: number[] = [], posts: number[] = [];
  const cell = 1.5;
  const quad = (a: number[], b: number[], c: number[], d: number[], lu: number, lv: number) => {
    pos.push(...a, ...b, ...c, ...a, ...c, ...d);
    uv.push(0, 0, lu, 0, lu, lv, 0, 0, lu, lv, 0, lv);
    edge.push(...a, ...b, ...b, ...c, ...c, ...d, ...d, ...a);
  };
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  for (const [x1, y1, x2, y2] of s.walls) {
    xmin = Math.min(xmin, x1, x2); xmax = Math.max(xmax, x1, x2);
    ymin = Math.min(ymin, y1, y2); ymax = Math.max(ymax, y1, y2);
  }
  // A shield fixed to a building is drawn a hand's width proud of the wall it sits on.
  const proud = s.attached && !s.room && s.preset !== 'surround-wall' ? 0.18 : 0;
  const cxm = (xmin + xmax) / 2;
  const px = (x: number) => (proud && Math.abs(x - cxm) > 1e-6 ? x + Math.sign(x - cxm) * proud : x);
  const py = (y: number) => (proud && y > ymin + 0.5 && Math.abs(y - ymax) < 1e-6 ? y + proud : y);
  const za = z0 - proud, zb = z1 + proud;
  for (const [x1, y1, x2, y2] of s.walls) {
    const len = Math.hypot(x2 - x1, y2 - y1);
    quad([px(x1), py(y1), za], [px(x2), py(y2), za], [px(x2), py(y2), zb], [px(x1), py(y1), zb], len / cell, (zb - za) / cell);
    if (Math.abs(x1 - x2) < 0.05 && Math.min(y1, y2) < 0.3 && !s.attached) {
      const n = Math.max(1, Math.round((z1 - z0) / 10));
      for (let i = 0; i <= n; i++) { const z = z0 + ((z1 - z0) * i) / n; posts.push(x1, 0, z, x1, Math.max(y1, y2) + 0.4, z); }
    }
  }
  if (s.surrounding) {
    // the two end walls, which the cross-section model does not see but the real shield has
    for (const z of [za, zb]) quad([px(xmin), ymin, z], [px(xmax), ymin, z], [px(xmax), py(ymax), z], [px(xmin), py(ymax), z], (xmax - xmin) / cell, (ymax - ymin) / cell);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  const mat = new THREE.MeshBasicMaterial({
    color: pattern ? '#ffffff' : pal.teal, map: pattern, transparent: true, opacity: pattern ? 0.85 : s.room ? 0.6 : (pal.dark ? 0.3 : 0.34),
    side: THREE.DoubleSide, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
  });
  const m = new THREE.Mesh(geo, mat);
  m.renderOrder = 6;
  g.add(m);
  const eg = new THREE.BufferGeometry();
  eg.setAttribute('position', new THREE.Float32BufferAttribute(edge, 3));
  g.add(new THREE.LineSegments(eg, new THREE.LineBasicMaterial({ color: pal.tealBright })));
  if (posts.length) {
    const pg = new THREE.BufferGeometry();
    pg.setAttribute('position', new THREE.Float32BufferAttribute(posts, 3));
    g.add(new THREE.LineSegments(pg, new THREE.LineBasicMaterial({ color: pal.teal })));
  }
  return out;
}
