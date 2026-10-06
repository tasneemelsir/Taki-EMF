// Small, dependency-free UI primitives in the Taki design system.

import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronRight, X } from 'lucide-react';
import { clamp, STATUS_CLASS, STATUS_LABEL } from '@/lib/format';
import { rampCss } from '@/lib/colors';
import { useStore } from '@/lib/store';

type Div = React.HTMLAttributes<HTMLDivElement>;

export function cx(...parts: (string | false | null | undefined)[]) { return parts.filter(Boolean).join(' '); }

export function Card({ className, title, sub, actions, children, ...rest }: Omit<Div, 'title'> & { title?: React.ReactNode; sub?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className={cx('card', className)} {...rest}>
      {(title || actions) && (
        <div className="card-head">
          <h3>{title}{sub && <span className="sub">{sub}</span>}</h3>
          {actions}
        </div>
      )}
      {children}
    </div>
  );
}

export function Eyebrow({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cx('eyebrow', className)}>{children}</div>;
}

export function Metric({ label, value, unit, sub, tone, rule, small, title }: { label: string; value: React.ReactNode; unit?: string; sub?: React.ReactNode; tone?: string; rule?: boolean; small?: boolean; title?: string }) {
  return (
    <div className={cx('metric', tone, rule && 'rule')} title={title}>
      <div className="label">{label}</div>
      <div className={cx('value', small && 'sm')}>{value}{unit && <span className="unit">{unit}</span>}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

export function Badge({ status, children }: { status: string; children?: React.ReactNode }) {
  return <span className={cx('badge', STATUS_CLASS[status] ?? 'na')}>{children ?? STATUS_LABEL[status] ?? status}</span>;
}

export function Pill({ tone, children, title }: { tone?: 'blue' | 'teal' | 'amber' | 'red' | 'green'; children: React.ReactNode; title?: string }) {
  return <span className={cx('pill', tone)} title={title}>{children}</span>;
}

export function Note({ kind, children, className }: { kind?: 'info' | 'warn' | 'bad' | 'good'; children: React.ReactNode; className?: string }) {
  return <div className={cx('note', kind && kind !== 'warn' && kind, className)}>{children}</div>;
}

export function Spinner() { return <span className="spinner" aria-label="Loading" />; }

export function Busy({ on }: { on: boolean }) { return on ? <div className="busy-bar" /> : null; }

export function Empty({ title, children, action }: { title: string; children?: React.ReactNode; action?: React.ReactNode }) {
  return <div className="empty"><h3>{title}</h3><div className="small">{children}</div>{action && <div className="mt-12">{action}</div>}</div>;
}

// ---------------------------------------------------------------- buttons
type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'danger'; size?: 'sm'; icon?: boolean; block?: boolean };
export const Button = React.forwardRef<HTMLButtonElement, BtnProps>(function Button({ variant, size, icon, block, className, type, ...rest }, ref) {
  return <button ref={ref} type={type ?? 'button'} className={cx('btn', variant, size, icon && 'icon', block && 'block', className)} {...rest} />;
});

// ---------------------------------------------------------------- fields
export function Field({ label, hint, help, children, className }: { label?: React.ReactNode; hint?: React.ReactNode; help?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <div className={cx('field', className)}>
      {label !== undefined && <div className="label">{label}{hint !== undefined && <span className="hint">{hint}</span>}</div>}
      {children}
      {help && <div className="help">{help}</div>}
    </div>
  );
}

function fmtNum(v: number, step?: number): string {
  if (!Number.isFinite(v)) return '';
  if (step && step < 1) {
    const d = Math.min(6, Math.max(0, Math.ceil(-Math.log10(step))));
    return String(parseFloat(v.toFixed(d)));
  }
  return String(parseFloat(v.toFixed(6)));
}

export function NumberInput({ value, onChange, min, max, step = 1, unit, disabled, id, placeholder, allowEmpty }: {
  value: number | null; onChange: (v: number) => void; min?: number; max?: number; step?: number; unit?: string;
  disabled?: boolean; id?: string; placeholder?: string; allowEmpty?: boolean;
}) {
  const [text, setText] = useState(value === null ? '' : fmtNum(value, step));
  const focused = useRef(false);
  useEffect(() => { if (!focused.current) setText(value === null ? '' : fmtNum(value, step)); }, [value, step]);
  const commit = (raw: string, final: boolean) => {
    const v = parseFloat(raw.replace(',', '.'));
    if (!Number.isFinite(v)) {
      if (final) setText(value === null ? '' : fmtNum(value, step));
      return;
    }
    const c = clamp(v, min ?? -Infinity, max ?? Infinity);
    if (final) setText(fmtNum(c, step));
    if (final || c === v) { if (c !== value) onChange(c); }
  };
  const input = (
    <input
      id={id} className="input mono" inputMode="decimal" disabled={disabled} value={text} placeholder={placeholder}
      onFocus={(e) => { focused.current = true; e.currentTarget.select(); }}
      onBlur={() => { focused.current = false; if (allowEmpty && text.trim() === '') return; commit(text, true); }}
      onChange={(e) => { setText(e.target.value); commit(e.target.value, false); }}
      onKeyDown={(e) => {
        if (e.key === 'Enter') { commit(text, true); (e.target as HTMLInputElement).blur(); }
        if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
          e.preventDefault();
          const base = Number.isFinite(parseFloat(text)) ? parseFloat(text) : (value ?? 0);
          const n = clamp(base + (e.key === 'ArrowUp' ? 1 : -1) * step * (e.shiftKey ? 10 : 1), min ?? -Infinity, max ?? Infinity);
          setText(fmtNum(n, step)); onChange(parseFloat(fmtNum(n, step)));
        }
      }}
    />
  );
  return unit ? <div className="input-unit">{input}<span className="u">{unit}</span></div> : input;
}

export function SliderField({ label, value, onChange, min, max, step = 1, unit, disabled, help, hint }: {
  label: React.ReactNode; value: number; onChange: (v: number) => void; min: number; max: number; step?: number;
  unit?: string; disabled?: boolean; help?: React.ReactNode; hint?: React.ReactNode;
}) {
  return (
    <Field label={label} hint={hint} help={help}>
      <div className="slider-row">
        <input type="range" min={min} max={max} step={step} value={clamp(value, min, max)} disabled={disabled}
               onChange={(e) => onChange(parseFloat(e.target.value))} aria-label={typeof label === 'string' ? label : undefined} />
        <NumberInput value={value} onChange={onChange} min={min} max={max} step={step} unit={unit} disabled={disabled} />
      </div>
    </Field>
  );
}

export function Select<T extends string | number>({ value, onChange, options, disabled, id }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: string; disabled?: boolean }[]; disabled?: boolean; id?: string;
}) {
  const isNum = typeof value === 'number';
  return (
    <select id={id} className="select" value={String(value)} disabled={disabled}
            onChange={(e) => onChange((isNum ? Number(e.target.value) : e.target.value) as T)}>
      {options.map((o) => <option key={String(o.value)} value={String(o.value)} disabled={o.disabled}>{o.label}</option>)}
    </select>
  );
}

export function TextInput({ value, onChange, placeholder, type = 'text', disabled, autoFocus, id, autoComplete, maxLength }: {
  value: string; onChange: (v: string) => void; placeholder?: string; type?: string; disabled?: boolean; autoFocus?: boolean; id?: string; autoComplete?: string; maxLength?: number;
}) {
  return <input id={id} className="input" type={type} value={value} placeholder={placeholder} disabled={disabled} autoFocus={autoFocus}
                autoComplete={autoComplete} maxLength={maxLength} onChange={(e) => onChange(e.target.value)} />;
}

export function Switch({ checked, onChange, label, disabled, title }: { checked: boolean; onChange: (v: boolean) => void; label?: React.ReactNode; disabled?: boolean; title?: string }) {
  return (
    <label className={cx('switch', disabled && 'disabled')} title={title}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span className="tr" />
      {label && <span>{label}</span>}
    </label>
  );
}

export function Segmented<T extends string>({ value, onChange, options, size }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: React.ReactNode; disabled?: boolean; title?: string }[]; size?: 'sm';
}) {
  return (
    <div className={cx('seg', size)} role="tablist">
      {options.map((o) => (
        <button key={o.value} type="button" role="tab" aria-selected={o.value === value} disabled={o.disabled} title={o.title}
                className={o.value === value ? 'on' : undefined} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

export function Tabs<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { value: T; label: React.ReactNode }[] }) {
  return (
    <div className="tabs" role="tablist">
      {options.map((o) => <button key={o.value} type="button" role="tab" aria-selected={o.value === value} className={o.value === value ? 'active' : undefined} onClick={() => onChange(o.value)}>{o.label}</button>)}
    </div>
  );
}

export function Chip({ on, onClick, children, tone }: { on: boolean; onClick: () => void; children: React.ReactNode; tone?: 'blue' }) {
  return <button type="button" className={cx('chip', tone, on && 'on')} aria-pressed={on} onClick={onClick}>{children}</button>;
}

export function Accordion({ title, meta, children, defaultOpen, open, onToggle }: { title: React.ReactNode; meta?: React.ReactNode; children: React.ReactNode; defaultOpen?: boolean; open?: boolean; onToggle?: (o: boolean) => void }) {
  return (
    <details className="accordion" open={open ?? defaultOpen} onToggle={(e) => onToggle?.((e.target as HTMLDetailsElement).open)}>
      <summary><ChevronRight size={14} className="chev" />{title}{meta && <span className="meta">{meta}</span>}</summary>
      <div className="body">{children}</div>
    </details>
  );
}

// ---------------------------------------------------------------- overlays
export function Modal({ title, onClose, children, footer, wide }: { title: React.ReactNode; onClose: () => void; children: React.ReactNode; footer?: React.ReactNode; wide?: boolean }) {
  useEffect(() => {
    const fn = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [onClose]);
  return createPortal(
    <div className="scrim" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={cx('modal', wide && 'wide')} role="dialog" aria-modal="true">
        <div className="modal-head"><h2>{title}</h2><Button variant="ghost" icon size="sm" onClick={onClose} aria-label="Close"><X size={16} /></Button></div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>, document.body);
}

export function Confirm({ title, children, confirmLabel = 'Confirm', danger, onConfirm, onClose }: { title: string; children: React.ReactNode; confirmLabel?: string; danger?: boolean; onConfirm: () => void; onClose: () => void }) {
  return (
    <Modal title={title} onClose={onClose} footer={<>
      <Button onClick={onClose}>Cancel</Button>
      <Button variant={danger ? 'danger' : 'primary'} onClick={() => { onConfirm(); onClose(); }}>{confirmLabel}</Button>
    </>}>
      <div className="small">{children}</div>
    </Modal>
  );
}

/** A button that opens a small menu anchored beneath it. */
export function MenuButton({ button, children, align = 'right' }: { button: (open: boolean, toggle: () => void) => React.ReactNode; children: (close: () => void) => React.ReactNode; align?: 'left' | 'right' }) {
  const [open, setOpen] = useState(false);
  const anchor = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<{ top: number; left?: number; right?: number }>({ top: 0 });
  useLayoutEffect(() => {
    if (!open || !anchor.current) return;
    const r = anchor.current.getBoundingClientRect();
    setPos(align === 'right' ? { top: r.bottom + 4, right: Math.max(8, window.innerWidth - r.right) } : { top: r.bottom + 4, left: Math.max(8, r.left) });
  }, [open, align]);
  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => { if (e.type === 'keydown' && (e as KeyboardEvent).key !== 'Escape') return; setOpen(false); };
    window.addEventListener('keydown', close); window.addEventListener('resize', close);
    return () => { window.removeEventListener('keydown', close); window.removeEventListener('resize', close); };
  }, [open]);
  return (
    <>
      <span ref={anchor} style={{ display: 'inline-flex' }}>{button(open, () => setOpen((o) => !o))}</span>
      {open && createPortal(<>
        <div style={{ position: 'fixed', inset: 0, zIndex: 49 }} onMouseDown={() => setOpen(false)} />
        <div className="menu" style={{ position: 'fixed', ...pos }} role="menu">{children(() => setOpen(false))}</div>
      </>, document.body)}
    </>
  );
}

export function Toasts() {
  const toasts = useStore((s) => s.toasts);
  const dismiss = useStore((s) => s.dismissToast);
  return createPortal(
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={cx('toast', t.kind === 'error' && 'error')} onClick={() => dismiss(t.id)}>{t.text}</div>
      ))}
    </div>, document.body);
}

// ---------------------------------------------------------------- misc
export function ColorBar({ lo, hi, unit, label, diff, dark }: { lo: string; hi: string; unit?: string; label?: string; diff?: boolean; dark?: boolean }) {
  const bg = diff
    ? (dark ? 'linear-gradient(90deg,#38E1D4,#18202F,#FB7185)' : 'linear-gradient(90deg,#0B7A75,#F2F4F5,#B3261E)')
    : rampCss();
  return (
    <div className="colorbar">
      {label && <div style={{ color: 'var(--ink)', fontFamily: 'var(--font-ui)', fontSize: 11 }}>{label}</div>}
      <div className="legend-bar" style={{ background: bg }} />
      <div className="ends"><span>{lo}</span><span>{hi}{unit ? ` ${unit}` : ''}</span></div>
    </div>
  );
}

export function PhaseDot({ phase }: { phase: string }) {
  const v = phase === 'A' ? '--phase-a' : phase === 'B' ? '--phase-b' : '--phase-c';
  return <span className="swatch" style={{ background: `var(${v})`, border: '1px solid rgba(0,0,0,.35)' }} />;
}

export function Kv({ k, v }: { k: React.ReactNode; v: React.ReactNode }) {
  return <div className="row between small" style={{ padding: '4px 0', borderBottom: '1px solid var(--line)' }}><span className="muted">{k}</span><span className="mono" style={{ textAlign: 'right' }}>{v}</span></div>;
}

export function PageHead({ title, lede, children }: { title: string; lede?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1>{lede && <p className="lede">{lede}</p>}</div>
      {children && <div className="actions">{children}</div>}
    </div>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  return error ? <Note kind="bad" className="mb-12">{error}</Note> : null;
}
