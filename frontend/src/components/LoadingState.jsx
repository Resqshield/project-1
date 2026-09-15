import { Loader2, WifiOff } from 'lucide-react';

export function LoadingSpinner({ message = 'Loading…' }) {
  return (
    <div className="loading-state">
      <Loader2 size={32} className="spinner-icon" />
      <p className="loading-msg">{message}</p>
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="error-state">
      <WifiOff size={32} className="error-icon" />
      <p className="error-msg">{message}</p>
      {onRetry && (
        <button className="retry-btn" onClick={onRetry} id="retry-button">
          Try Again
        </button>
      )}
    </div>
  );
}
