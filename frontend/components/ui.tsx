import type { ReactNode } from "react";
import { X } from "lucide-react";

type Tone = "neutral" | "primary" | "success" | "warning" | "danger";

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: Tone }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

const SUCCESS = new Set(["active", "approved", "confirmed", "resolved", "payment_released", "verified", "completed", "accepted"]);
const WARNING = new Set(["submitted", "under_review", "pending", "invitation_sent", "awaiting_agreement", "awaiting_counterparty", "open", "proposed", "revision_requested", "in_progress"]);
const DANGER = new Set(["cancelled", "disputed", "failed", "mismatch", "rejected"]);

export function StatusBadge({ status }: { status: string }) {
  const tone: Tone = SUCCESS.has(status) ? "success" : WARNING.has(status) ? "warning" : DANGER.has(status) ? "danger" : "primary";
  return <Badge tone={tone}><span className="dot" />{status.replaceAll("_", " ")}</Badge>;
}

export function StatCard({ label, value, icon, hint }: { label: string; value: ReactNode; icon?: ReactNode; hint?: string }) {
  return (
    <div className="metricCard">
      <div className="rowBetween">
        <span className="metricLabel">{label}</span>
        {icon && <span className="metricIcon">{icon}</span>}
      </div>
      <strong className="metricValue">{value}</strong>
      {hint && <small>{hint}</small>}
    </div>
  );
}

export function Avatar({ name, large = false }: { name: string; large?: boolean }) {
  const initials = name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
  return <span className={large ? "avatarLg" : "avatar"} aria-hidden="true">{initials || "FF"}</span>;
}

export function EmptyState({ icon, title, description, action }: { icon?: ReactNode; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="emptyState">
      {icon && <div className="emptyStateIcon">{icon}</div>}
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
    </div>
  );
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <div key={index} className="skeleton skeletonLine" style={{ width: `${90 - index * 12}%` }} />
      ))}
    </div>
  );
}

export function Progress({ value, label }: { value: number; label?: string }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className="stack" style={{ gap: 6 }}>
      {label && <div className="rowBetween"><small>{label}</small><small>{Math.round(clamped)}%</small></div>}
      <div className="progressTrack" role="progressbar" aria-valuenow={Math.round(clamped)} aria-valuemin={0} aria-valuemax={100}>
        <div className="progressFill" style={{ width: `${clamped}%` }} />
      </div>
    </div>
  );
}

export function SectionHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="sectionHead">
      <div><h2>{title}</h2>{subtitle && <p className="cardSubtitle">{subtitle}</p>}</div>
      {action}
    </div>
  );
}

export function Toast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return (
    <div className="toast" role="status">
      <span>{message}</span>
      <button className="linkBtn" onClick={onDismiss} aria-label="Dismiss notification" style={{ color: "white" }}><X size={15} /></button>
    </div>
  );
}

export function BarChart({ data }: { data: { label: string; value: number }[] }) {
  const max = Math.max(...data.map((item) => item.value), 1);
  return (
    <div className="barChart">
      {data.map((item) => (
        <div className="barChartCol" key={item.label}>
          <div className="barChartBar" style={{ height: `${Math.max(3, (item.value / max) * 100)}%` }} title={`${item.label}: ${item.value}`} />
          <span className="barChartLabel">{item.label}</span>
        </div>
      ))}
    </div>
  );
}
