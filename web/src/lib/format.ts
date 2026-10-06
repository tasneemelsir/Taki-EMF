// Number formatting used across the app. Field values use a fixed number of
// significant figures so digits do not jitter as a slider moves.

export function fmt(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—';
  const a = Math.abs(v);
  if (a === 0) return '0';
  if (a >= 1000) return v.toFixed(0);
  if (a >= 100) return v.toFixed(Math.max(0, digits - 3));
  if (a >= 10) return v.toFixed(Math.max(0, digits - 2));
  if (a >= 1) return v.toFixed(Math.max(0, digits - 1));
  if (a >= 0.1) return v.toFixed(digits);
  if (a >= 0.001) return v.toFixed(digits + 1);
  return v.toExponential(2);
}

export const fx = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined || !Number.isFinite(v) ? '—' : v.toFixed(d);

export const pct = (v: number | null | undefined, d = 0) =>
  v === null || v === undefined || !Number.isFinite(v) ? '—' : `${v.toFixed(d)}%`;

/** Reduction as a signed change: 35 -> "-35%", -8 -> "+8%". */
export function change(redPct: number | null | undefined, d = 0): string {
  if (redPct === null || redPct === undefined || !Number.isFinite(redPct)) return '—';
  const c = -redPct, a = Math.abs(c);
  // near-total reductions keep their decimals: 99.6 reads "−99.6%", not "−100%"
  const digits = a >= 99 && a < 99.995 ? Math.max(d, a < 99.95 ? 1 : 2) : d;
  const text = a.toFixed(digits);
  if (Number(text) === 0) return `${text}%`;                    // no "−0%"
  return `${c > 0 ? '+' : '−'}${text}%`;
}

/** A current in amperes: whole numbers once it is large enough for the decimals not to matter. */
export const amps = (v: number | null | undefined) =>
  v === null || v === undefined || !Number.isFinite(v) ? '—' : Math.abs(v) >= 100 ? v.toFixed(0) : fmt(v, 3);

/** A field value that has all but vanished next to its reference prints as "≈ 0". */
export const near0 = (v: number, ref: number) => (Math.abs(v) < Math.abs(ref) * 1e-3 ? '≈ 0' : fmt(v));

export const dB = (v: number | null | undefined) =>
  v === null || v === undefined || !Number.isFinite(v) ? '—' : `${v.toFixed(1)} dB`;

export function sci(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—';
  if (v === 0) return '0';
  const e = Math.floor(Math.log10(Math.abs(v)));
  if (e >= -2 && e <= 3) return fmt(v);
  const m = v / Math.pow(10, e);
  return `${m.toFixed(2)}×10${sup(e)}`;
}

function sup(n: number): string {
  const map: Record<string, string> = { '-': '⁻', '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹' };
  return String(n).split('').map((c) => map[c] ?? c).join('');
}

const two = (n: number) => String(n).padStart(2, '0');

/** Today on the reader's own clock, for file names: 2026-10-07. */
export function localDay(d: Date = new Date()): string {
  return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}`;
}

/** Now on the reader's own clock, for the date a report carries: a published copy's clock is hours away. */
export function localStamp(d: Date = new Date()): string {
  return `${localDay(d)} ${two(d.getHours())}:${two(d.getMinutes())}`;
}

export function ago(ts: number): string {
  const s = Date.now() / 1000 - ts;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)} d ago`;
  return new Date(ts * 1000).toLocaleDateString();
}

export const STATUS_LABEL: Record<string, string> = {
  PASS: 'Compliant', MARGINAL: 'Low margin', FAIL: 'Exceeds limit', NOT_ASSESSED: 'No limit',
};
export const STATUS_CLASS: Record<string, string> = { PASS: 'pass', MARGINAL: 'marginal', FAIL: 'fail', NOT_ASSESSED: 'na' };
export const STATUS_TONE: Record<string, string> = { PASS: 'good', MARGINAL: 'warn', FAIL: 'bad', NOT_ASSESSED: '' };
export const STATUS_VAR: Record<string, string> = { PASS: 'var(--green)', MARGINAL: 'var(--amber)', FAIL: 'var(--red)', NOT_ASSESSED: 'var(--steel)' };

export function csv(rows: (string | number | null | undefined)[][]): string {
  return rows.map((r) => r.map((c) => {
    const s = c === null || c === undefined ? '' : String(c);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }).join(',')).join('\n');
}

export function clamp(v: number, lo: number, hi: number) { return Math.max(lo, Math.min(hi, v)); }
