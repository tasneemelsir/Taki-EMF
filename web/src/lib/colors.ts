// Colour ramps. Cividis is perceptually uniform and colour-vision-deficiency
// safe; it is the heat-map ramp everywhere (charts, 3-D ground map, section).

export const CIVIDIS: [number, number, number][] = [
  [0, 32, 77], [0, 42, 102], [24, 53, 108], [53, 66, 108], [76, 78, 108], [97, 91, 110],
  [116, 105, 113], [136, 119, 117], [157, 134, 117], [180, 150, 112], [204, 167, 102],
  [229, 185, 86], [253, 204, 60], [255, 234, 70],
];

export function ramp(t: number, stops: [number, number, number][] = CIVIDIS): [number, number, number] {
  t = t <= 0 ? 0 : t >= 1 ? 1 : t;
  const x = t * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(x));
  const f = x - i;
  const a = stops[i], b = stops[i + 1];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}

export function rampCss(stops: [number, number, number][] = CIVIDIS): string {
  return `linear-gradient(90deg, ${stops.map((c, i) => `rgb(${c.join(',')}) ${(i / (stops.length - 1)) * 100}%`).join(', ')})`;
}

export const PLOTLY_CIVIDIS = CIVIDIS.map((c, i) => [i / (CIVIDIS.length - 1), `rgb(${c.join(',')})`]);

// Difference maps: teal = reduced, neutral = unchanged, red = increased.
export const DIFF_SCALE = [[0, '#0B7A75'], [0.5, '#F2F4F5'], [1, '#B3261E']];
export const DIFF_SCALE_DARK = [[0, '#38E1D4'], [0.5, '#18202F'], [1, '#FB7185']];

export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function phaseColor(p: string): string {
  return cssVar(p === 'A' ? '--phase-a' : p === 'B' ? '--phase-b' : '--phase-c');
}

export const SERIES = ['--blue', '--red', '--green', '--violet', '--amber', '--steel', '--teal', '--blue-bright'];
