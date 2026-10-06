// Electric field lines at one instant of the cycle, traced from the wires.
//
// An electric field line starts on positive charge and ends on negative charge: another wire,
// the ground, or an earthed shield. The number of lines that leave a wire is in proportion to
// the charge on it at that instant, so the same charge stands behind every line and the lines
// crowd where the field is strong.
//
// The field of the wires is summed exactly here (a line charge and its image in the ground give
// lam / r each, with lam in kV); the field of the charge induced on a shield comes from the
// server on a grid, because it is smooth everywhere except on the sheet, where the lines end.
// engine/field_lines.py describes the same model.

export interface EGrid {
  x0: number; x1: number; y0: number; y1: number; nx: number; ny: number;
  exr: Float32Array; exi: Float32Array; eyr: Float32Array; eyi: Float32Array;
}
export interface ESource {
  conds: { x: number; y: number }[];
  /** charge phasor of every conductor as [re, im] of q / (2 pi eps0), in kV */
  lam: number[][];
  /** field of the charge on the shield, kV/m; null without a shield */
  grid: EGrid | null;
  walls: number[][];
  wires: number[][];
}
export interface ELines {
  x: (number | null)[]; y: (number | null)[];
  /** one arrowhead per line: position and angle, clockwise from up */
  ax: number[]; ay: number[]; angle: number[];
  count: number;
}

const R0 = 0.4;          // m: lines start and end this far from the centre of a wire
const MAX_STEPS = 6000;

/** Where the segment p -> q meets the segment a -> b, as a fraction of p -> q; -1 if it does not. */
function cross(px: number, py: number, qx: number, qy: number, ax: number, ay: number, bx: number, by: number): number {
  const rx = qx - px, ry = qy - py, sx = bx - ax, sy = by - ay;
  const den = rx * sy - ry * sx;
  if (Math.abs(den) < 1e-12) return -1;
  const t = ((ax - px) * sy - (ay - py) * sx) / den;
  const u = ((ax - px) * ry - (ay - py) * rx) / den;
  return t >= 0 && t <= 1 && u >= 0 && u <= 1 ? t : -1;
}

/**
 * The lines at ωt = phaseDeg. `linesAtMax` is how many lines the most highly charged wire has at
 * its peak (lamRef, kV); every other wire gets its share. Lines leave a wire evenly around it,
 * counted from straight down, so they fan out smoothly as the charge grows and new ones appear
 * in pairs at the top.
 */
export function traceElectric(src: ESource, phaseDeg: number, linesAtMax: number, lamRef: number,
  box: { x0: number; x1: number; y1: number }): ELines {
  const out: ELines = { x: [], y: [], ax: [], ay: [], angle: [], count: 0 };
  const n = src.conds.length;
  if (!n || !(lamRef > 0)) return out;
  const c = Math.cos((phaseDeg * Math.PI) / 180), s = Math.sin((phaseDeg * Math.PI) / 180);
  const lam = src.lam.map(([re, im]) => re * c - im * s);
  const cx = src.conds.map((k) => k.x), cy = src.conds.map((k) => k.y);
  const g = src.grid;
  let gx: Float32Array | null = null, gy: Float32Array | null = null;
  if (g) {
    const m = g.nx * g.ny;
    gx = new Float32Array(m); gy = new Float32Array(m);
    for (let i = 0; i < m; i++) { gx[i] = g.exr[i] * c - g.exi[i] * s; gy[i] = g.eyr[i] * c - g.eyi[i] * s; }
  }
  const e = [0, 0];
  const field = (x: number, y: number) => {
    let ex = 0, ey = 0;
    for (let k = 0; k < n; k++) {
      const dx = x - cx[k], dy = y - cy[k], dyi = y + cy[k];
      const r2 = Math.max(dx * dx + dy * dy, 1e-6), r2i = Math.max(dx * dx + dyi * dyi, 1e-6);
      ex += lam[k] * (dx / r2 - dx / r2i); ey += lam[k] * (dy / r2 - dyi / r2i);
    }
    if (g && gx && gy) {
      const fi = Math.max(0, Math.min(g.nx - 1.0001, ((x - g.x0) / (g.x1 - g.x0)) * (g.nx - 1)));
      const fj = Math.max(0, Math.min(g.ny - 1.0001, ((y - g.y0) / (g.y1 - g.y0)) * (g.ny - 1)));
      const i = Math.floor(fi), j = Math.floor(fj), u = fi - i, v = fj - j, o = j * g.nx + i;
      const w00 = (1 - u) * (1 - v), w10 = u * (1 - v), w01 = (1 - u) * v, w11 = u * v;
      ex += gx[o] * w00 + gx[o + 1] * w10 + gx[o + g.nx] * w01 + gx[o + g.nx + 1] * w11;
      ey += gy[o] * w00 + gy[o + 1] * w10 + gy[o + g.nx] * w01 + gy[o + g.nx + 1] * w11;
    }
    e[0] = ex; e[1] = ey;
  };
  // unit direction of travel at a point: along the field from a positive wire, against it from a negative one
  const dir = (x: number, y: number, sg: number, d: number[]) => {
    field(x, y);
    const m = Math.hypot(e[0], e[1]);
    if (!(m > 1e-12)) { d[0] = 0; d[1] = 0; return false; }
    d[0] = (sg * e[0]) / m; d[1] = (sg * e[1]) / m; return true;
  };
  const d1 = [0, 0], d2 = [0, 0], d3 = [0, 0], d4 = [0, 0];
  const step = lamRef / Math.max(2, linesAtMax);

  for (let k = 0; k < n; k++) {
    const q = Math.abs(lam[k]);
    if (q < step / 2) continue;
    const sg = lam[k] > 0 ? 1 : -1;
    const half = Math.floor(q / (2 * step) - 1e-9);
    for (let j = -half; j <= half; j++) {
      const phi = (2 * Math.PI * j * step) / q;                // from straight down, positive towards +x
      let x = cx[k] + R0 * Math.sin(phi), y = cy[k] - R0 * Math.cos(phi);
      const px: number[] = [x], py: number[] = [y];
      let end = 'steps', lx = x, ly = y, len = 0;
      for (let it = 0; it < MAX_STEPS; it++) {
        let dmin = Infinity;
        for (let m = 0; m < n; m++) dmin = Math.min(dmin, Math.hypot(x - cx[m], y - cy[m]));
        const h = Math.max(0.04, Math.min(0.5, 0.15 * dmin));
        if (!dir(x, y, sg, d1)) { end = 'null'; break; }
        if (!dir(x + 0.5 * h * d1[0], y + 0.5 * h * d1[1], sg, d2)) { end = 'null'; break; }
        if (!dir(x + 0.5 * h * d2[0], y + 0.5 * h * d2[1], sg, d3)) { end = 'null'; break; }
        if (!dir(x + h * d3[0], y + h * d3[1], sg, d4)) { end = 'null'; break; }
        let nx = x + (h / 6) * (d1[0] + 2 * d2[0] + 2 * d3[0] + d4[0]);
        let ny = y + (h / 6) * (d1[1] + 2 * d2[1] + 2 * d3[1] + d4[1]);
        // a shield sheet: the line ends on the charge it carries
        let tHit = 2;
        for (const w of src.walls) { const t = cross(x, y, nx, ny, w[0], w[1], w[2], w[3]); if (t >= 0 && t < tHit) tHit = t; }
        if (tHit <= 1) { nx = x + (nx - x) * tHit; ny = y + (ny - y) * tHit; end = 'shield'; }
        else if (ny <= 0) { const t = y / (y - ny); nx = x + (nx - x) * t; ny = 0; end = 'ground'; }
        else {
          for (const w of src.wires) if (Math.hypot(nx - w[0], ny - w[1]) < R0) { end = 'shield'; break; }
          if (end === 'steps') for (let m = 0; m < n; m++) if ((m !== k || len > 3) && Math.hypot(nx - cx[m], ny - cy[m]) < R0) { end = 'wire'; break; }
          if (end === 'steps' && (nx < box.x0 || nx > box.x1 || ny > box.y1)) end = 'out';
        }
        len += Math.hypot(nx - x, ny - y);
        x = nx; y = ny;
        if (end !== 'steps' || Math.hypot(x - lx, y - ly) > 0.3) { px.push(x); py.push(y); lx = x; ly = y; }
        if (end !== 'steps') break;
        if (len > 900) { end = 'long'; break; }
      }
      // a line between two wires is drawn once, from its positive end
      if (sg < 0 && end === 'wire') continue;
      if (px.length < 2) continue;
      for (let i = 0; i < px.length; i++) { out.x.push(px[i]); out.y.push(py[i]); }
      out.x.push(null); out.y.push(null);
      out.count++;
      if (len > 7) {
        const i = Math.max(1, Math.min(px.length - 1, Math.round(px.length * 0.42)));
        const ux = sg * (px[i] - px[i - 1]), uy = sg * (py[i] - py[i - 1]);
        out.ax.push(px[i]); out.ay.push(py[i]); out.angle.push((Math.atan2(ux, uy) * 180) / Math.PI);
      }
    }
  }
  return out;
}
