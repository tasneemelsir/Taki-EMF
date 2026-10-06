import { useMemo, useRef } from 'react';
import { useElementSize } from '@/lib/hooks';
import type { LineOut } from '@/lib/types';

/**
 * One span seen from the side: the two towers, the wires sagging between them, and what stands
 * under the line. z runs along the line, 0 at mid-span. The marker is where the cross-section on
 * the page is cut; click or drag to move it.
 */
export function SpanStrip({ halfSpan, lines, buildings, shield, z, onChange }: {
  halfSpan: number; lines: LineOut[];
  buildings: { name: string; z_offset: number; depth: number; height: number }[];
  shield: { zc: number; zh: number } | null;
  z: number; onChange: (z: number) => void;
}) {
  const [ref, size] = useElementSize<HTMLDivElement>();
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef(false);
  const H = 118, L = 16, R = 16, T = 18, B = 24;
  const W = Math.max(120, size.w - L - R);
  // every distinct wire height, as [at mid-span, at the tower]
  const wires = useMemo(() => {
    const seen = new Map<string, [number, number]>();
    for (const l of lines) for (const k of l.conductors) seen.set(`${k.y.toFixed(1)}|${k.y_att.toFixed(1)}`, [k.y, k.y_att]);
    return [...seen.values()].sort((a, b) => a[0] - b[0]);
  }, [lines]);
  if (!(halfSpan > 0) || !wires.length) return null;
  const top = Math.max(...wires.map((w) => w[1]), ...buildings.map((b) => b.height)) * 1.1;
  const X = (zz: number) => L + ((zz + halfSpan) / (2 * halfSpan)) * W;
  const Y = (y: number) => H - B - (y / top) * (H - T - B);
  const curve = (w: [number, number]) => {
    let d = '';
    for (let i = 0; i <= 40; i++) { const zz = -halfSpan + (i / 40) * 2 * halfSpan, u = zz / halfSpan; d += `${i ? 'L' : 'M'}${X(zz).toFixed(1)} ${Y(w[0] + (w[1] - w[0]) * u * u).toFixed(1)}`; }
    return d;
  };
  const zAt = (clientX: number) => {
    const r = svg.current!.getBoundingClientRect();
    let v = ((clientX - r.left - L) / W) * 2 * halfSpan - halfSpan;
    v = Math.max(-halfSpan, Math.min(halfSpan, v));
    if (Math.abs(v) < halfSpan * 0.025) v = 0;                               // snaps to mid-span and to the towers
    else if (halfSpan - Math.abs(v) < halfSpan * 0.025) v = Math.sign(v) * halfSpan;
    else v = Math.round(v);
    return v;
  };
  const move = (v: number) => { if (v !== z) onChange(v); };
  const u = Math.min(1, Math.abs(z) / halfSpan);
  const rise = (wires[0][1] - wires[0][0]) * u * u;
  const cut = buildings.filter((b) => Math.abs(z - b.z_offset) <= b.depth / 2 + 1e-6).map((b) => b.name);
  const inShield = !!shield && Math.abs(z - shield.zc) <= shield.zh + 1e-6;
  const where = z === 0 ? 'mid-span' : Math.abs(z) >= halfSpan ? 'at the tower' : `${Math.abs(z)} m from mid-span`;
  const what = [...cut, ...(inShield ? ['the shield'] : [])];
  const towerTop = Math.max(...wires.map((w) => w[1]));
  const arms = [...new Set(wires.map((w) => w[1].toFixed(1)))].map(Number);

  return (
    <div className="span-strip" ref={ref}>
      <div className="head">
        <h3>Where the slice is cut</h3>
        <span className="sub">one span from the side · click or drag to move the slice</span>
        <span className="read"><b>z = {z} m</b> · {where}{rise >= 0.05 ? ` · wires ${rise.toFixed(1)} m higher than at mid-span` : z === 0 ? ' · wires at their lowest' : ''} · {what.length ? `cuts through ${what.join(' and ')}` : 'only the line is in this slice'}</span>
      </div>
      <svg ref={svg} width="100%" height={H} role="slider" tabIndex={0} aria-label="Position of the slice along the span, in metres from mid-span"
        aria-valuemin={-halfSpan} aria-valuemax={halfSpan} aria-valuenow={z}
        onPointerDown={(e) => { drag.current = true; (e.target as Element).setPointerCapture?.(e.pointerId); move(zAt(e.clientX)); }}
        onPointerMove={(e) => { if (drag.current) move(zAt(e.clientX)); }}
        onPointerUp={() => { drag.current = false; }} onPointerCancel={() => { drag.current = false; }}
        onKeyDown={(e) => {
          const s = e.shiftKey ? 20 : 5;
          if (e.key === 'ArrowLeft') { move(Math.max(-halfSpan, z - s)); e.preventDefault(); }
          else if (e.key === 'ArrowRight') { move(Math.min(halfSpan, z + s)); e.preventDefault(); }
          else if (e.key === 'Home') { move(0); e.preventDefault(); }
        }}>
        <line className="ground" x1={0} x2={size.w} y1={Y(0)} y2={Y(0)} />
        {[-1, 1].map((s) => (
          <g key={s} className="tower">
            <path d={`M${X(s * halfSpan) - 5} ${Y(0)}L${X(s * halfSpan)} ${Y(towerTop) - 4}L${X(s * halfSpan) + 5} ${Y(0)}`} />
            {arms.map((a) => <path key={a} d={`M${X(s * halfSpan) - 7} ${Y(a)}h14`} />)}
          </g>
        ))}
        {buildings.map((b, i) => {
          const x0 = X(Math.max(-halfSpan, b.z_offset - b.depth / 2)), x1 = X(Math.min(halfSpan, b.z_offset + b.depth / 2));
          return x1 > x0 ? (
            <g key={i}>
              <rect className="bld" x={x0} y={Y(b.height)} width={x1 - x0} height={Y(0) - Y(b.height)} />
              {Y(0) - Y(b.height) >= 16 && x1 - x0 >= 40
                ? <text className="lbl" x={(x0 + x1) / 2} y={(Y(0) + Y(b.height)) / 2 + 3.5} textAnchor="middle">{b.name}</text>
                : <text className="lbl" x={(x0 + x1) / 2} y={Y(b.height) - 4} textAnchor="middle">{b.name}</text>}
            </g>
          ) : null;
        })}
        {shield && <line className="shield" x1={X(Math.max(-halfSpan, shield.zc - shield.zh))} x2={X(Math.min(halfSpan, shield.zc + shield.zh))} y1={Y(0) + 3.5} y2={Y(0) + 3.5}><title>Length of the shield along the line</title></line>}
        {wires.map((w, i) => <path key={i} className={i === 0 ? 'wire low' : 'wire'} d={curve(w)} />)}
        <text className="tick" x={X(-halfSpan)} y={H - 6} textAnchor="start">tower</text>
        <text className="tick" x={X(0)} y={H - 6} textAnchor="middle">mid-span, z = 0</text>
        <text className="tick" x={X(halfSpan)} y={H - 6} textAnchor="end">tower</text>
        <g className="cut">
          <line x1={X(z)} x2={X(z)} y1={T - 6} y2={Y(0)} />
          <circle cx={X(z)} cy={T - 6} r={5} />
        </g>
      </svg>
    </div>
  );
}
