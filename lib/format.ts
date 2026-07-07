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

export function mm(v: number): string {
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} mm`;
}

export const SEVERITY_LABELS: Record<Severity, string> = {
  green: 'Normal',
  yellow: 'Watch',
  orange: 'Alert',
  red: 'Severe',
};
