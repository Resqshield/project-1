/** @type {import('next').NextConfig} */

const isProd = process.env.NODE_ENV === 'production';

/**
 * Content-Security-Policy — production only (Next dev server needs eval/HMR).
 * Every external host the app touches is allowlisted explicitly; if you add a
 * data source, add its host here or the browser will (correctly) block it.
 */
const TILE_HOSTS = [
  'https://basemaps.cartocdn.com',
  'https://*.basemaps.cartocdn.com',
  'https://tiles.openfreemap.org',
  'https://tile.openstreetmap.org',
  'https://server.arcgisonline.com',
  'https://gibs.earthdata.nasa.gov',
].join(' ');

const csp = [
  `default-src 'self'`,
  // Next.js injects inline bootstrap scripts; no third-party script is loaded.
  `script-src 'self' 'unsafe-inline'`,
  // Tailwind/emotion-free; 'unsafe-inline' needed for Next font/style injection + MapLibre.
  `style-src 'self' 'unsafe-inline'`,
  // Map tiles + globe textures (unpkg) + data-URI sprites.
  `img-src 'self' data: blob: ${TILE_HOSTS} https://unpkg.com`,
  // MapLibre fetches styles/tiles/glyphs via fetch; district boundaries from GitHub raw.
  `connect-src 'self' ${TILE_HOSTS} https://raw.githubusercontent.com https://unpkg.com`,
  // MapLibre runs its worker from a blob URL.
  `worker-src 'self' blob:`,
  `font-src 'self' data:`,
  `object-src 'none'`,
  `base-uri 'self'`,
  `form-action 'self'`,
  `frame-ancestors 'none'`,
  `upgrade-insecure-requests`,
].join('; ');

const securityHeaders = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), payment=()' },
  { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains' },
  ...(isProd ? [{ key: 'Content-Security-Policy', value: csp }] : []),
];

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false, // don't advertise the framework version
  experimental: {
    optimizePackageImports: ['three'],
  },
  async headers() {
    return [
      { source: '/:path*', headers: securityHeaders },
      {
        source: '/data/:path*',
        headers: [
          { key: 'Cache-Control', value: 'public, max-age=86400, stale-while-revalidate=604800' },
        ],
      },
    ];
  },
};

export default nextConfig;
