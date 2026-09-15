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
  resetWorkspaceDemo,
  sendMessage,
  startRepositoryAnalysis,
} from "./client";
import { ConversationView } from "./ConversationView";
import { CreateIssueModal, IssueDeliveryView, IssueListView, IssueOverview, IssuePlanView } from "./IssueViews";
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
} from "./types";
import "./workspace.css";

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
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [options, setOptions] = useState<IssueCreationOptions | null>(null);
  const [creationConversations, setCreationConversations] = useState<IssueCreationConversations | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisSnapshot | null>(null);
  const [busy, setBusy] = useState(false);

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

  const loadConversation = useCallback(async (conversationId: string) => {
    setBusy(true);
    setError(null);
    const [snapshot, page] = await Promise.all([readConversation(conversationId), readMessages(conversationId)]);
    setBusy(false);
    if (snapshot.kind === "error") return fail(snapshot);
    if (page.kind === "error") return fail(page);
    setConversation(snapshot.value);
    setMessages(page.value.items);
    const question = page.value.items.find((item) => item.clarificationId !== null);
    if (question?.clarificationId !== undefined && question.clarificationId !== null) {
      const current = await readClarification(conversationId, question.clarificationId);
      if (current.kind === "ok") setClarification(current.value);
      else setClarification(null);
    } else setClarification(null);
  }, [fail]);

  const loadIssueBundle = useCallback(async (issueId: string, include: "overview" | "plan" | "delivery") => {
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
    if (current.kind === "conversation") void loadConversation(current.conversationId);
    if (current.kind === "issue") void loadIssueBundle(current.issueId, "overview");
    if (current.kind === "issue-plan") void loadIssueBundle(current.issueId, "plan");
    if (current.kind === "issue-delivery") void loadIssueBundle(current.issueId, "delivery");
    if (current.kind === "issues") setIssue(null);
  }, [path, loadConversation, loadIssueBundle]);

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
    await loadConversation(conversation.id);
  };

  const scene = useMemo(() => {
    if (creating) return "create";
    if (route.kind === "issues") return "issues";
    if (route.kind === "issue") return "overview";
    if (route.kind === "issue-plan") return "plan";
    if (route.kind === "issue-delivery") return "delivery";
    if (clarification?.state === "open") return "clarification";
    return "conversation";
  }, [creating, route, clarification]);

  return (
    <div className="ws-app">
      <header className="ws-banner">
        <strong>F07–F15 假数据演示</strong>
        <span>请求走 /api · 内存模拟 · 非产品实现</span>
        <nav className="ws-scenes" aria-label="演示场景">
          <button className={scene === "conversation" ? "is-on" : ""} onClick={() => go({ kind: "conversation", conversationId: "conv_1" })}>会话</button>
          <button className={scene === "clarification" ? "is-on" : ""} onClick={() => go({ kind: "conversation", conversationId: "conv_1" })}>澄清</button>
          <button className={scene === "issues" ? "is-on" : ""} onClick={() => go({ kind: "issues" })}>Issue 列表</button>
          <button className={scene === "create" ? "is-on" : ""} onClick={() => void openCreate()}>创建 Issue</button>
          <button className={scene === "overview" ? "is-on" : ""} onClick={() => go({ kind: "issue", issueId: "iss_3" })}>最小概览</button>
          <button className={scene === "plan" ? "is-on" : ""} onClick={() => go({ kind: "issue-plan", issueId: "iss_1" })}>DAG</button>
          <button className={scene === "delivery" ? "is-on" : ""} onClick={() => go({ kind: "issue-delivery", issueId: "iss_1" })}>验证与交付</button>
        </nav>
        <span className="ws-spacer" />
        <button onClick={async () => { await resetWorkspaceDemo(); window.location.reload(); }}>重置演示数据</button>
      </header>
      <div className="ws-shell">
        <aside className="ws-sidebar">
          <div className="ws-brand">RepoMesh</div>
          <nav className="ws-nav" aria-label="主导航">
            <button className={route.kind === "conversation" ? "ws-active" : ""} onClick={() => go({ kind: "conversation", conversationId: conversations[0]?.id ?? "conv_1" })}>新建会话</button>
            <button className={route.kind === "issues" || route.kind === "issue" || route.kind === "issue-plan" || route.kind === "issue-delivery" ? "ws-active" : ""} onClick={() => go({ kind: "issues" })}>Issue</button>
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
          {busy && <p className="ws-quiet" style={{ padding: "8px 22px" }}>正在读取 /api …</p>}
          {route.kind === "conversation" && conversation !== null && (
            <ConversationView
              conversation={conversation}
              messages={messages}
              clarification={clarification}
              onSend={send}
              onOpenIssue={(issueId) => go({ kind: "issue", issueId })}
              onOpenPlan={(issueId) => go({ kind: "issue-plan", issueId })}
              onCreateIssue={() => void openCreate()}
            />
          )}
          {route.kind === "issues" && <IssueListView issues={issues} onOpen={(issueId) => go({ kind: "issue", issueId })} onCreate={() => void openCreate()} />}
          {route.kind === "issue" && issue !== null && <IssueOverview issue={issue} rooms={rooms} onOpenConversation={(id) => go({ kind: "conversation", conversationId: id })} onOpenPlan={() => go({ kind: "issue-plan", issueId: issue.id })} onOpenDelivery={() => go({ kind: "issue-delivery", issueId: issue.id })} onBack={() => go({ kind: "issues" })} />}
          {route.kind === "issue-plan" && issue !== null && graph !== null && <IssuePlanView issue={issue} graph={graph} onBack={() => go({ kind: "issue", issueId: issue.id })} onDelivery={() => go({ kind: "issue-delivery", issueId: issue.id })} />}
          {route.kind === "issue-delivery" && issue !== null && delivery !== null && <IssueDeliveryView issue={issue} delivery={delivery} onBack={() => go({ kind: "issue", issueId: issue.id })} onPlan={() => go({ kind: "issue-plan", issueId: issue.id })} />}
          {route.kind === "not-found" && <div className="ws-details"><h1>没有这个演示页面</h1><button className="ws-primary" onClick={() => go({ kind: "conversation", conversationId: "conv_1" })}>返回会话</button></div>}
        </section>
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
