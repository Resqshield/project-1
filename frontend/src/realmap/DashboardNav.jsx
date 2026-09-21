/**
 * frontend/src/realmap/DashboardNav.jsx
 * ========================================
 * Small persona switcher shown in the top bar of all three dashboards,
 * so the four-map demo can be flipped between live during a walkthrough.
 */

const VIEWS = [
  { key: "technical", label: "Technical/Admin", href: "?view=technical" },
  { key: "authority", label: "Authority", href: "?view=authority" },
  { key: "citizen", label: "Citizen", href: "?view=citizen" },
  { key: "field", label: "Field Worker", href: "?view=field" },
];

export default function DashboardNav({ active }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      {VIEWS.map(v => (
        <a
          key={v.key}
          href={v.href}
          style={{
            padding: "5px 12px",
            borderRadius: 20,
            fontSize: 11,
            fontWeight: 600,
            textDecoration: "none",
            border: `1px solid ${active === v.key ? "#8b5cf6" : "rgba(148,163,184,0.3)"}`,
            background: active === v.key ? "rgba(139,92,246,0.2)" : "transparent",
            color: active === v.key ? "#c4b5fd" : "#94a3b8",
          }}
        >
          {v.label}
        </a>
      ))}
    </div>
  );
}
