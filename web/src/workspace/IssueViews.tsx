import { useState } from "react";
import type { AnalysisSnapshot, IssueCreationConversations, IssueCreationOptions, IssueDelivery, IssueListItem, IssueRooms, IssueSnapshot, PlanGraph } from "./types";
import { graphLabel } from "./ConversationView";

const kindLabel = { repo_task: "仓内任务", coordination: "业务协调", verification: "验证活动" } as const;
const layout: Record<string, { x: number; y: number }> = {
  node_contract: { x: 24, y: 148 },
  node_service: { x: 268, y: 36 },
  node_ui: { x: 268, y: 248 },
  node_combination: { x: 512, y: 148 },
  node_verify: { x: 756, y: 148 },
};

function runtimeText(rooms: IssueRooms | null): string {
  if (rooms === null) return "运行状态待确认";
  if (rooms.main.availability === "unknown") return "运行状态待确认；尚未取得主房间就绪依据。";
  if (rooms.main.availability === "preparing") return "正在准备主房间。";
  if (rooms.main.availability === "unavailable") return "主房间暂不可用。";
  return "主房间可进入。";
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
  issue, rooms, onOpenConversation, onOpenPlan, onOpenDelivery, onBack,
}: {
  issue: IssueSnapshot;
  rooms: IssueRooms | null;
  onOpenConversation: (id: string) => void;
  onOpenPlan: () => void;
  onOpenDelivery: () => void;
  onBack: () => void;
}) {
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
        <button onClick={() => onOpenConversation(issue.source.conversationId)}>查看关联会话 →</button>
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
  const node = graph.nodes.find((item) => item.id === selected) ?? graph.nodes[0];
  return (
    <div className="ws-panel">
      <header className="ws-top">
        <div>
          <button onClick={onBack}>← Issue #{issue.number}</button>
          <h1>#{issue.number} {issue.title}</h1>
          <p>计划 {graph.planVersion} · 第 {graph.round} 轮 · 当前安排只读</p>
        </div>
      </header>
      <div className="ws-details">
        <div className="ws-tabs">
          <button onClick={onBack}>概览与房间</button>
          <button className="is-on">任务图与规格</button>
          <button onClick={onDelivery}>验证与交付</button>
        </div>
        {graph.nodes.length === 0 && <p className="ws-quiet">当前没有可读计划。记录保存不等于已经排图。</p>}
        {graph.nodes.length > 0 && (
          <div className="ws-dag" aria-label="当前轮次只读任务依赖图">
            {graph.nodes.map((item) => {
              const point = layout[item.id] ?? { x: 24, y: 24 };
              return (
                <button key={item.id} className={`ws-dag-node ${item.status}${item.id === selected ? " is-on" : ""}`} style={{ left: point.x, top: point.y }} onClick={() => setSelected(item.id)}>
                  <small>{kindLabel[item.kind]} · {item.owner}</small>
                  <strong>{item.title}</strong>
                  <span className="ws-status">{graphLabel[item.status]}</span>
                </button>
              );
            })}
          </div>
        )}
        {node !== undefined && (
          <section className="ws-notice" style={{ marginTop: 16 }}>
            <h2 style={{ margin: "0 0 8px", fontSize: 15 }}>{node.title} · {kindLabel[node.kind]}</h2>
            <p>{node.detail}</p>
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
