import type { Metadata, Viewport } from 'next';
import { Inter, Space_Grotesk } from 'next/font/google';
// MapLibre CSS must load globally from the root layout — importing it inside a
// lazily-loaded client component can silently break the chunk in App Router.
import 'maplibre-gl/dist/maplibre-gl.css';
import './globals.css';

const body = Inter({ subsets: ['latin'], variable: '--font-body', display: 'swap' });
const display = Space_Grotesk({ subsets: ['latin'], variable: '--font-display', display: 'swap' });

export const metadata: Metadata = {
  title: 'Vegvisir — Disaster Intelligence for Kerala & South India',
  description:
    'Real-time disaster monitoring and risk assessment: live rainfall, hazard alerts, river levels, landslide susceptibility and population exposure on one interactive map.',
  keywords: ['Kerala', 'disaster management', 'flood monitoring', 'landslide', 'rainfall', 'KSDMA', 'dashboard'],
  metadataBase: new URL('https://vegvisir.vercel.app'),
  openGraph: {
    title: 'Vegvisir — see the storm before it arrives',
    description: 'Live disaster intelligence for Kerala & South India.',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Vegvisir — see the storm before it arrives',
    description: 'Live disaster intelligence for Kerala & South India.',
  },
};

export const viewport: Viewport = {
  themeColor: '#05070d',
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${body.variable} ${display.variable}`}>
      <head>
        {/* R4 — shave first-map-paint latency: warm up the tile/style hosts and
            preload the polished dark style JSON that upgrades the boot basemap. */}
        <link rel="preconnect" href="https://basemaps.cartocdn.com" crossOrigin="anonymous" />
        <link rel="dns-prefetch" href="https://basemaps.cartocdn.com" />
        <link rel="dns-prefetch" href="https://server.arcgisonline.com" />
        <link rel="dns-prefetch" href="https://gibs.earthdata.nasa.gov" />
        <link rel="dns-prefetch" href="https://tile.openstreetmap.org" />
        <link
          rel="preload"
          as="fetch"
          href="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
          crossOrigin="anonymous"
        />
      </head>
      <body className="bg-ink-950 font-body text-ink-200 antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-ink-950"
        >
          Skip to map
        </a>
        <main id="main">{children}</main>
      </body>
    </html>
  );
}
