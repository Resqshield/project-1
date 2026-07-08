import type { Severity } from './types';

export function timeAgo(iso: string | number): string {
  const t = typeof iso === 'number' ? iso : Date.parse(iso);
  const mins = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  if (h < 48) return `${h} h ago`;
  return `${Math.round(h / 24)} d ago`;
}

/**
 * Shared numeric precision rule (S1): values ≥ 10 render as integers, values
 * below 10 keep one decimal. Prevents the "214.3 m³/s" vs "7.0 mm" vs "19 mm"
 * inconsistency — every readable quantity in the UI flows through here.
 */
export function fmtNum(v: number): string {
  if (!Number.isFinite(v)) return '—';
  const a = Math.abs(v);
  return a >= 10 ? Math.round(v).toLocaleString('en-IN') : v.toFixed(1);
}

/** A quantity with its unit, using the shared precision rule (e.g. "19 mm"). */
export function qty(v: number, unit: string): string {
  return `${fmtNum(v)} ${unit}`;
}

export function mm(v: number): string {
  return qty(v, 'mm');
}

export const SEVERITY_LABELS: Record<Severity, string> = {
  green: 'Normal',
  yellow: 'Watch',
  orange: 'Alert',
  red: 'Severe',
};
