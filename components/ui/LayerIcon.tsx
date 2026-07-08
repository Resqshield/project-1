import type { LayerId } from '@/lib/types';

/**
 * Distinctive icon per layer — each animates subtly while its layer is active,
 * so the panel itself communicates "this is live on the map".
 * Pure SVG + CSS keyframes (see globals.css `veg-*`); reduced-motion safe.
 */
export default function LayerIcon({ id, active }: { id: LayerId; active: boolean }) {
  const cls = active ? 'text-accent' : 'text-ink-400';
  const anim = (name: string) => (active ? name : '');

  switch (id) {
    case 'risk':
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className={cls} aria-hidden>
          <path d="M12 3l7 3v5c0 4.4-3 8.2-7 9.5C8 19.2 5 15.4 5 11V6l7-3z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          <circle cx="12" cy="11" r="2.6" fill="currentColor" className={anim('veg-pulse-core')} />
        </svg>
      );
    case 'rainfall':
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className={cls} aria-hidden>
          <path d="M7 12a4.5 4.5 0 1 1 .6-8.96A5.5 5.5 0 0 1 18.4 5.5 3.75 3.75 0 0 1 17.5 12H7z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          <g stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <line x1="8.5" y1="15" x2="8.5" y2="18" className={anim('veg-drop')} />
            <line x1="12" y1="15.5" x2="12" y2="18.5" className={anim('veg-drop veg-delay-1')} />
            <line x1="15.5" y1="15" x2="15.5" y2="18" className={anim('veg-drop veg-delay-2')} />
          </g>
        </svg>
      );
    case 'alerts':
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className={cls} aria-hidden>
          <path d="M12 4 21 19H3L12 4z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" className={anim('veg-blink')} />
          <path d="M12 10v4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          <circle cx="12" cy="16.6" r="1" fill="currentColor" />
        </svg>
      );
    case 'quakes':
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className={cls} aria-hidden>
          <path
            d="M2 12h4l2-6 3 12 3-9 2 3h6"
            stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
            pathLength="100" strokeDasharray="100"
            className={anim('veg-trace')}
          />
        </svg>
      );
    case 'gauges':
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className={cls} aria-hidden>
          <g stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
            <path d="M2.5 8c2 -1.6 4 -1.6 6 0s4 1.6 6 0 4 -1.6 6 0" className={anim('veg-wave')} />
            <path d="M2.5 13c2 -1.6 4 -1.6 6 0s4 1.6 6 0 4 -1.6 6 0" className={anim('veg-wave veg-delay-1')} />
            <path d="M2.5 18c2 -1.6 4 -1.6 6 0s4 1.6 6 0 4 -1.6 6 0" className={anim('veg-wave veg-delay-2')} />
          </g>
        </svg>
      );
    case 'infrastructure':
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className={cls} aria-hidden>
          <path d="M4 21V9l8-5 8 5v12" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          <path d="M4 21h16" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          <path d="M12 10v6M9 13h6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" className={anim('veg-pulse-core')} />
        </svg>
      );
    case 'satellite':
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className={cls} aria-hidden>
          <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.6" />
          <ellipse cx="12" cy="12" rx="9" ry="3.6" stroke="currentColor" strokeWidth="1.2" opacity="0.6" transform="rotate(-18 12 12)" />
          <circle r="1.4" fill="currentColor" className={anim('veg-orbit')}>
            {active && (
              <animateMotion dur="3.2s" repeatCount="indefinite" path="M 12 12 m -8.56 2.78 a 9 3.6 -18 1 0 17.12 -5.56 a 9 3.6 -18 1 0 -17.12 5.56" />
            )}
          </circle>
        </svg>
      );
    default:
      return null;
  }
}
