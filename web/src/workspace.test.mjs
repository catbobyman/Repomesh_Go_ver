import assert from "node:assert/strict";
import test from "node:test";
import { createIssue, readClarification, readConversation, readCreationOptions, readDelivery, readIssue, readIssueList, readIssueRooms, readMessages, readPlanGraph, readRepositoryAnalysis, readRoom, sendMessage, startRepositoryAnalysis } from "./workspace/client.ts";
import { createWorkspaceMock } from "./workspace/mock/server.ts";
import { parseIssueList, parseIssueSnapshot, parseMessagePage, parsePlanGraph, parseRoomSnapshot } from "./workspace/parse.ts";
import { parseWorkspaceRoute, workspacePath } from "./workspace/routes.ts";
import { DEMO_CSRF } from "./workspace/types.ts";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

function installMock(t, mock = createWorkspaceMock()) {
  t.mock.method(globalThis, "fetch", async (path, options = {}) => {
    const headers = {};
    const incoming = options.headers;
    if (incoming !== undefined && typeof incoming.forEach === "function") incoming.forEach((value, key) => { headers[key] = value; });
    const body = typeof options.body === "string" ? JSON.parse(options.body) : undefined;
    const result = mock.handle({ method: options.method ?? "GET", path, headers, body });
    return new Response(JSON.stringify(result.body), { status: result.status, headers: { "Content-Type": "application/json" } });
  });
  return mock;
}

test("workspace demo routes map F07-F15 surfaces", () => {
  assert.deepEqual(parseWorkspaceRoute("/demo/workspace"), { kind: "conversation", conversationId: "conv_1" });
  assert.deepEqual(parseWorkspaceRoute("/demo/workspace/issues"), { kind: "issues" });
  assert.deepEqual(parseWorkspaceRoute("/demo/workspace/issues/iss_1/plan"), { kind: "issue-plan", issueId: "iss_1" });
  assert.deepEqual(parseWorkspaceRoute("/demo/workspace/issues/iss_1/rooms/rm_leader_iss_1_service"), { kind: "issue-room", issueId: "iss_1", roomId: "rm_leader_iss_1_service" });
  assert.equal(workspacePath({ kind: "issue-delivery", issueId: "iss_1" }), "/demo/workspace/issues/iss_1/delivery");
});

test("the same demo path always parses to the same route shape", () => {
  const first = parseWorkspaceRoute("/demo/workspace/conversations/conv_1");
  const second = parseWorkspaceRoute("/demo/workspace/conversations/conv_1");
  assert.deepEqual(first, second);
  assert.equal(JSON.stringify(first), JSON.stringify(second));
});

test("mock API lists issues and conversations then returns adopted snapshots", async (t) => {
  installMock(t);
  const list = await readIssueList();
  assert.equal(list.kind, "ok");
  if (list.kind !== "ok") return;
  assert.equal(list.value.items.length, 3);
  parseIssueList(list.value);
  const issue = await readIssue("iss_3");
  assert.equal(issue.kind, "ok");
  if (issue.kind !== "ok") return;
  parseIssueSnapshot(issue.value);
  assert.equal(issue.value.title, "订单归档");
  assert.equal(issue.value.source.conversationId, "conv_2");
  const rooms = await readIssueRooms("iss_1");
  assert.equal(rooms.kind, "ok");
  if (rooms.kind !== "ok") return;
  assert.equal(rooms.value.main.availability, "ready");
  assert.equal(rooms.value.main.canEnter, true);
  assert.equal(rooms.value.main.roomId, "rm_main_iss_1");
  assert.equal(rooms.value.leaders.filter((item) => item.canEnter).length, 2);
  const graph = await readPlanGraph("iss_1");
  assert.equal(graph.kind, "ok");
  if (graph.kind !== "ok") return;
  parsePlanGraph(graph.value);
  assert.equal(graph.value.readOnly, true);
  assert.equal(graph.value.upstreamProjects.length, 2);
  assert.deepEqual(graph.value.upstreamProjects[1].workflow.next, ["ui-01"]);
  assert.equal(graph.value.businessOverlay.readyIsNotDispatch, true);
  assert.equal(graph.value.businessOverlay.dispatchState["ui-01"], "not_dispatched");
  const ui = graph.value.nodes.find((item) => item.id === "ui-01");
  assert.ok(ui);
  assert.equal(ui.nativeStatus, "assigned");
  assert.equal(ui.inNext, true);
  assert.equal(ui.dispatchState, "not_dispatched");
  const delivery = await readDelivery("iss_1");
  assert.equal(delivery.kind, "ok");
  if (delivery.kind !== "ok") return;
  assert.equal(delivery.value.combination.status, "not_formed");
});

test("creating an issue goes through options, POST with idempotency, and receipt query", async (t) => {
  installMock(t);
  const options = await readCreationOptions();
  assert.equal(options.kind, "ok");
  if (options.kind !== "ok") return;
  assert.equal(options.value.canSubmit, true);
  assert.equal(options.value.repositoryAnalysis.availability, "available");
  const key = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  const body = {
    expectedCreationContextRevision: options.value.creationContextRevision,
    title: "增加订单归档",
    description: "归档历史订单，保持原有读取权限。",
    repositoryIds: ["repo_service"],
    conversation: { mode: "new" },
  };
  const created = await createIssue(key, body);
  assert.equal(created.kind, "ok");
  if (created.kind !== "ok") return;
  assert.equal(created.value.status, "committed");
  const replay = await createIssue(key, body);
  assert.equal(replay.kind, "ok");
  if (replay.kind !== "ok") return;
  assert.equal(replay.value.issue.id, created.value.issue.id);
  const conflict = await createIssue(key, { ...body, title: "另一项工作" });
  assert.equal(conflict.kind, "error");
  if (conflict.kind !== "error") return;
  assert.equal(conflict.code, "IDEMPOTENCY_CONFLICT");
});

test("messages and clarification replies use the adopted five endpoints", async (t) => {
  installMock(t);
  const page = await readMessages("conv_1");
  assert.equal(page.kind, "ok");
  if (page.kind !== "ok") return;
  parseMessagePage(page.value);
  const question = page.value.items.find((item) => item.clarificationId === "cl_1");
  assert.ok(question);
  const snapshot = await readClarification("conv_1", "cl_1");
  assert.equal(snapshot.kind, "ok");
  if (snapshot.kind !== "ok") return;
  assert.equal(snapshot.value.state, "open");
  assert.equal(snapshot.value.actions.canReply, true);
  const sent = await sendMessage("conv_1", "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", {
    content: "指的是 #2 订单导出。",
    replyTo: { clarificationId: "cl_1", expectedRevision: snapshot.value.revision },
  });
  assert.equal(sent.kind, "ok");
  if (sent.kind !== "ok") return;
  assert.equal(sent.value.status, "committed");
  const after = await readClarification("conv_1", "cl_1");
  assert.equal(after.kind, "ok");
  if (after.kind !== "ok") return;
  assert.equal(after.value.state, "answer_saved");
  assert.equal(after.value.actions.canReply, false);
});

test("repository analysis is optional and does not block manual create", async (t) => {
  installMock(t);
  const options = await readCreationOptions();
  assert.equal(options.kind, "ok");
  if (options.kind !== "ok") return;
  const key = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
  const accepted = await startRepositoryAnalysis(key, {
    expectedCreationContextRevision: options.value.creationContextRevision,
    title: "支付筛选",
    description: "在订单列表增加支付状态筛选",
  });
  assert.equal(accepted.kind, "ok");
  if (accepted.kind !== "ok") return;
  const report = await readRepositoryAnalysis(accepted.value.analysisId);
  assert.equal(report.kind, "ok");
  if (report.kind !== "ok") return;
  assert.equal(report.value.status, "succeeded");
  assert.ok(report.value.recommendations.length >= 1);
  const conversation = await readConversation("conv_1");
  assert.equal(conversation.kind, "ok");
  if (conversation.kind !== "ok") return;
  assert.equal(conversation.value.linkedIssues.length, 2);
});

test("workspace mock requires CSRF and UUID keys on writes", () => {
  const mock = createWorkspaceMock();
  const denied = mock.handle({
    method: "POST",
    path: "/api/projects/prj_orders/issues",
    headers: { "Idempotency-Key": "dddddddd-dddd-4ddd-8ddd-dddddddddddd" },
    body: { expectedCreationContextRevision: "ctx_17", title: "x", description: "yyyy", repositoryIds: ["repo_service"] },
  });
  assert.equal(denied.status, 401);
  const missingKey = mock.handle({
    method: "POST",
    path: "/api/projects/prj_orders/issues",
    headers: { "X-CSRF-Token": DEMO_CSRF },
    body: { expectedCreationContextRevision: "ctx_17", title: "x", description: "yyyy", repositoryIds: ["repo_service"] },
  });
  assert.equal(missingKey.status, 400);
});

test("room snapshots re-check canEnter and map AgentTeams roomKind without Matrix ids", async (t) => {
  installMock(t);
  const entered = await readRoom("iss_1", "rm_leader_iss_1_service");
  assert.equal(entered.kind, "ok");
  if (entered.kind !== "ok") return;
  parseRoomSnapshot(entered.value);
  assert.equal(entered.value.roomRole, "leader");
  assert.equal(entered.value.readOnly, true);
  assert.equal(entered.value.composer.enabled, false);
  assert.equal(entered.value.upstream.roomKind, "team_room");
  assert.equal(entered.value.roomId.startsWith("!"), false);
  const main = await readRoom("iss_1", "rm_main_iss_1");
  assert.equal(main.kind, "ok");
  if (main.kind !== "ok") return;
  assert.equal(main.value.upstream.roomKind, "task_room");
  assert.equal(main.value.readOnly, false);
  const denied = await readRoom("iss_2", "rm_leader_iss_2_service");
  assert.equal(denied.kind, "error");
  if (denied.kind !== "error") return;
  assert.equal(denied.code, "ROOM_NOT_ENTERABLE");
});

test("fake-backend fixtures never expose Matrix room addresses as browser ids", () => {
  const root = join(dirname(fileURLToPath(import.meta.url)), "../fake-backend/fixtures");
  const files = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const next = join(dir, entry.name);
      if (entry.isDirectory()) walk(next);
      else if (entry.name.endsWith(".json")) files.push(next);
    }
  };
  walk(root);
  assert.ok(files.length > 0);
  for (const file of files) {
    const text = readFileSync(file, "utf8");
    assert.equal(text.includes("matrix:!"), false, file);
    assert.equal(/"[!][A-Za-z0-9]+:/u.test(text), false, file);
  }
});

