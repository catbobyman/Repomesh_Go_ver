import type { RoomSnapshot } from "./types";

const roleMark: Record<string, string> = { leader: "L", worker: "W", manager: "M", user: "你", system: "S" };

export function RoomView({
  room,
  onBack,
  onOpenIssue,
  onOpenConversation,
}: {
  room: RoomSnapshot;
  onBack: () => void;
  onOpenIssue: (issueId: string) => void;
  onOpenConversation: (conversationId: string) => void;
}) {
  return (
    <div className="ws-panel">
      <div className="ws-source">
        <button onClick={onBack}>← 返回 Issue</button>
        <span>Leader 房间 · 只读 · 来源 Issue</span>
      </div>
      <header className="ws-top">
        <div>
          <h1>{room.displayName}</h1>
          <p>
            {room.upstream.roomKind} · {room.upstream.lifecycle} · 内部房间 {room.roomId}
          </p>
        </div>
      </header>
      <div className="ws-details">
        <p className="ws-quiet">映射 AgentTeams Matrix 语义，界面仍是 RepoMesh 气泡，不嵌入 Element。浏览器只持有内部 roomId。</p>
        {room.environment !== null && (
          <details className="ws-notice">
            <summary>本仓工作环境</summary>
            <p>{room.environment.repositoryDisplayName}</p>
            <p className="ws-quiet">{room.environment.attemptLabel} · {room.environment.changeSetId}</p>
            <p className="ws-quiet">{room.environment.workDirNote}</p>
          </details>
        )}
        <div className="ws-chat" style={{ padding: "12px 0 24px" }}>
          {room.messages.map((message) => (
            <article className="ws-message" key={message.id}>
              <div className="ws-message-head">
                <span className="ws-role-mark" aria-hidden="true">{roleMark[message.author.role] ?? "?"}</span>
                <span>{message.author.displayName}</span>
                <time>{message.createdAt.replace("T", " ").replace("Z", "")}</time>
              </div>
              <p style={{ whiteSpace: "pre-wrap", margin: "8px 0" }}>{message.content}</p>
            </article>
          ))}
        </div>
      </div>
      {room.readOnly && (
        <div className="ws-composer-wrap">
          <div className="ws-readonly-bar">
            <span>Leader 房间只读 · 在主会话与 Manager 沟通</span>
            <span>
              <button onClick={() => onOpenIssue(room.navigation.issueId)}>返回 Issue</button>
              <button onClick={() => onOpenConversation(room.navigation.conversationId)}>进入主房间</button>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
