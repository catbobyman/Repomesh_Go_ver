import { isUuid, scalarLength } from "../../values";
import { DEMO_ACTOR, DEMO_CSRF, DEMO_PROJECT_ID } from "../types";
import { CREATION_CONTEXT_REVISION, issueGraph, OBSERVED_AT, projectId, REPOSITORIES, seedStore, mainRoom } from "./store";
import type { StoredAnalysis, StoredClarification, StoredConversation, StoredIssue, StoredMessage, WorkspaceStore } from "./store";

export type MockRequest = {
  method: string;
  path: string;
  headers?: Record<string, string | undefined>;
  body?: unknown;
};

export type MockResponse = {
  status: number;
  body: unknown;
};

type RouteMatch = { pattern: string; params: Record<string, string>; query: URLSearchParams };

function header(request: MockRequest, name: string): string | undefined {
  if (request.headers === undefined) return undefined;
  const target = name.toLowerCase();
  for (const [key, value] of Object.entries(request.headers)) {
    if (key.toLowerCase() === target) return value;
  }
  return undefined;
}

function fail(status: number, code: string, message: string, fieldErrors: Array<{ field: string; code: string }> = []): MockResponse {
  return { status, body: { error: { code, message, fieldErrors, requestId: "req_demo" } } };
}

function parsePath(rawPath: string): { pathname: string; query: URLSearchParams } {
  const url = new URL(rawPath, "http://workspace.invalid");
  return { pathname: url.pathname, query: url.searchParams };
}

function match(pathname: string, method: string): RouteMatch | null {
  const rules: Array<[string, string, string[]]> = [
    ["GET", "/api/projects/:projectId/issue-creation-options", ["projectId"]],
    ["GET", "/api/projects/:projectId/issue-creation-conversations", ["projectId"]],
    ["POST", "/api/projects/:projectId/issues", ["projectId"]],
    ["GET", "/api/projects/:projectId/issues", ["projectId"]],
    ["GET", "/api/projects/:projectId/issue-creations/:creationId", ["projectId", "creationId"]],
    ["GET", "/api/projects/:projectId/conversations/:conversationId/messages/:messageId", ["projectId", "conversationId", "messageId"]],
    ["GET", "/api/projects/:projectId/conversations/:conversationId/messages", ["projectId", "conversationId"]],
    ["POST", "/api/projects/:projectId/conversations/:conversationId/messages", ["projectId", "conversationId"]],
    ["GET", "/api/projects/:projectId/conversations/:conversationId/message-submissions/:submissionId", ["projectId", "conversationId", "submissionId"]],
    ["GET", "/api/projects/:projectId/conversations/:conversationId/clarifications/:clarificationId", ["projectId", "conversationId", "clarificationId"]],
    ["GET", "/api/projects/:projectId/conversations/:conversationId", ["projectId", "conversationId"]],
    ["GET", "/api/projects/:projectId/conversations", ["projectId"]],
    ["POST", "/api/projects/:projectId/repository-analyses", ["projectId"]],
    ["GET", "/api/projects/:projectId/repository-analyses/:analysisId", ["projectId", "analysisId"]],
    ["GET", "/api/issues/:issueId/rooms", ["issueId"]],
    ["GET", "/api/issues/:issueId/plan-graph", ["issueId"]],
    ["GET", "/api/issues/:issueId/delivery", ["issueId"]],
    ["GET", "/api/issues/:issueId", ["issueId"]],
    ["POST", "/api/demo/workspace/reset", []],
  ];
  for (const [expectedMethod, pattern, keys] of rules) {
    if (expectedMethod !== method) continue;
    const parts = pattern.split("/");
    const actual = pathname.split("/");
    if (parts.length !== actual.length) continue;
    const params: Record<string, string> = {};
    let ok = true;
    for (let index = 0; index < parts.length; index += 1) {
      if (parts[index].startsWith(":")) params[parts[index].slice(1)] = decodeURIComponent(actual[index] ?? "");
      else if (parts[index] !== actual[index]) { ok = false; break; }
    }
    if (!ok) continue;
    for (const key of keys) if (!params[key]) return failNotFound();
    return { pattern, params, query: new URLSearchParams() };
  }
  return null;
}

function failNotFound(): never {
  throw new Error("NOT_FOUND_INTERNAL");
}

function requireProject(projectIdValue: string): MockResponse | null {
  if (projectIdValue !== DEMO_PROJECT_ID) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
  return null;
}

function requireUuidHeader(request: MockRequest): string | MockResponse {
  const key = header(request, "Idempotency-Key");
  if (key === undefined || !isUuid(key)) return fail(400, "INVALID_IDEMPOTENCY_KEY", "需要恰好一个 UUID 幂等键。");
  return key.toLowerCase();
}

function requireCsrf(request: MockRequest): MockResponse | null {
  if (header(request, "X-CSRF-Token") !== DEMO_CSRF) return fail(401, "AUTHENTICATION_REQUIRED", "当前演示会话无效。");
  return null;
}

function limitOf(query: URLSearchParams): number | MockResponse {
  const raw = query.get("limit");
  if (raw === null || raw === "") return 50;
  if (!/^[0-9]+$/.test(raw)) return fail(422, "VALIDATION_FAILED", "limit 非法。", [{ field: "limit", code: "INVALID" }]);
  const value = Number(raw);
  if (value < 1 || value > 100) return fail(422, "VALIDATION_FAILED", "limit 非法。", [{ field: "limit", code: "INVALID" }]);
  return value;
}

function search(query: URLSearchParams): string {
  return (query.get("q") ?? "").trim().toLowerCase();
}

function paginate<T extends { id: string }>(items: T[], query: URLSearchParams): { items: T[]; nextCursor: string | null } | MockResponse {
  const limit = limitOf(query);
  if (typeof limit !== "number") return limit;
  const cursorValue = query.get("cursor");
  let start = 0;
  if (cursorValue !== null && cursorValue !== "") {
    const index = items.findIndex((item) => item.id === cursorValue);
    if (index < 0) return fail(400, "INVALID_CURSOR", "游标无效。");
    start = index + 1;
  }
  const slice = items.slice(start, start + limit);
  const last = slice[slice.length - 1];
  const more = start + slice.length < items.length;
  return { items: slice, nextCursor: more && last !== undefined ? last.id : null };
}

function now(): string {
  return "2026-09-15T12:30:00Z";
}

function issueItem(issue: StoredIssue) {
  return {
    id: issue.id,
    number: issue.number,
    title: issue.title,
    repositoryIds: issue.repositoryIds,
    mainChangeSetId: issue.mainChangeSetId,
    source: { kind: issue.sourceKind, conversationId: issue.conversationId },
    createdAt: issue.createdAt,
    revision: issue.revision,
  };
}

function issueSnapshot(issue: StoredIssue) {
  return { ...issueItem(issue), projectId: DEMO_PROJECT_ID, description: issue.description, acceptanceCriteria: issue.acceptanceCriteria };
}

function linkedIssues(store: WorkspaceStore, conversationId: string) {
  return store.issues.filter((issue) => issue.conversationId === conversationId).map((issue) => ({ id: issue.id, number: issue.number, title: issue.title }));
}

function messageJson(store: WorkspaceStore, message: StoredMessage) {
  const issue = message.issueId === null ? null : store.issues.find((item) => item.id === message.issueId) ?? null;
  return {
    id: message.id,
    sequence: String(message.sequence),
    author: { kind: message.authorKind, displayName: message.displayName },
    content: message.content,
    createdAt: message.createdAt,
    replyTo: message.replyToClarificationId === null ? null : { clarificationId: message.replyToClarificationId },
    clarificationId: message.clarificationId,
    issueCard: issue === null ? null : { id: issue.id, number: issue.number, title: issue.title },
  };
}

function clarificationJson(store: WorkspaceStore, clarification: StoredClarification) {
  const open = clarification.state === "open";
  return {
    id: clarification.id,
    revision: clarification.revision,
    state: clarification.state,
    sourceMessageId: clarification.sourceMessageId,
    questionMessageId: clarification.questionMessageId,
    answerMessageId: clarification.answerMessageId,
    candidates: clarification.candidateIssueIds.map((id) => {
      const issue = store.issues.find((item) => item.id === id);
      if (issue === undefined) throw new Error("missing candidate");
      return { issueId: issue.id, number: issue.number, title: issue.title };
    }),
    resolution: null,
    supersededBy: null,
    actions: { canReply: open },
    reasonCodes: open ? [] : ["ANSWER_SAVED"],
  };
}

function analysisBody(analysis: StoredAnalysis) {
  const succeeded = analysis.status === "succeeded";
  return {
    analysisId: analysis.analysisId,
    status: analysis.status,
    quality: succeeded ? "partial" : null,
    title: analysis.title,
    description: analysis.description,
    coverageNote: succeeded ? "演示数据：未扫描真实仓库。分析失败不能阻止手动建项。" : null,
    recommendations: succeeded
      ? [
          { repositoryId: "repo_service", displayName: "repomesh/order-service", reason: "标题与归档/筛选目标匹配订单服务。", relation: "likely_involved", selectable: true },
          { repositoryId: "repo_admin", displayName: "repomesh/admin-console", reason: "查询体验涉及运营后台界面。", relation: "likely_involved", selectable: true },
        ]
      : [],
    links: { analysis: `/api/projects/${DEMO_PROJECT_ID}/repository-analyses/${analysis.analysisId}` },
  };
}

function graphStatusLabel(status: StoredIssue["id"]): ReturnType<typeof issueGraph> {
  return issueGraph(status);
}

export function createWorkspaceMock() {
  let store: WorkspaceStore = seedStore();
  const handle = (request: MockRequest): MockResponse => {
    const method = request.method.toUpperCase();
    const { pathname, query } = parsePath(request.path);
    if (method === "POST" && pathname === "/api/demo/workspace/reset") {
      store = seedStore();
      return { status: 200, body: { status: "reset", projectId: DEMO_PROJECT_ID } };
    }
    let matched: RouteMatch | null;
    try {
      matched = match(pathname, method);
    } catch {
      return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
    }
    if (matched === null) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
    matched.query = query;
    const params = matched.params;
    if (params.projectId !== undefined) {
      const denied = requireProject(params.projectId);
      if (denied !== null) return denied;
    }

    if (matched.pattern === "/api/projects/:projectId/issue-creation-options") {
      return {
        status: 200,
        body: {
          projectId: DEMO_PROJECT_ID,
          creationContextRevision: CREATION_CONTEXT_REVISION,
          defaultConversationMode: "new",
          allowedConversationModes: ["new", "existing"],
          canSubmit: true,
          blockingReasons: [],
          repositories: REPOSITORIES,
          nextCursor: null,
          repositoryAnalysis: { availability: "available", reasonCodes: [] },
        },
      };
    }

    if (matched.pattern === "/api/projects/:projectId/issue-creation-conversations") {
      const page = paginate(store.conversations.map((item) => ({ id: item.id, title: item.title })), query);
      if ("status" in page) return page;
      return { status: 200, body: page };
    }

    if (matched.pattern === "/api/projects/:projectId/issues" && method === "GET") {
      const filtered = store.issues
        .filter((issue) => search(query) === "" || issue.title.toLowerCase().includes(search(query)))
        .filter((issue) => {
          const repositoryId = query.get("repositoryId");
          return repositoryId === null || repositoryId === "" || issue.repositoryIds.includes(repositoryId);
        })
        .sort((left, right) => left.id.localeCompare(right.id))
        .map(issueItem);
      const page = paginate(filtered, query);
      if ("status" in page) return page;
      return { status: 200, body: page };
    }

    if (matched.pattern === "/api/projects/:projectId/issues" && method === "POST") {
      const csrf = requireCsrf(request);
      if (csrf !== null) return csrf;
      const key = requireUuidHeader(request);
      if (typeof key !== "string") return key;
      const body = request.body;
      if (typeof body !== "object" || body === null || Array.isArray(body)) return fail(400, "INVALID_JSON", "请求体必须是 JSON 对象。");
      const payload = body as Record<string, unknown>;
      const extra = Object.keys(payload).filter((field) => !["expectedCreationContextRevision", "conversation", "title", "description", "repositoryIds", "acceptanceCriteria", "repositoryAnalysisId"].includes(field));
      if (extra.length > 0) return fail(422, "VALIDATION_FAILED", "存在未知字段。", extra.map((field) => ({ field, code: "UNKNOWN" })));
      if (payload.expectedCreationContextRevision !== CREATION_CONTEXT_REVISION) return fail(409, "CREATION_CONTEXT_CHANGED", "创建条件已变化，请刷新后核对。");
      if (typeof payload.title !== "string" || scalarLength(payload.title) === null || scalarLength(payload.title) === 0) return fail(422, "VALIDATION_FAILED", "标题无效。", [{ field: "title", code: "REQUIRED" }]);
      if (typeof payload.description !== "string" || scalarLength(payload.description) === null || scalarLength(payload.description) === 0) return fail(422, "VALIDATION_FAILED", "目标无效。", [{ field: "description", code: "REQUIRED" }]);
      if (!Array.isArray(payload.repositoryIds) || payload.repositoryIds.length === 0) return fail(422, "VALIDATION_FAILED", "需要明确仓库。", [{ field: "repositoryIds", code: "REQUIRED" }]);
      const repositoryIds = payload.repositoryIds.map((item) => String(item));
      if (new Set(repositoryIds).size !== repositoryIds.length) return fail(422, "VALIDATION_FAILED", "仓库重复。", [{ field: "repositoryIds", code: "DUPLICATE" }]);
      for (const repositoryId of repositoryIds) {
        const repo = REPOSITORIES.find((item) => item.repositoryId === repositoryId);
        if (repo === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
        if (!repo.selectable) return fail(409, "CREATION_REQUIREMENTS_UNMET", "本次范围不满足创建条件。", [{ field: "repositoryIds", code: "APP_PERMISSION_MISSING" }]);
      }
      let conversationMode = "new";
      let existingId: string | null = null;
      if (payload.conversation !== undefined) {
        if (typeof payload.conversation !== "object" || payload.conversation === null) return fail(422, "VALIDATION_FAILED", "会话关联无效。", [{ field: "conversation", code: "INVALID" }]);
        const conversation = payload.conversation as Record<string, unknown>;
        if (conversation.mode === "existing") {
          conversationMode = "existing";
          if (typeof conversation.id !== "string") return fail(422, "VALIDATION_FAILED", "已有会话需要 id。", [{ field: "conversation.id", code: "REQUIRED" }]);
          existingId = conversation.id;
        } else if (conversation.mode !== "new") return fail(422, "VALIDATION_FAILED", "会话关联无效。", [{ field: "conversation.mode", code: "INVALID" }]);
        else if (conversation.id !== undefined) return fail(422, "VALIDATION_FAILED", "新建会话不能带 id。", [{ field: "conversation.id", code: "UNKNOWN" }]);
      }
      const analysisId = payload.repositoryAnalysisId === undefined ? null : String(payload.repositoryAnalysisId);
      if (analysisId !== null) {
        const analysis = store.analyses.find((item) => item.analysisId === analysisId && item.actor === DEMO_ACTOR);
        if (analysis === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
        if (analysis.status !== "succeeded") return fail(409, "ANALYSIS_NOT_APPLICABLE", "所附分析未完成或不适用于当前输入。");
      }
      const acceptanceCriteria = Array.isArray(payload.acceptanceCriteria) ? payload.acceptanceCriteria.map((item) => String(item)) : [];
      const input = JSON.stringify({
        expectedCreationContextRevision: payload.expectedCreationContextRevision,
        conversation: conversationMode === "new" ? { mode: "new" } : { mode: "existing", id: existingId },
        title: payload.title,
        description: payload.description,
        repositoryIds: [...repositoryIds].sort(),
        acceptanceCriteria,
        repositoryAnalysisId: analysisId,
      });
      const existing = store.creations.find((item) => item.creationId === key && item.actor === DEMO_ACTOR);
      if (existing !== undefined) {
        if (existing.input !== input) return fail(409, "IDEMPOTENCY_CONFLICT", "同一操作键不能绑定不同输入。");
        const issue = store.issues.find((item) => item.id === existing.issueId);
        if (issue === undefined) return fail(410, "CREATION_RESULT_REMOVED", "原创建结果已清理。");
        return receipt(existing.creationId, issue, existing.createdAt);
      }
      if (conversationMode === "existing") {
        const conversation = store.conversations.find((item) => item.id === existingId);
        if (conversation === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
      }
      const createdAt = now();
      const number = store.nextIssueNumber;
      store.nextIssueNumber += 1;
      const issueId = `iss_${number}`;
      let conversationId = existingId ?? `conv_${number}`;
      if (conversationMode === "new") {
        const conversation: StoredConversation = { id: conversationId, title: String(payload.title), createdAt, revision: "convrev_1" };
        store.conversations.push(conversation);
        store.nextSequence[conversationId] = 1;
      }
      const issue: StoredIssue = {
        id: issueId,
        number,
        title: String(payload.title),
        description: String(payload.description),
        acceptanceCriteria,
        repositoryIds,
        mainChangeSetId: `cs_${number}`,
        conversationId,
        createdAt,
        revision: "issrev_1",
        sourceKind: "issue_page",
      };
      store.issues.push(issue);
      store.creations.push({ creationId: key, actor: DEMO_ACTOR, input, issueId, conversationId, createdAt });
      const sequence = store.nextSequence[conversationId] ?? 1;
      store.messages.push({
        id: `msg_${conversationId}_${sequence}`,
        conversationId,
        sequence,
        authorKind: "system",
        displayName: "系统",
        content: `页面创建了 Issue #${number} ${issue.title}，并关联本会话。`,
        createdAt,
        replyToClarificationId: null,
        clarificationId: null,
        issueId,
      });
      store.nextSequence[conversationId] = sequence + 1;
      return receipt(key, issue, createdAt, 201);
    }

    if (matched.pattern === "/api/projects/:projectId/issue-creations/:creationId") {
      const creation = store.creations.find((item) => item.creationId === params.creationId && item.actor === DEMO_ACTOR);
      if (creation === undefined) return fail(404, "CREATION_NOT_FOUND", "暂未查到原保存结果。");
      const issue = store.issues.find((item) => item.id === creation.issueId);
      if (issue === undefined) return fail(410, "CREATION_RESULT_REMOVED", "原创建结果已清理。");
      return receipt(creation.creationId, issue, creation.createdAt);
    }

    if (matched.pattern === "/api/projects/:projectId/conversations" && method === "GET") {
      const filtered = store.conversations
        .filter((item) => search(query) === "" || item.title.toLowerCase().includes(search(query)))
        .sort((left, right) => left.id.localeCompare(right.id));
      const page = paginate(filtered, query);
      if ("status" in page) return page;
      return { status: 200, body: { items: page.items.map((item) => ({ id: item.id, title: item.title, createdAt: item.createdAt, revision: item.revision })), nextCursor: page.nextCursor } };
    }

    if (matched.pattern === "/api/projects/:projectId/conversations/:conversationId") {
      const conversation = store.conversations.find((item) => item.id === params.conversationId);
      if (conversation === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
      return {
        status: 200,
        body: {
          ...conversation,
          projectId: DEMO_PROJECT_ID,
          linkedIssues: linkedIssues(store, conversation.id),
          actions: { canSend: true },
        },
      };
    }

    if (matched.pattern === "/api/projects/:projectId/conversations/:conversationId/messages" && method === "GET") {
      const conversation = store.conversations.find((item) => item.id === params.conversationId);
      if (conversation === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
      const items = store.messages.filter((item) => item.conversationId === conversation.id).sort((left, right) => left.sequence - right.sequence);
      const page = paginate(items, query);
      if ("status" in page) return page;
      return { status: 200, body: { items: page.items.map((item) => messageJson(store, item)), nextCursor: page.nextCursor } };
    }

    if (matched.pattern === "/api/projects/:projectId/conversations/:conversationId/messages/:messageId") {
      const message = store.messages.find((item) => item.conversationId === params.conversationId && item.id === params.messageId);
      if (message === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
      return { status: 200, body: messageJson(store, message) };
    }

    if (matched.pattern === "/api/projects/:projectId/conversations/:conversationId/messages" && method === "POST") {
      const csrf = requireCsrf(request);
      if (csrf !== null) return csrf;
      const key = requireUuidHeader(request);
      if (typeof key !== "string") return key;
      const conversation = store.conversations.find((item) => item.id === params.conversationId);
      if (conversation === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
      const body = request.body;
      if (typeof body !== "object" || body === null || Array.isArray(body)) return fail(400, "INVALID_JSON", "请求体必须是 JSON 对象。");
      const payload = body as Record<string, unknown>;
      if (typeof payload.content !== "string" || payload.content.trim().length === 0) return fail(422, "VALIDATION_FAILED", "消息不能为空。", [{ field: "content", code: "REQUIRED" }]);
      let reply: { clarificationId: string; expectedRevision: string } | null = null;
      if (payload.replyTo !== undefined) {
        if (typeof payload.replyTo !== "object" || payload.replyTo === null) return fail(422, "VALIDATION_FAILED", "引用无效。", [{ field: "replyTo", code: "INVALID" }]);
        const row = payload.replyTo as Record<string, unknown>;
        if (typeof row.clarificationId !== "string" || typeof row.expectedRevision !== "string") return fail(422, "VALIDATION_FAILED", "引用无效。", [{ field: "replyTo", code: "INVALID" }]);
        reply = { clarificationId: row.clarificationId, expectedRevision: row.expectedRevision };
      }
      const input = JSON.stringify({ content: payload.content, replyTo: reply });
      const existing = store.submissions.find((item) => item.submissionId === key && item.actor === DEMO_ACTOR && item.conversationId === conversation.id);
      if (existing !== undefined) {
        if (existing.input !== input) return fail(409, "IDEMPOTENCY_CONFLICT", "同一操作键不能绑定不同输入。");
        return submissionReceipt(existing);
      }
      if (reply !== null) {
        const clarification = store.clarifications.find((item) => item.id === reply.clarificationId && item.conversationId === conversation.id);
        if (clarification === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
        if (clarification.state !== "open" || clarification.revision !== reply.expectedRevision) return fail(409, "CLARIFICATION_REVISION_CONFLICT", "当前问题已变化，本次答复未保存。");
      }
      const sequence = store.nextSequence[conversation.id] ?? 1;
      const messageId = `msg_${conversation.id}_${sequence}`;
      const committedAt = now();
      const message: StoredMessage = {
        id: messageId,
        conversationId: conversation.id,
        sequence,
        authorKind: "user",
        displayName: "林悦",
        content: String(payload.content),
        createdAt: committedAt,
        replyToClarificationId: reply?.clarificationId ?? null,
        clarificationId: null,
        issueId: null,
      };
      store.messages.push(message);
      store.nextSequence[conversation.id] = sequence + 1;
      if (reply !== null) {
        const clarification = store.clarifications.find((item) => item.id === reply.clarificationId);
        if (clarification !== undefined) {
          clarification.state = "answer_saved";
          clarification.answerMessageId = messageId;
        }
      }
      const saved = { submissionId: key, actor: DEMO_ACTOR, conversationId: conversation.id, input, messageId, sequence, committedAt, replyTo: reply === null ? null : { clarificationId: reply.clarificationId, answeredRevision: reply.expectedRevision } };
      store.submissions.push(saved);
      return submissionReceipt(saved, 201);
    }

    if (matched.pattern === "/api/projects/:projectId/conversations/:conversationId/message-submissions/:submissionId") {
      const saved = store.submissions.find((item) => item.submissionId === params.submissionId && item.conversationId === params.conversationId && item.actor === DEMO_ACTOR);
      if (saved === undefined) return fail(404, "MESSAGE_SUBMISSION_NOT_FOUND", "暂未查到原提交结果。");
      return submissionReceipt(saved);
    }

    if (matched.pattern === "/api/projects/:projectId/conversations/:conversationId/clarifications/:clarificationId") {
      const clarification = store.clarifications.find((item) => item.id === params.clarificationId && item.conversationId === params.conversationId);
      if (clarification === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
      return { status: 200, body: clarificationJson(store, clarification) };
    }

    if (matched.pattern === "/api/projects/:projectId/repository-analyses" && method === "POST") {
      const csrf = requireCsrf(request);
      if (csrf !== null) return csrf;
      const key = requireUuidHeader(request);
      if (typeof key !== "string") return key;
      const body = request.body;
      if (typeof body !== "object" || body === null || Array.isArray(body)) return fail(400, "INVALID_JSON", "请求体必须是 JSON 对象。");
      const payload = body as Record<string, unknown>;
      if (payload.expectedCreationContextRevision !== CREATION_CONTEXT_REVISION) return fail(409, "CREATION_CONTEXT_CHANGED", "创建条件已变化，请刷新后核对。");
      if (typeof payload.title !== "string" || typeof payload.description !== "string") return fail(422, "VALIDATION_FAILED", "分析输入无效。");
      const input = JSON.stringify({ expectedCreationContextRevision: payload.expectedCreationContextRevision, title: payload.title, description: payload.description, acceptanceCriteria: payload.acceptanceCriteria ?? [] });
      const existing = store.analyses.find((item) => item.analysisId === key && item.actor === DEMO_ACTOR);
      if (existing !== undefined) {
        if (existing.input !== input) return fail(409, "IDEMPOTENCY_CONFLICT", "同一操作键不能绑定不同输入。");
        return { status: existing.status === "succeeded" || existing.status === "failed" ? 200 : 202, body: analysisBody(existing) };
      }
      const analysis: StoredAnalysis = { analysisId: key, actor: DEMO_ACTOR, input, status: "running", title: String(payload.title), description: String(payload.description) };
      store.analyses.push(analysis);
      return { status: 202, body: analysisBody(analysis) };
    }

    if (matched.pattern === "/api/projects/:projectId/repository-analyses/:analysisId") {
      const analysis = store.analyses.find((item) => item.analysisId === params.analysisId && item.actor === DEMO_ACTOR);
      if (analysis === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
      if (analysis.status === "running" || analysis.status === "queued" || analysis.status === "recovering") analysis.status = "succeeded";
      return { status: 200, body: analysisBody(analysis) };
    }

    if (matched.pattern === "/api/issues/:issueId") {
      const issue = store.issues.find((item) => item.id === params.issueId);
      if (issue === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
      return { status: 200, body: issueSnapshot(issue) };
    }

    if (matched.pattern === "/api/issues/:issueId/rooms") {
      const issue = store.issues.find((item) => item.id === params.issueId);
      if (issue === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
      const main = mainRoom(issue);
      return {
        status: 200,
        body: {
          issueId: issue.id,
          main: { conversationId: issue.conversationId, ...main, observedAt: OBSERVED_AT },
          leaders: issue.repositoryIds.filter((id) => id !== "repo_billing").map((repositoryId, index) => {
            const repo = REPOSITORIES.find((item) => item.repositoryId === repositoryId);
            return {
              repositoryIssueId: `ri_${issue.id}_${index + 1}`,
              repositoryId,
              displayName: repo?.displayName ?? repositoryId,
              conversationId: null,
              availability: "unavailable" as const,
              reason: "NOT_ASSOCIATED",
              roomId: null,
              canEnter: false,
              observedAt: OBSERVED_AT,
              readOnly: true,
            };
          }),
        },
      };
    }

    if (matched.pattern === "/api/issues/:issueId/plan-graph") {
      const issue = store.issues.find((item) => item.id === params.issueId);
      if (issue === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
      const graph = graphStatusLabel(issue.id);
      if (graph === null) {
        return {
          status: 200,
          body: { issueId: issue.id, planVersion: "none", round: 1, readOnly: true, observedAt: OBSERVED_AT, nodes: [], edges: [] },
        };
      }
      return { status: 200, body: { issueId: issue.id, planVersion: "v1", round: 1, readOnly: true, observedAt: OBSERVED_AT, nodes: graph.nodes, edges: graph.edges } };
    }

    if (matched.pattern === "/api/issues/:issueId/delivery") {
      const issue = store.issues.find((item) => item.id === params.issueId);
      if (issue === undefined) return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
      return {
        status: 200,
        body: {
          issueId: issue.id,
          mainChangeSetId: issue.mainChangeSetId,
          combination: { status: "not_formed", label: "尚未形成可验证的固定组合" },
          verification: { status: "pending", label: "待验证" },
          delivery: { status: "not_delivered", label: "未交付" },
          repositories: issue.repositoryIds.map((repositoryId) => {
            const repo = REPOSITORIES.find((item) => item.repositoryId === repositoryId);
            return { repositoryId, displayName: repo?.displayName ?? repositoryId, evidenceStatus: "candidate" };
          }),
          observedAt: OBSERVED_AT,
        },
      };
    }

    return fail(404, "RESOURCE_NOT_FOUND", "资源不存在或当前不可见。");
  };

  function receipt(creationId: string, issue: StoredIssue, createdAt: string, status = 200): MockResponse {
    return {
      status,
      body: {
        creationId,
        status: "committed",
        projectId: DEMO_PROJECT_ID,
        createdAt,
        source: { kind: "issue_page" },
        issue: { id: issue.id, number: issue.number },
        mainChangeSet: { id: issue.mainChangeSetId },
        conversation: { id: issue.conversationId },
        links: {
          issue: `/api/issues/${issue.id}`,
          rooms: `/api/issues/${issue.id}/rooms`,
          operation: `/api/projects/${DEMO_PROJECT_ID}/issue-creations/${creationId}`,
        },
      },
    };
  }

  function submissionReceipt(saved: WorkspaceStore["submissions"][number], status = 200): MockResponse {
    return {
      status,
      body: {
        submissionId: saved.submissionId,
        status: "committed",
        conversationId: saved.conversationId,
        messageId: saved.messageId,
        sequence: String(saved.sequence),
        committedAt: saved.committedAt,
        replyTo: saved.replyTo,
        links: {
          message: `/api/projects/${DEMO_PROJECT_ID}/conversations/${saved.conversationId}/messages/${saved.messageId}`,
          operation: `/api/projects/${DEMO_PROJECT_ID}/conversations/${saved.conversationId}/message-submissions/${saved.submissionId}`,
        },
      },
    };
  }

  return {
    handle,
    reset() {
      store = seedStore();
    },
    projectId: projectId(),
  };
}

export const demoWorkspaceMock = createWorkspaceMock();
