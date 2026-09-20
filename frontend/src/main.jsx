import { StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import RealMapPage from "./realmap/RealMapPage.jsx"
import CitizenMapPage from "./realmap/CitizenMapPage.jsx"
import FieldWorkerMapPage from "./realmap/FieldWorkerMapPage.jsx"
import TechnicalMapPage from "./realmap/TechnicalMapPage.jsx"

// Four-map demo: pick a dashboard via path (/technical, /realmap, /citizen,
// /field) — no router dependency, plain pathname switch on this static SPA.
// The dev server (Vite) and the vercel.json SPA rewrite both fall back to
// index.html for unknown paths, so any of these URLs works directly.
// A legacy ?view= query param is still honored for old links/bookmarks.
const PAGES = {
  "/technical": TechnicalMapPage,
  "/realmap": RealMapPage,
  "/citizen": CitizenMapPage,
  "/field": FieldWorkerMapPage,
}
const legacyView = new URLSearchParams(window.location.search).get('view')
const LEGACY_VIEW_PAGES = { citizen: CitizenMapPage, field: FieldWorkerMapPage, technical: TechnicalMapPage, authority: RealMapPage }
const PageForView = PAGES[window.location.pathname] || LEGACY_VIEW_PAGES[legacyView] || RealMapPage

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Suspense fallback={
      <div style={{
        position: "fixed", inset: 0, background: "#0f172a",
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "#475569", fontFamily: "system-ui", fontSize: 14,
      }}>
        Loading Real Data Map…
      </div>
    }>
      <PageForView />
    </Suspense>
  </StrictMode>,
)
