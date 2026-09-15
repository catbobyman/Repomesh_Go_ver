import type { DispatchState, GraphNodeKind, NativeTaskStatus, WorkflowTaskStatus } from "./types";

export const kindLabel: Record<GraphNodeKind, string> = {
  upstream_task: "上游任务",
  coordination: "业务协调",
  verification: "验证活动",
};

export const nativeStatusLabel: Record<NativeTaskStatus, string> = {
  planned: "planned · 已规划",
  assigned: "assigned · 已委派",
  in_progress: "in_progress · 执行中",
  submitted: "submitted · 已提交",
  completed: "completed · 已完成",
  revision: "revision · 需修订",
  blocked: "blocked · 阻塞",
  cancelled: "cancelled · 已取消",
};

export const workflowStatusLabel: Record<WorkflowTaskStatus, string> = {
  pending: "pending · 压缩待开始",
  delegated: "delegated · 压缩已委派",
  "in-progress": "in-progress · 压缩进行中",
  completed: "completed · 压缩已完成",
  revision: "revision · 压缩需修订",
  blocked: "blocked · 压缩阻塞",
};

export const dispatchLabel: Record<DispatchState, string> = {
  not_dispatched: "未派工",
  attempt_active: "执行尝试进行中",
  completed: "已完成",
  not_applicable: "不适用（业务叠加）",
};

export function nodeStatusLine(input: {
  nativeStatus: NativeTaskStatus | null;
  workflowStatus: WorkflowTaskStatus | null;
  inNext: boolean;
  dispatchState: DispatchState;
}): string {
  if (input.inNext) return "候选就绪 · 非派工";
  if (input.nativeStatus !== null) return nativeStatusLabel[input.nativeStatus];
  if (input.dispatchState === "not_applicable") return "RepoMesh 叠加 · 非上游状态";
  return dispatchLabel[input.dispatchState];
}
