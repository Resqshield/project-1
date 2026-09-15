import { Shield, AlertTriangle } from 'lucide-react';

export default function Header({ backendStatus }) {
  const connected = backendStatus === 'connected';

  return (
    <header className="header">
      <div className="header-brand">
        <div className="header-logo">
          <Shield size={28} strokeWidth={2} />
        </div>
        <div className="header-text">
          <h1 className="header-title">ResQ Shield</h1>
          <p className="header-subtitle">AI Disaster Risk Intelligence · India</p>
        </div>
      </div>

      <div className="header-meta">
        <div className={`backend-status ${connected ? 'status-ok' : 'status-error'}`}>
          <span className="status-dot" />
          {connected ? 'Backend Connected' : 'Backend Unavailable'}
        </div>
        <div className="demo-badge">
          <AlertTriangle size={13} />
          Demo / Synthetic Data
        </div>
      </div>
    </header>
  );
}
