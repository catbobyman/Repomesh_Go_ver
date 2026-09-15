import type { ReactNode } from "react";
import type { IssueRooms, LinkedIssue } from "./types";

export type DockPanel =
  | { kind: "issue"; issueId: string }
  | { kind: "plan"; issueId: string }
  | { kind: "leader"; issueId: string; roomId: string };

function Icon({ kind }: { kind: "issue" | "dag" | "room" }) {
  if (kind === "dag") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" className="ws-dock-icon">
        <rect x="2" y="8" width="5" height="5" rx="1" />
        <rect x="16" y="2" width="5" height="5" rx="1" />
        <rect x="16" y="15" width="5" height="5" rx="1" />
        <path d="M7 10.5h5V4.5h4M12 10.5v7h4" />
      </svg>
    );
  }
  if (kind === "issue") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" className="ws-dock-icon">
        <circle cx="12" cy="12" r="8" />
        <circle cx="12" cy="12" r="2" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="ws-dock-icon">
      <path d="M4 4h16v12H9l-5 4z" />
      <path d="M8 8h8M8 12h5" />
    </svg>
  );
}

export function WorkspaceDock({
  issues,
  rooms,
  selectedIssueId,
  planAvailable,
  panel,
  compact,
  contextOpen,
  onSelectIssue,
  onToggleContext,
  onToggleCompact,
  onOpen,
}: {
  issues: LinkedIssue[];
  rooms: IssueRooms | null;
  selectedIssueId: string | null;
  planAvailable: boolean;
  panel: DockPanel | null;
  compact: boolean;
  contextOpen: boolean;
  onSelectIssue: (issueId: string) => void;
  onToggleContext: () => void;
  onToggleCompact: () => void;
  onOpen: (panel: DockPanel) => void;
}) {
  const selected = issues.find((item) => item.id === selectedIssueId) ?? issues[0] ?? null;
  const leaders = rooms?.leaders ?? [];
  const pressed = (kind: DockPanel["kind"], roomId?: string) => {
    if (panel === null || selected === null) return false;
    if (panel.kind !== kind || panel.issueId !== selected.id) return false;
    if (kind === "leader" && panel.kind === "leader") return panel.roomId === roomId;
    return true;
  };
  const openOrClose = (next: DockPanel) => onOpen(next);
  return (
    <nav className={`ws-dock${compact ? " is-compact" : ""}`} aria-label="悬浮快捷入口">
      <button
        type="button"
        aria-pressed={contextOpen}
        aria-label={selected ? `#${selected.number} ${selected.title}` : "选择关联 Issue"}
        title={selected ? `#${selected.number} ${selected.title}` : "选择关联 Issue"}
        onClick={onToggleContext}
      >
        <span className="ws-dock-symbol" aria-hidden="true">{selected ? `#${selected.number}` : "?"}</span>
        <span className="ws-dock-label">{selected ? `#${selected.number} ${selected.title}` : "选择关联 Issue"}</span>
      </button>
      {contextOpen && (
        <div className="ws-dock-context">
          <label>
            查看关联 Issue
            <select aria-label="右栏查看的 Issue" value={selected?.id ?? ""} onChange={(event) => onSelectIssue(event.target.value)}>
              {issues.map((item) => (
                <option key={item.id} value={item.id}>#{item.number} {item.title}</option>
              ))}
            </select>
          </label>
          <p>仅切换查看范围，不改变消息目标。</p>
        </div>
      )}
      <div className="ws-dock-rule" />
      <button
        type="button"
        disabled={selected === null}
        aria-pressed={pressed("issue")}
        aria-label="Issue 详情"
        title="Issue 详情"
        onClick={() => selected !== null && openOrClose({ kind: "issue", issueId: selected.id })}
      >
        <Icon kind="issue" />
        <span className="ws-dock-label">Issue 详情</span>
      </button>
      <button
        type="button"
        disabled={selected === null || !planAvailable}
        aria-pressed={pressed("plan")}
        aria-label={planAvailable ? "任务 DAG" : "任务 DAG · 暂无可读计划"}
        title={planAvailable ? "任务 DAG" : "任务 DAG · 暂无可读计划"}
        onClick={() => selected !== null && planAvailable && openOrClose({ kind: "plan", issueId: selected.id })}
      >
        <Icon kind="dag" />
        <span className="ws-dock-label">{planAvailable ? "任务 DAG" : "任务 DAG · 暂无可读计划"}</span>
      </button>
      <div className="ws-dock-rule" />
      <div className="ws-dock-caption">Leader 房间 · 只读</div>
      {leaders.length === 0 && (
        <button type="button" disabled aria-label="暂无可进入的 Leader 房间">
          <Icon kind="room" />
          <span className="ws-dock-label">暂无可进入的 Leader 房间</span>
        </button>
      )}
      {leaders.map((leader, index) => {
        const short = leader.displayName.split("/").pop() ?? leader.displayName;
        const label = `${short} · Leader`;
        const canOpen = leader.canEnter && leader.roomId !== null;
        return (
          <button
            key={leader.repositoryIssueId}
            type="button"
            disabled={!canOpen}
            aria-pressed={leader.roomId !== null && pressed("leader", leader.roomId)}
            aria-label={label}
            title={canOpen ? label : `${label} · 当前不可进入`}
            onClick={() => selected !== null && canOpen && leader.roomId !== null && openOrClose({ kind: "leader", issueId: selected.id, roomId: leader.roomId })}
          >
            <span className="ws-dock-symbol" aria-hidden="true">{index === 0 ? "L₁" : "L₂"}</span>
            <span className="ws-dock-label">{label}</span>
          </button>
        );
      })}
      <div className="ws-dock-rule" />
      <button type="button" aria-label={compact ? "展开入口文字" : "收起入口文字"} title={compact ? "展开入口文字" : "收起入口文字"} onClick={onToggleCompact}>
        <span className="ws-dock-symbol" aria-hidden="true">⇥</span>
        <span className="ws-dock-label">{compact ? "展开入口文字" : "收起入口文字"}</span>
      </button>
    </nav>
  );
}

export function DockPane({
  title,
  subtitle,
  footer,
  expanded,
  onExpand,
  onClose,
  children,
}: {
  title: string;
  subtitle: string;
  footer: string;
  expanded: boolean;
  onExpand: () => void;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <aside className={`ws-side-pane${expanded ? " is-expanded" : ""}`} aria-label="右侧内容栏">
      <header className="ws-pane-head">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <div className="ws-pane-actions">
          <button type="button" onClick={onExpand} aria-label={expanded ? "恢复面板宽度" : "扩大面板"} title={expanded ? "恢复面板宽度" : "扩大面板"}>⤢</button>
          <button type="button" onClick={onClose} aria-label="关闭右侧内容栏" title="关闭右侧内容栏">×</button>
        </div>
      </header>
      <div className="ws-pane-content">{children}</div>
      <footer className="ws-pane-footer">{footer}</footer>
    </aside>
  );
}
