// Decode the base64 float32 / uint8 arrays the server sends for field grids.

export function b64f32(s: string): Float32Array {
  const bin = atob(s);
  const u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  return new Float32Array(u8.buffer);
}

export function b64u8(s: string): Uint8Array {
  const bin = atob(s);
  const u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  return u8;
}

/** Row-major (ny rows of nx) Float32Array -> number[][] for Plotly. */
export function toRows(a: Float32Array, nx: number, ny: number): number[][] {
  const out: number[][] = new Array(ny);
  for (let j = 0; j < ny; j++) out[j] = Array.from(a.subarray(j * nx, (j + 1) * nx));
  return out;
}

export function linspace(a: number, b: number, n: number): number[] {
  const out = new Array(n);
  for (let i = 0; i < n; i++) out[i] = a + ((b - a) * i) / (n - 1);
  return out;
}

export function maxOf(a: ArrayLike<number>): number {
  let m = -Infinity;
  for (let i = 0; i < a.length; i++) if (a[i] > m) m = a[i];
  return m;
}
