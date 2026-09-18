import { StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import RealMapPage from "./realmap/RealMapPage.jsx"

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
      <RealMapPage />
    </Suspense>
  </StrictMode>,
)
