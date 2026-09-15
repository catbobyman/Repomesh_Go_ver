import { useCallback, useEffect, useMemo, useState } from "react";
import type { ApiError } from "../api";
import { errorMessage } from "../api";
import {
  createIssue,
  readClarification,
  readConversation,
  readConversationList,
  readCreationConversations,
  readCreationOptions,
  readDelivery,
  readIssue,
  readIssueList,
  readIssueRooms,
  readMessages,
  readPlanGraph,
  readRepositoryAnalysis,
  readRoom,
  resetWorkspaceDemo,
  sendMessage,
  startRepositoryAnalysis,
} from "./client";
import { ConversationView } from "./ConversationView";
import { DockPane, WorkspaceDock, type DockPanel } from "./Dock";
import { CreateIssueModal, IssueDeliveryView, IssueListView, IssueOverview, IssuePlanView } from "./IssueViews";
import { RoomView } from "./RoomView";
import { parseWorkspaceRoute, workspacePath, type WorkspaceRoute } from "./routes";
import type {
  AnalysisSnapshot,
  ClarificationSnapshot,
  ConversationListItem,
  ConversationSnapshot,
  IssueCreationConversations,
  IssueCreationOptions,
  IssueDelivery,
  IssueListItem,
  IssueRooms,
  IssueSnapshot,
  Message,
  PlanGraph,
  RoomSnapshot,
} from "./types";
import "./workspace.css";

function sameDock(left: DockPanel, right: DockPanel): boolean {
  if (left.kind !== right.kind || left.issueId !== right.issueId) return false;
  if (left.kind === "leader" && right.kind === "leader") return left.roomId === right.roomId;
  return true;
}

export function WorkspaceApp({ path, navigate }: { path: string; navigate: (path: string) => void }) {
  const route = useMemo(() => parseWorkspaceRoute(path), [path]);
  const [issues, setIssues] = useState<IssueListItem[]>([]);
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [conversation, setConversation] = useState<ConversationSnapshot | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [clarification, setClarification] = useState<ClarificationSnapshot | null>(null);
  const [issue, setIssue] = useState<IssueSnapshot | null>(null);
  const [rooms, setRooms] = useState<IssueRooms | null>(null);
  const [graph, setGraph] = useState<PlanGraph | null>(null);
  const [delivery, setDelivery] = useState<IssueDelivery | null>(null);
  const [room, setRoom] = useState<RoomSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [options, setOptions] = useState<IssueCreationOptions | null>(null);
  const [creationConversations, setCreationConversations] = useState<IssueCreationConversations | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [dockIssueId, setDockIssueId] = useState<string | null>(null);
  const [dockPanel, setDockPanel] = useState<DockPanel | null>(null);
  const [dockCompact, setDockCompact] = useState(false);
  const [dockContext, setDockContext] = useState(false);
  const [paneExpanded, setPaneExpanded] = useState(false);
  const [dockIssue, setDockIssue] = useState<IssueSnapshot | null>(null);
  const [dockRooms, setDockRooms] = useState<IssueRooms | null>(null);
  const [dockGraph, setDockGraph] = useState<PlanGraph | null>(null);
  const [dockRoom, setDockRoom] = useState<RoomSnapshot | null>(null);

  const go = useCallback((next: WorkspaceRoute) => navigate(workspacePath(next)), [navigate]);

  const fail = useCallback((result: { kind: "error" } & ApiError) => {
    setError(errorMessage(result));
  }, []);

  const loadLists = useCallback(async () => {
    const [issuePage, conversationPage] = await Promise.all([readIssueList(), readConversationList()]);
    if (issuePage.kind === "error") return fail(issuePage);
    if (conversationPage.kind === "error") return fail(conversationPage);
    setIssues(issuePage.value.items);
    setConversations(conversationPage.value.items);
    return undefined;
  }, [fail]);

  const loadConversation = useCallback(async (conversationId: string, keepDock = false) => {
    setBusy(true);
    setError(null);
    const [snapshot, page] = await Promise.all([readConversation(conversationId), readMessages(conversationId)]);
    setBusy(false);
    if (snapshot.kind === "error") return fail(snapshot);
    if (page.kind === "error") return fail(page);
    setConversation(snapshot.value);
    setMessages(page.value.items);
    const firstIssue = snapshot.value.linkedIssues[0]?.id ?? null;
    if (!keepDock) {
      setDockIssueId(firstIssue);
      setDockPanel(null);
      setDockContext(false);
      setPaneExpanded(false);
    }
    const question = page.value.items.find((item) => item.clarificationId !== null);
    if (question?.clarificationId !== undefined && question.clarificationId !== null) {
      const current = await readClarification(conversationId, question.clarificationId);
      if (current.kind === "ok") setClarification(current.value);
      else setClarification(null);
    } else setClarification(null);
  }, [fail]);

  const loadIssueBundle = useCallback(async (issueId: string, include: "overview" | "plan" | "delivery" | "room") => {
    setBusy(true);
    setError(null);
    const snapshot = await readIssue(issueId);
    if (snapshot.kind === "error") { setBusy(false); return fail(snapshot); }
    setIssue(snapshot.value);
    const roomPage = await readIssueRooms(issueId);
    setRooms(roomPage.kind === "ok" ? roomPage.value : null);
    if (include === "plan") {
      const current = await readPlanGraph(issueId);
      setGraph(current.kind === "ok" ? current.value : null);
    }
    if (include === "delivery") {
      const current = await readDelivery(issueId);
      setDelivery(current.kind === "ok" ? current.value : null);
    }
    setBusy(false);
  }, [fail]);

  useEffect(() => {
    void loadLists();
  }, [loadLists]);

  useEffect(() => {
    const current = parseWorkspaceRoute(path);
    setRoom(null);
    if (current.kind === "conversation") void loadConversation(current.conversationId);
    if (current.kind === "issue") void loadIssueBundle(current.issueId, "overview");
    if (current.kind === "issue-plan") void loadIssueBundle(current.issueId, "plan");
    if (current.kind === "issue-delivery") void loadIssueBundle(current.issueId, "delivery");
    if (current.kind === "issue-room") {
      void (async () => {
        await loadIssueBundle(current.issueId, "room");
        const snapshot = await readRoom(current.issueId, current.roomId);
        if (snapshot.kind === "error") {
          fail(snapshot);
          setRoom(null);
          return;
        }
        setRoom(snapshot.value);
      })();
    }
    if (current.kind === "issues") setIssue(null);
  }, [path, loadConversation, loadIssueBundle, fail]);

  useEffect(() => {
    if (route.kind !== "conversation" || dockIssueId === null) {
      setDockIssue(null);
      setDockRooms(null);
      setDockGraph(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      const [snapshot, roomPage, plan] = await Promise.all([readIssue(dockIssueId), readIssueRooms(dockIssueId), readPlanGraph(dockIssueId)]);
      if (cancelled) return;
      setDockIssue(snapshot.kind === "ok" ? snapshot.value : null);
      setDockRooms(roomPage.kind === "ok" ? roomPage.value : null);
      setDockGraph(plan.kind === "ok" ? plan.value : null);
    })();
    return () => {
      cancelled = true;
    };
  }, [route.kind, dockIssueId]);

  useEffect(() => {
    if (dockPanel?.kind !== "leader") {
      setDockRoom(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      const snapshot = await readRoom(dockPanel.issueId, dockPanel.roomId);
      if (cancelled) return;
      if (snapshot.kind === "error") {
        fail(snapshot);
        setDockPanel(null);
        setDockRoom(null);
        return;
      }
      setDockRoom(snapshot.value);
    })();
    return () => {
      cancelled = true;
    };
  }, [dockPanel, fail]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && (dockPanel !== null || dockContext)) {
        setDockPanel(null);
        setDockContext(false);
        setPaneExpanded(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dockPanel, dockContext]);

  const openCreate = async () => {
    setCreating(true);
    setAnalysis(null);
    const [nextOptions, nextConversations] = await Promise.all([readCreationOptions(), readCreationConversations()]);
    if (nextOptions.kind === "ok") setOptions(nextOptions.value);
    else fail(nextOptions);
    if (nextConversations.kind === "ok") setCreationConversations(nextConversations.value);
  };

  const submitIssue = async (input: { title: string; description: string; repositoryIds: string[]; conversation: { mode: "new" } | { mode: "existing"; id: string }; analysisId: string | null }) => {
    const key = crypto.randomUUID();
    const body: Record<string, unknown> = {
      expectedCreationContextRevision: options?.creationContextRevision,
      title: input.title,
      description: input.description,
      repositoryIds: input.repositoryIds,
      conversation: input.conversation,
    };
    if (input.analysisId !== null) body.repositoryAnalysisId = input.analysisId;
    const result = await createIssue(key, body);
    if (result.kind === "error") { fail(result); return; }
    setCreating(false);
    await loadLists();
    go({ kind: "issue", issueId: result.value.issue.id });
  };

  const runAnalysis = async (title: string, description: string) => {
    if (options === null) return;
    const key = crypto.randomUUID();
    const accepted = await startRepositoryAnalysis(key, { expectedCreationContextRevision: options.creationContextRevision, title, description });
    if (accepted.kind === "error") return fail(accepted);
    const snapshot = await readRepositoryAnalysis(accepted.value.analysisId);
    if (snapshot.kind === "error") return fail(snapshot);
    setAnalysis(snapshot.value);
  };

  const send = async (content: string, replyTo?: { clarificationId: string; expectedRevision: string }) => {
    if (conversation === null) return;
    const result = await sendMessage(conversation.id, crypto.randomUUID(), replyTo === undefined ? { content } : { content, replyTo });
    if (result.kind === "error") return fail(result);
    await loadConversation(conversation.id, true);
  };

  const openDock = (next: DockPanel) => {
    setDockContext(false);
    setPaneExpanded(false);
    setDockPanel((current) => (current !== null && sameDock(current, next) ? null : next));
  };

  const waiting = busy && (
    (route.kind === "conversation" && conversation === null)
    || ((route.kind === "issue" || route.kind === "issue-plan" || route.kind === "issue-delivery") && issue === null)
    || (route.kind === "issue-room" && room === null)
  );

  const scene = useMemo(() => {
    if (creating) return "create";
    if (route.kind === "issues") return "issues";
    if (route.kind === "issue") return "overview";
    if (route.kind === "issue-plan") return "plan";
    if (route.kind === "issue-delivery") return "delivery";
    if (route.kind === "issue-room") return "room";
    if (clarification?.state === "open") return "clarification";
    return "conversation";
  }, [creating, route, clarification]);

  const showDock = route.kind === "conversation" && conversation !== null && conversation.linkedIssues.length > 0;
  const paneOpen = showDock && dockPanel !== null;
  const selectedDockIssue = conversation?.linkedIssues.find((item) => item.id === dockIssueId) ?? conversation?.linkedIssues[0] ?? null;
  const planAvailable = (dockGraph?.nodes.length ?? 0) > 0;

  let paneTitle = "";
  let paneFooter = "";
  if (dockPanel?.kind === "plan") {
    paneTitle = "任务 DAG";
    paneFooter = "只读 · workflow.next 是候选就绪，不是派工";
  } else if (dockPanel?.kind === "leader") {
    paneTitle = dockRoom?.displayName ?? "Leader 房间";
    paneFooter = "Leader 房间只读 · 在左侧主会话与 Manager 沟通";
  } else if (dockPanel?.kind === "issue") {
    paneTitle = "Issue 详情";
    paneFooter = "当前仅查看此 Issue，不改变会话的消息目标";
  }

  return (
    <div className="ws-app">
      <header className="ws-banner">
        <strong>F07–F15 假数据演示</strong>
        <span>请求走 /api · fake-backend 夹具 · 非产品实现</span>
        <nav className="ws-scenes" aria-label="演示场景">
          <button className={scene === "conversation" ? "is-on" : ""} onClick={() => go({ kind: "conversation", conversationId: "conv_1" })}>会话</button>
          <button className={scene === "clarification" ? "is-on" : ""} onClick={() => go({ kind: "conversation", conversationId: "conv_1" })}>澄清</button>
          <button className={scene === "issues" ? "is-on" : ""} onClick={() => go({ kind: "issues" })}>Issue 列表</button>
          <button className={scene === "create" ? "is-on" : ""} onClick={() => void openCreate()}>创建 Issue</button>
          <button className={scene === "overview" && route.kind === "issue" && route.issueId === "iss_1" ? "is-on" : ""} onClick={() => go({ kind: "issue", issueId: "iss_1" })}>可进房间</button>
          <button className={route.kind === "issue" && route.issueId === "iss_3" ? "is-on" : ""} onClick={() => go({ kind: "issue", issueId: "iss_3" })}>最小概览</button>
          <button className={scene === "plan" ? "is-on" : ""} onClick={() => go({ kind: "issue-plan", issueId: "iss_1" })}>DAG</button>
          <button className={scene === "room" ? "is-on" : ""} onClick={() => go({ kind: "issue-room", issueId: "iss_1", roomId: "rm_leader_iss_1_service" })}>Leader</button>
          <button className={scene === "delivery" ? "is-on" : ""} onClick={() => go({ kind: "issue-delivery", issueId: "iss_1" })}>验证与交付</button>
        </nav>
        <span className="ws-spacer" />
        <button onClick={async () => { await resetWorkspaceDemo(); window.location.reload(); }}>重置演示数据</button>
      </header>
      <div className={`ws-shell${showDock ? " ws-dock-workspace" : ""}${paneOpen ? " ws-pane-open" : ""}${dockCompact ? " ws-dock-compact" : ""}${paneExpanded ? " ws-pane-expanded" : ""}`}>
        <aside className="ws-sidebar">
          <div className="ws-brand">RepoMesh</div>
          <nav className="ws-nav" aria-label="主导航">
            <button className={route.kind === "conversation" ? "ws-active" : ""} onClick={() => go({ kind: "conversation", conversationId: conversations[0]?.id ?? "conv_1" })}>新建会话</button>
            <button className={route.kind === "issues" || route.kind === "issue" || route.kind === "issue-plan" || route.kind === "issue-delivery" || route.kind === "issue-room" ? "ws-active" : ""} onClick={() => go({ kind: "issues" })}>Issue</button>
          </nav>
          <div className="ws-label"><span>项目与会话</span><button onClick={() => void openCreate()}>+ 新建</button></div>
          <div>
            <div className="ws-project-head">订单系统</div>
            {conversations.map((item) => (
              <button key={item.id} className={`ws-conversation-link${route.kind === "conversation" && route.conversationId === item.id ? " ws-active" : ""}`} onClick={() => go({ kind: "conversation", conversationId: item.id })}>{item.title}</button>
            ))}
          </div>
          <div className="ws-profile"><span className="ws-avatar">林</span><span>林悦<small className="ws-quiet"> · 演示账号</small></span></div>
        </aside>
        <section className="ws-main">
          {error !== null && <p className="ws-error" role="alert">{error}</p>}
          {waiting && <p className="ws-quiet" style={{ padding: "8px 22px" }}>正在读取 /api …</p>}
          {route.kind === "conversation" && conversation !== null && (
            <ConversationView
              conversation={conversation}
              messages={messages}
              clarification={clarification}
              onSend={send}
              onOpenIssue={(issueId) => go({ kind: "issue", issueId })}
              onCreateIssue={() => void openCreate()}
            />
          )}
          {route.kind === "issues" && <IssueListView issues={issues} onOpen={(issueId) => go({ kind: "issue", issueId })} onCreate={() => void openCreate()} />}
          {route.kind === "issue" && issue !== null && (
            <IssueOverview
              issue={issue}
              rooms={rooms}
              onOpenConversation={(id) => go({ kind: "conversation", conversationId: id })}
              onOpenPlan={() => go({ kind: "issue-plan", issueId: issue.id })}
              onOpenDelivery={() => go({ kind: "issue-delivery", issueId: issue.id })}
              onOpenRoom={(roomId) => go({ kind: "issue-room", issueId: issue.id, roomId })}
              onBack={() => go({ kind: "issues" })}
            />
          )}
          {route.kind === "issue-plan" && issue !== null && graph !== null && <IssuePlanView issue={issue} graph={graph} onBack={() => go({ kind: "issue", issueId: issue.id })} onDelivery={() => go({ kind: "issue-delivery", issueId: issue.id })} />}
          {route.kind === "issue-delivery" && issue !== null && delivery !== null && <IssueDeliveryView issue={issue} delivery={delivery} onBack={() => go({ kind: "issue", issueId: issue.id })} onPlan={() => go({ kind: "issue-plan", issueId: issue.id })} />}
          {route.kind === "issue-room" && room !== null && (
            <RoomView
              room={room}
              onBack={() => go({ kind: "issue", issueId: room.issueId })}
              onOpenIssue={(issueId) => go({ kind: "issue", issueId })}
              onOpenConversation={(conversationId) => go({ kind: "conversation", conversationId })}
            />
          )}
          {route.kind === "not-found" && <div className="ws-details"><h1>没有这个演示页面</h1><button className="ws-primary" onClick={() => go({ kind: "conversation", conversationId: "conv_1" })}>返回会话</button></div>}
        </section>
        {paneOpen && selectedDockIssue !== null && (
          <DockPane
            title={paneTitle}
            subtitle={`#${selectedDockIssue.number} ${selectedDockIssue.title}`}
            footer={paneFooter}
            expanded={paneExpanded}
            onExpand={() => setPaneExpanded((value) => !value)}
            onClose={() => { setDockPanel(null); setPaneExpanded(false); }}
          >
            {dockPanel !== null && dockPanel.kind === "issue" && dockIssue !== null && (
              <div className="ws-details">
                <h2>{dockIssue.title}</h2>
                <p>{dockIssue.description}</p>
                <p className="ws-quiet">主 ChangeSet {dockIssue.mainChangeSetId}</p>
                {dockIssue.repositoryIds.map((id) => <p className="ws-quiet" key={id}>{id}</p>)}
              </div>
            )}
            {dockPanel !== null && dockPanel.kind === "plan" && dockIssue !== null && dockGraph !== null && (
              <IssuePlanView issue={dockIssue} graph={dockGraph} onBack={() => setDockPanel(null)} onDelivery={() => go({ kind: "issue-delivery", issueId: dockIssue.id })} />
            )}
            {dockPanel !== null && dockPanel.kind === "leader" && dockRoom !== null && (
              <RoomView
                room={dockRoom}
                onBack={() => setDockPanel(null)}
                onOpenIssue={(issueId) => go({ kind: "issue", issueId })}
                onOpenConversation={(conversationId) => go({ kind: "conversation", conversationId })}
              />
            )}
          </DockPane>
        )}
        {showDock && (
          <WorkspaceDock
            issues={conversation?.linkedIssues ?? []}
            rooms={dockRooms}
            selectedIssueId={selectedDockIssue?.id ?? null}
            planAvailable={planAvailable}
            panel={dockPanel}
            compact={dockCompact || paneOpen}
            contextOpen={dockContext}
            onSelectIssue={(issueId) => { setDockIssueId(issueId); setDockPanel(null); setDockContext(false); }}
            onToggleContext={() => setDockContext((value) => !value)}
            onToggleCompact={() => setDockCompact((value) => !value)}
            onOpen={openDock}
          />
        )}
      </div>
      {creating && options !== null && creationConversations !== null && (
        <CreateIssueModal
          options={options}
          conversations={creationConversations}
          analysis={analysis}
          onClose={() => setCreating(false)}
          onAnalyze={runAnalysis}
          onSubmit={submitIssue}
        />
      )}
    </div>
  );
}
