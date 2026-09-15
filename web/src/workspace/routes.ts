import { isSafeSegment } from "../values";

export type WorkspaceRoute =
  | { kind: "conversation"; conversationId: string }
  | { kind: "issues" }
  | { kind: "issue"; issueId: string }
  | { kind: "issue-plan"; issueId: string }
  | { kind: "issue-delivery"; issueId: string }
  | { kind: "not-found" };

export const WORKSPACE_DEMO_PREFIX = "/demo/workspace";

export function isWorkspaceDemoPath(path: string): boolean {
  return path === WORKSPACE_DEMO_PREFIX || path.startsWith(`${WORKSPACE_DEMO_PREFIX}/`);
}

export function parseWorkspaceRoute(path: string): WorkspaceRoute {
  if (path === WORKSPACE_DEMO_PREFIX || path === `${WORKSPACE_DEMO_PREFIX}/`) return { kind: "conversation", conversationId: "conv_1" };
  if (!path.startsWith(`${WORKSPACE_DEMO_PREFIX}/`)) return { kind: "not-found" };
  const segments = path.slice(`${WORKSPACE_DEMO_PREFIX}/`.length).split("/");
  if (segments.some((segment) => segment.length === 0)) return { kind: "not-found" };
  if (segments.length === 1 && segments[0] === "issues") return { kind: "issues" };
  if (segments.length === 2 && segments[0] === "conversations" && isSafeSegment(segments[1])) return { kind: "conversation", conversationId: segments[1] };
  if (segments.length === 2 && segments[0] === "issues" && isSafeSegment(segments[1])) return { kind: "issue", issueId: segments[1] };
  if (segments.length === 3 && segments[0] === "issues" && isSafeSegment(segments[1]) && segments[2] === "plan") return { kind: "issue-plan", issueId: segments[1] };
  if (segments.length === 3 && segments[0] === "issues" && isSafeSegment(segments[1]) && segments[2] === "delivery") return { kind: "issue-delivery", issueId: segments[1] };
  return { kind: "not-found" };
}

export function workspacePath(route: WorkspaceRoute): string {
  switch (route.kind) {
    case "conversation": return `${WORKSPACE_DEMO_PREFIX}/conversations/${route.conversationId}`;
    case "issues": return `${WORKSPACE_DEMO_PREFIX}/issues`;
    case "issue": return `${WORKSPACE_DEMO_PREFIX}/issues/${route.issueId}`;
    case "issue-plan": return `${WORKSPACE_DEMO_PREFIX}/issues/${route.issueId}/plan`;
    case "issue-delivery": return `${WORKSPACE_DEMO_PREFIX}/issues/${route.issueId}/delivery`;
    case "not-found": return WORKSPACE_DEMO_PREFIX;
  }
}
