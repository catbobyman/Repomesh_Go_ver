import { useMemo, useState } from "react";
import { dispatchLabel, kindLabel, nativeStatusLabel, nodeStatusLine, workflowStatusLabel } from "./labels";
import type { AnalysisSnapshot, IssueCreationConversations, IssueCreationOptions, IssueDelivery, IssueListItem, IssueRooms, IssueSnapshot, PlanGraph, PlanGraphNode } from "./types";

function runtimeText(rooms: IssueRooms | null): string {
  if (rooms === null) return "运行状态待确认";
  if (rooms.main.availability === "unknown") return "运行状态待确认；尚未取得主房间就绪依据。";
  if (rooms.main.availability === "preparing") return "正在准备主房间。";
  if (rooms.main.availability === "unavailable") return "主房间暂不可用。";
  return "主房间可进入。";
}

const nodeLayout: Record<string, { x: number; y: number }> = {
  "svc-01": { x: 24, y: 40 },
  "svc-02": { x: 268, y: 40 },
  "svc-03": { x: 512, y: 40 },
  "ui-01": { x: 268, y: 200 },
  "ui-02": { x: 512, y: 200 },
  "overlay-combination": { x: 756, y: 120 },
  "overlay-verify": { x: 1000, y: 120 },
};

const NODE_W = 188;
const NODE_H = 92;

function pointFor(id: string, index: number): { x: number; y: number } {
  return nodeLayout[id] ?? { x: 24 + (index % 4) * 240, y: 40 + Math.floor(index / 4) * 160 };
}

function tone(node: PlanGraphNode): "done" | "active" | "ready" | "wait" {
  if (node.dispatchState === "completed" || node.nativeStatus === "completed") return "done";
  if (node.dispatchState === "attempt_active" || node.nativeStatus === "in_progress" || node.nativeStatus === "submitted") return "active";
  if (node.inNext) return "ready";
  return "wait";
}

export function IssueListView({ issues, onOpen, onCreate }: { issues: IssueListItem[]; onOpen: (id: string) => void; onCreate: () => void }) {
  return (
    <div className="ws-panel">
      <header className="ws-top">
        <div>
          <p>订单系统 / Issue</p>
          <h1>Issue</h1>
          <p>订单系统 · {issues.length} 条独立工作事项</p>
        </div>
        <button className="ws-primary" style={{ width: "auto" }} onClick={onCreate}>＋ 创建 Issue</button>
      </header>
      <div className="ws-details">
        {issues.map((issue) => (
          <div className="ws-issue-row" key={issue.id}>
            <div>
              <button onClick={() => onOpen(issue.id)}><strong>#{issue.number} {issue.title}</strong></button>
              <p className="ws-quiet">{issue.repositoryIds.length} 个涉及仓库 · 主 ChangeSet {issue.mainChangeSetId}</p>
            </div>
            <span className="ws-pill">记录已建立</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function IssueOverview({
  issue, rooms, onOpenConversation, onOpenPlan, onOpenDelivery, onOpenRoom, onBack,
}: {
  issue: IssueSnapshot;
  rooms: IssueRooms | null;
  onOpenConversation: (id: string) => void;
  onOpenPlan: () => void;
  onOpenDelivery: () => void;
  onOpenRoom: (roomId: string) => void;
  onBack: () => void;
}) {
  const enterableLeaders = rooms?.leaders.filter((item) => item.canEnter && item.roomId !== null) ?? [];
  return (
    <div className="ws-panel">
      <header className="ws-top">
        <div>
          <p>订单系统 / Issue</p>
          <button onClick={onBack}>← Issue 列表</button>
          <h1>#{issue.number} {issue.title}</h1>
        </div>
      </header>
      <div className="ws-details">
        <span className="ws-pill green">记录已保存</span>
        <div className="ws-runtime"><span>{runtimeText(rooms)}</span><span className="ws-quiet">重新读取走 GET /api/issues 与 /rooms</span></div>
        <h2>工作目标</h2>
        <p>{issue.description}</p>
        <p className="ws-quiet">涉及仓库 · {issue.repositoryIds.length}</p>
        <div className="ws-tabs">
          {issue.repositoryIds.map((id) => <span className="ws-pill" key={id}>{id}</span>)}
        </div>
        <h2>关联会话</h2>
        <div className="ws-notice">
          <p>Manager 主房间映射上游 task_room，不是 Admin DM。</p>
          <button onClick={() => onOpenConversation(issue.source.conversationId)}>查看关联会话 →</button>
          {rooms?.main.canEnter === true && rooms.main.roomId !== null ? (
            <button onClick={() => onOpenConversation(issue.source.conversationId)}>进入主房间 →</button>
          ) : (
            <p className="ws-quiet">尚无主房间就绪依据，暂不可进入</p>
          )}
        </div>
        <h2>仓库房间</h2>
        {enterableLeaders.length === 0 && (
          <div className="ws-notice">
            <p>当前没有可进入的 Leader 房间。</p>
            <p className="ws-quiet">空列表只表示当前无可进入入口，不推断无委派。Leader 房间映射上游 team_room，只读。</p>
          </div>
        )}
        {enterableLeaders.map((leader) => (
          <section className="ws-notice" key={leader.repositoryIssueId}>
            <h2 style={{ margin: "0 0 8px", fontSize: 15 }}>{leader.displayName}</h2>
            <p className="ws-quiet">Leader 房间 · 只读 · {leader.roomId}</p>
            <button onClick={() => leader.roomId !== null && onOpenRoom(leader.roomId)}>进入 Leader 房间 →</button>
          </section>
        ))}
        <p className="ws-quiet">主 ChangeSet {issue.mainChangeSetId} · 状态观察与记录保存分开。</p>
        <div className="ws-tabs">
          <button className="is-on">概览与房间</button>
          <button onClick={onOpenPlan}>任务图与规格</button>
          <button onClick={onOpenDelivery}>验证与交付</button>
        </div>
      </div>
    </div>
  );
}

export function IssuePlanView({ issue, graph, onBack, onDelivery }: { issue: IssueSnapshot; graph: PlanGraph; onBack: () => void; onDelivery: () => void }) {
  const [selected, setSelected] = useState(graph.nodes[0]?.id ?? "");
  const [zoom, setZoom] = useState(1);
  const node = graph.nodes.find((item) => item.id === selected) ?? graph.nodes[0];
  const positions = useMemo(
    () => Object.fromEntries(graph.nodes.map((item, index) => [item.id, pointFor(item.id, index)])),
    [graph.nodes],
  );
  const incoming = graph.edges.filter((edge) => edge.to === node?.id).map((edge) => graph.nodes.find((item) => item.id === edge.from)?.title ?? edge.from);
  const overlayReasons = node === undefined ? [] : (graph.businessOverlay.blockingReasons[node.id] ?? []);
  const width = 1220;
  const height = 340;
  return (
    <div className="ws-panel">
      <header className="ws-top">
        <div>
          <button onClick={onBack}>← Issue #{issue.number}</button>
          <h1>#{issue.number} {issue.title}</h1>
          <p>计划 {graph.planVersion} · 第 {graph.round} 轮 · native + Controller workflow · 只读</p>
        </div>
      </header>
      <div className="ws-details ws-dag-page">
        <div className="ws-tabs">
          <button onClick={onBack}>概览与房间</button>
          <button className="is-on">任务图与规格</button>
          <button onClick={onDelivery}>验证与交付</button>
        </div>
        {graph.nodes.length === 0 && <p className="ws-quiet">当前没有可读计划。记录保存不等于已经排图。</p>}
        {graph.nodes.length > 0 && (
          <>
            <div className="ws-dag-toolbar">
              <p className="ws-quiet">箭头是 depends_on / workflow.edges。workflow.next 是候选就绪，不是派工。</p>
              <div className="ws-dag-tools">
                <button type="button" onClick={() => setZoom((value) => Math.max(0.8, value - 0.2))}>−</button>
                <span>{Math.round(zoom * 100)}%</span>
                <button type="button" onClick={() => setZoom((value) => Math.min(1.6, value + 0.2))}>＋</button>
                <button type="button" onClick={() => setZoom(1)}>重置</button>
              </div>
            </div>
            <div className="ws-dag-viewport" aria-label="当前轮次只读任务依赖图">
              <svg className="ws-dag-svg" style={{ width: `${zoom * 100}%` }} viewBox={`0 0 ${width} ${height}`} role="group">
                <text x="24" y="22" fill="#8e8e8e" fontSize="12">仓内上游 Project</text>
                <text x="756" y="22" fill="#8e8e8e" fontSize="12">RepoMesh overlay</text>
                {graph.edges.map((edge) => {
                  const from = positions[edge.from];
                  const to = positions[edge.to];
                  if (from === undefined || to === undefined) return null;
                  const x1 = from.x + NODE_W;
                  const y1 = from.y + NODE_H / 2;
                  const x2 = to.x;
                  const y2 = to.y + NODE_H / 2;
                  const selectedEdge = edge.from === selected || edge.to === selected;
                  return <path key={`${edge.from}-${edge.to}`} d={`M${x1} ${y1} C${x1 + 36} ${y1}, ${x2 - 36} ${y2}, ${x2} ${y2}`} className={selectedEdge ? "is-on" : undefined} />;
                })}
                {graph.nodes.map((item) => {
                  const point = positions[item.id];
                  return (
                    <g
                      key={item.id}
                      role="button"
                      tabIndex={0}
                      aria-label={`${item.title}：${nodeStatusLine(item)}`}
                      aria-pressed={item.id === selected}
                      className={`ws-dag-node-svg ${tone(item)}${item.id === selected ? " is-on" : ""}`}
                      transform={`translate(${point.x},${point.y})`}
                      onClick={() => setSelected(item.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelected(item.id);
                        }
                      }}
                    >
                      <rect width={NODE_W} height={NODE_H} rx="9" />
                      <text x="14" y="22" fontSize="10" fill="#9c9c9c">{kindLabel[item.kind]} · {item.owner}</text>
                      <text x="14" y="46" fontSize="15" fill="#e2e2e2">{item.title}</text>
                      <circle cx="18" cy="70" r="3" />
                      <text x="28" y="74" fontSize="11">{nodeStatusLine(item)}</text>
                    </g>
                  );
                })}
              </svg>
            </div>
            <div className="ws-dag-legend">
              <span>native 状态来自 plan_dag / meta.json</span>
              <span>压缩态来自 GET …/workflow</span>
              <span>next[] ≠ 派工</span>
            </div>
          </>
        )}
        {node !== undefined && (
          <section className="ws-dag-detail">
            <h2 style={{ margin: "0 0 8px", fontSize: 15 }}>{node.title} · {kindLabel[node.kind]}</h2>
            <div className="ws-kv"><span>所属范围</span><span>{node.owner}</span></div>
            <div className="ws-kv"><span>前置依赖</span><span>{incoming.join("、") || "无前置任务"}</span></div>
            <div className="ws-kv"><span>native status</span><span>{node.nativeStatus === null ? "无（overlay）" : nativeStatusLabel[node.nativeStatus]}</span></div>
            <div className="ws-kv"><span>workflow status</span><span>{node.workflowStatus === null ? "无（overlay）" : workflowStatusLabel[node.workflowStatus]}</span></div>
            <div className="ws-kv"><span>workflow.next</span><span>{node.inNext ? "在候选就绪集合中 · 不是派工" : "不在 next"}</span></div>
            <div className="ws-kv"><span>RepoMesh 派工</span><span>{dispatchLabel[node.dispatchState]}</span></div>
            {overlayReasons.length > 0 && <div className="ws-kv"><span>overlay 阻塞</span><span>{overlayReasons.join("、")}</span></div>}
            <p className="ws-quiet" style={{ marginTop: 12 }}>{node.detail}</p>
          </section>
        )}
        {graph.upstreamProjects.length > 0 && (
          <section className="ws-notice" style={{ marginTop: 16 }}>
            <h2 style={{ margin: "0 0 8px", fontSize: 15 }}>上游 Project 切片</h2>
            {graph.upstreamProjects.map((project) => (
              <p key={project.projectId} className="ws-quiet">
                {project.projectId} · {project.teamId} · native {project.native.status}/{project.native.planType} · next [{project.workflow.next.join(", ") || "空"}]
              </p>
            ))}
          </section>
        )}
      </div>
    </div>
  );
}

export function IssueDeliveryView({ issue, delivery, onBack, onPlan }: { issue: IssueSnapshot; delivery: IssueDelivery; onBack: () => void; onPlan: () => void }) {
  return (
    <div className="ws-panel">
      <header className="ws-top">
        <div>
          <button onClick={onBack}>← Issue #{issue.number}</button>
          <h1>#{issue.number} {issue.title}</h1>
        </div>
      </header>
      <div className="ws-details">
        <div className="ws-tabs">
          <button onClick={onBack}>概览与房间</button>
          <button onClick={onPlan}>任务图与规格</button>
          <button className="is-on">验证与交付</button>
        </div>
        <h2>验证与交付</h2>
        <div className="ws-kv"><span>当前组合</span><span className="ws-pill amber">{delivery.combination.label}</span></div>
        <div className="ws-kv"><span>独立验证</span><span className="ws-pill">{delivery.verification.label}</span></div>
        <div className="ws-kv"><span>交付</span><span className="ws-pill">{delivery.delivery.label}</span></div>
        <h2>逐仓证据</h2>
        {delivery.repositories.map((item) => (
          <div className="ws-kv" key={item.repositoryId}>
            <span>{item.displayName}</span>
            <span className="ws-pill">{item.evidenceStatus === "candidate" ? "待候选" : item.evidenceStatus}</span>
          </div>
        ))}
        <p className="ws-quiet">正式审查与人工合并分别记录；部署状态另行表达。主 ChangeSet {delivery.mainChangeSetId}。</p>
      </div>
    </div>
  );
}

export function CreateIssueModal({
  options, conversations, analysis, onClose, onAnalyze, onSubmit,
}: {
  options: IssueCreationOptions;
  conversations: IssueCreationConversations;
  analysis: AnalysisSnapshot | null;
  onClose: () => void;
  onAnalyze: (title: string, description: string) => Promise<void>;
  onSubmit: (input: { title: string; description: string; repositoryIds: string[]; conversation: { mode: "new" } | { mode: "existing"; id: string }; analysisId: string | null }) => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [mode, setMode] = useState<"new" | "existing">("new");
  const [existingId, setExistingId] = useState(conversations.items[0]?.id ?? "");
  const [appliedAnalysis, setAppliedAnalysis] = useState<string | null>(null);
  const canAnalyze = title.trim().length > 0 && description.trim().length > 0 && options.repositoryAnalysis.availability === "available";
  const toggle = (id: string) => setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  const applyRecommendations = () => {
    if (analysis === null) return;
    const extra = analysis.recommendations.filter((item) => item.selectable).map((item) => item.repositoryId);
    setSelected((current) => [...new Set([...current, ...extra])]);
    setAppliedAnalysis(analysis.analysisId);
  };
  return (
    <div className="ws-modal-backdrop">
      <form className="ws-modal" aria-labelledby="create-issue-title" onSubmit={(event) => { event.preventDefault(); void onSubmit({ title, description, repositoryIds: selected, conversation: mode === "new" ? { mode: "new" } : { mode: "existing", id: existingId }, analysisId: appliedAnalysis }); }}>
        <h2 id="create-issue-title">创建 Issue</h2>
        <p className="ws-quiet">订单系统 · 建立独立工作事项和主 ChangeSet</p>
        <label className="ws-field">Issue 标题<input value={title} onChange={(event) => { setTitle(event.target.value); setAppliedAnalysis(null); }} /></label>
        <label className="ws-field">目标、约束与预期结果<textarea value={description} onChange={(event) => { setDescription(event.target.value); setAppliedAnalysis(null); }} /></label>
        <p className="ws-quiet">涉及仓库</p>
        {options.repositories.map((item) => (
          <label className="ws-check" key={item.repositoryId}>
            <input type="checkbox" disabled={!item.selectable} checked={selected.includes(item.repositoryId)} onChange={() => toggle(item.repositoryId)} />
            <span>{item.displayName}{item.selectable ? "" : " · App 工作授权待补齐"}</span>
          </label>
        ))}
        <button type="button" disabled={!canAnalyze} onClick={() => void onAnalyze(title, description)}>仓库分析</button>
        {analysis !== null && (
          <div className="ws-notice" style={{ marginTop: 12 }}>
            <p>{analysis.coverageNote}</p>
            {analysis.recommendations.map((item) => <p key={item.repositoryId} className="ws-quiet">{item.displayName} · {item.reason}</p>)}
            <button type="button" onClick={applyRecommendations}>应用所选建议</button>
          </div>
        )}
        <p className="ws-quiet" style={{ marginTop: 16 }}>关联会话</p>
        <div className="ws-tabs">
          <button type="button" className={mode === "new" ? "is-on" : ""} onClick={() => setMode("new")}>新建会话</button>
          <button type="button" className={mode === "existing" ? "is-on" : ""} onClick={() => setMode("existing")}>选择已有会话</button>
        </div>
        {mode === "existing" && (
          <label className="ws-field">已有会话
            <select value={existingId} onChange={(event) => setExistingId(event.target.value)}>
              {conversations.items.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
            </select>
          </label>
        )}
        <div className="ws-modal-actions">
          <button type="button" onClick={onClose}>取消</button>
          <button className="ws-primary" type="submit" disabled={!options.canSubmit || selected.length === 0 || title.trim().length === 0 || description.trim().length === 0} style={{ width: "auto" }}>创建 Issue</button>
        </div>
      </form>
    </div>
  );
}
