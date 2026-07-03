import { Loader2 } from "lucide-react";

interface LoadingOverlayProps {
  show: boolean;
  label: string;
}

export function LoadingOverlay({ show, label }: LoadingOverlayProps) {
  if (!show) return null;

  return (
    <div className="loading-overlay" role="status" aria-live="polite">
      <div className="loading-box">
        <Loader2 className="spin" size={30} />
        <span>{label}</span>
      </div>
    </div>
  );
}
