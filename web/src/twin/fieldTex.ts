// Turns a field grid from the server into a coloured canvas (heat map with
// optional iso-lines) for the twin's ground map and section plane, and offers
// the bilinear sampler the hover read-out uses.

import { CIVIDIS, ramp } from '@/lib/colors';

export type Quantity = 'B' | 'E';
export type View = 'without' | 'with' | 'diff';
export type ScaleMode = 'limit' | 'peak' | 'log';

export interface FieldGrid { nx: number; ny: number; a0: Float32Array; aS: Float32Array }
export interface Contour { level: number; color: [number, number, number]; bold?: boolean; alpha?: number }

export interface PaintSpec {
  view: View;
  mode: ScaleMode;
  max: number;                 // value mapped to the top of the colour ramp
  logDecades?: number;         // range of the log scale below max
  dark: boolean;
  alphaLo: number;             // opacity at the bottom of the ramp
  alphaHi: number;             // opacity at the top
  contours: Contour[];
  /** For each canvas row (top = 0): does the shield act on this row? */
  rowMask?: Uint8Array | null;
  shieldAll?: boolean;         // shield acts on the whole grid (section plane)
}

export function sample(a: Float32Array, nx: number, ny: number, fx: number, fy: number): number {
  fx = fx < 0 ? 0 : fx > nx - 1 ? nx - 1 : fx;
  fy = fy < 0 ? 0 : fy > ny - 1 ? ny - 1 : fy;
  const i = Math.min(nx - 2, Math.floor(fx)), j = Math.min(ny - 2, Math.floor(fy));
  const u = fx - i, v = fy - j;
  const k = j * nx + i;
  return (a[k] * (1 - u) + a[k + 1] * u) * (1 - v) + (a[k + nx] * (1 - u) + a[k + nx + 1] * u) * v;
}

export function maxOf(a: Float32Array): number {
  let m = 0;
  for (let i = 0; i < a.length; i++) if (a[i] > m) m = a[i];
  return m;
}

export function scaleT(v: number, spec: { mode: ScaleMode; max: number; logDecades?: number }): number {
  if (!(v > 0) || !(spec.max > 0)) return 0;
  if (spec.mode === 'log') {
    const d = spec.logDecades ?? 3;
    return Math.max(0, Math.min(1, 1 + Math.log10(v / spec.max) / d));
  }
  return Math.max(0, Math.min(1, v / spec.max));
}

/** Colours for values above the top of the scale: yellow -> orange -> red -> purple over two decades. */
export const OVER: [number, number, number][] = [[255, 234, 70], [255, 178, 48], [240, 104, 34], [198, 40, 58], [126, 26, 112]];

const TEAL: [number, number, number] = [0, 150, 140];
const TEAL_DARK: [number, number, number] = [56, 225, 212];
const RED: [number, number, number] = [190, 45, 36];
const RED_DARK: [number, number, number] = [251, 113, 133];

/** Paint `grid` into `canvas`. Canvas row 0 is the LAST data row (textures are flipped in y). */
export function paintField(canvas: HTMLCanvasElement, grid: FieldGrid, spec: PaintSpec): void {
  const W = canvas.width, H = canvas.height;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(W, H);
  const px = img.data;
  const vals = new Float32Array(W * H);
  const { nx, ny, a0, aS } = grid;
  const sx = (nx - 1) / (W - 1), sy = (ny - 1) / (H - 1);
  const diff = spec.view === 'diff';
  const wantS = spec.view !== 'without';

  for (let j = 0; j < H; j++) {
    const fy = (H - 1 - j) * sy;
    const shielded = wantS && (spec.shieldAll || (spec.rowMask ? spec.rowMask[j] === 1 : false));
    for (let i = 0; i < W; i++) {
      const fx = i * sx;
      const v0 = sample(a0, nx, ny, fx, fy);
      const vS = shielded ? sample(aS, nx, ny, fx, fy) : v0;
      const k = j * W + i, o = k * 4;
      if (diff) {
        const d = v0 > 1e-12 ? (vS - v0) / v0 : 0;
        vals[k] = vS;
        const m = Math.min(1, Math.abs(d) * 1.4);
        const c = d < 0 ? (spec.dark ? TEAL_DARK : TEAL) : (spec.dark ? RED_DARK : RED);
        px[o] = c[0]; px[o + 1] = c[1]; px[o + 2] = c[2];
        px[o + 3] = Math.round(255 * spec.alphaHi * Math.pow(m, 0.75));
      } else {
        const v = spec.view === 'with' ? vS : v0;
        vals[k] = v;
        const t = scaleT(v, spec);
        const over = spec.mode !== 'log' && v > spec.max;
        const c = over ? ramp(Math.min(1, Math.log10(v / spec.max) / 2), OVER) : ramp(t, CIVIDIS);
        const s = Math.min(1, t / 0.4);
        const a = spec.alphaLo + (spec.alphaHi - spec.alphaLo) * s * s * (3 - 2 * s);
        px[o] = c[0]; px[o + 1] = c[1]; px[o + 2] = c[2]; px[o + 3] = Math.round(255 * a);
      }
    }
  }

  for (const ct of spec.contours) {
    if (!(ct.level > 0)) continue;
    const L = ct.level;
    for (let j = 0; j < H - 1; j++) {
      for (let i = 0; i < W - 1; i++) {
        const k = j * W + i;
        const s = vals[k] >= L;
        if (s !== (vals[k + 1] >= L) || s !== (vals[k + W] >= L)) {
          put(px, k, ct.color, ct.alpha ?? 1);
          if (ct.bold) { put(px, k + 1, ct.color, 1); put(px, k + W, ct.color, 1); }
        }
      }
    }
  }
  ctx.putImageData(img, 0, 0);
}

function put(px: Uint8ClampedArray, k: number, c: [number, number, number], a: number) {
  const o = k * 4;
  if (a >= 1) { px[o] = c[0]; px[o + 1] = c[1]; px[o + 2] = c[2]; px[o + 3] = 255; return; }
  // blend the line over whatever the heat map put there
  const a0 = px[o + 3] / 255, out = a + a0 * (1 - a);
  for (let i = 0; i < 3; i++) px[o + i] = Math.round((c[i] * a + px[o + i] * a0 * (1 - a)) / Math.max(out, 1e-6));
  px[o + 3] = Math.round(out * 255);
}

/** "Nice" contour levels (1-2-5 per decade) inside (lo, hi). */
export function niceLevels(lo: number, hi: number, maxCount = 6): number[] {
  if (!(hi > 0) || !(lo > 0) || lo >= hi) return [];
  const out: number[] = [];
  for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) {
    for (const m of [1, 2, 5]) {
      const v = m * Math.pow(10, e);
      if (v > lo * 1.001 && v < hi * 0.999) out.push(v);
    }
  }
  while (out.length > maxCount) {
    // thin from the bottom: keep the levels closest to the top of the range
    out.splice(0, 1);
  }
  return out;
}
