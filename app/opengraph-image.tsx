import { ImageResponse } from 'next/og';

// S3 — branded share image so links dropped into WhatsApp/X during an event
// don't render bare. During monsoon this is the growth channel.
export const alt = 'Vegvisir — disaster intelligence for Kerala & South India';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '80px',
          background:
            'radial-gradient(1200px 600px at 80% -10%, #0e2740 0%, #0a0e1a 55%, #05070d 100%)',
          color: '#e2e8f0',
          fontFamily: 'sans-serif',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          {/* Vegvisir-style compass mark */}
          <svg width="88" height="88" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" strokeWidth="1.4">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 3v18M3 12h18M6 6l12 12M18 6 6 18" strokeWidth="0.9" opacity="0.6" />
            <circle cx="12" cy="12" r="2.4" fill="#38bdf8" stroke="none" />
          </svg>
          <div
            style={{
              fontSize: 76,
              fontWeight: 800,
              letterSpacing: '-0.02em',
              color: '#ffffff',
            }}
          >
            VEGVISIR
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 44, fontWeight: 700, color: '#ffffff', lineHeight: 1.15 }}>
            See the storm before it arrives.
          </div>
          <div style={{ fontSize: 30, color: '#aab6d4' }}>
            Live disaster intelligence for Kerala &amp; South India — rainfall, hazard alerts,
            river levels &amp; risk on one map.
          </div>
        </div>

        <div style={{ display: 'flex', gap: 16, fontSize: 22, color: '#8b98b8' }}>
          <span style={{ color: '#22c55e' }}>● live feeds</span>
          <span>·</span>
          <span>open methodology</span>
          <span>·</span>
          <span>Kerala &amp; South India</span>
        </div>
      </div>
    ),
    { ...size }
  );
}
