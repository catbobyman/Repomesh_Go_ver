import { DEMO_PROJECT_ID } from "../types";
import type { AnalysisJobStatus, AuthorKind, ClarificationState, RoomAvailability } from "../types";

export const OBSERVED_AT = "2026-09-15T12:00:00Z";

export type StoredIssue = {
  id: string;
  number: number;
  title: string;
  description: string;
  acceptanceCriteria: string[];
  repositoryIds: string[];
  mainChangeSetId: string;
  conversationId: string;
  createdAt: string;
  revision: string;
  sourceKind: "issue_page";
};

export type StoredConversation = {
  id: string;
  title: string;
  createdAt: string;
  revision: string;
};

export type StoredMessage = {
  id: string;
  conversationId: string;
  sequence: number;
  authorKind: AuthorKind;
  displayName: string;
  content: string;
  createdAt: string;
  replyToClarificationId: string | null;
  clarificationId: string | null;
  issueId: string | null;
};

export type StoredClarification = {
  id: string;
  conversationId: string;
  revision: string;
  state: ClarificationState;
  sourceMessageId: string;
  questionMessageId: string;
  answerMessageId: string | null;
  candidateIssueIds: string[];
};

export type StoredCreation = {
  creationId: string;
  actor: string;
  input: string;
  issueId: string;
  conversationId: string;
  createdAt: string;
};

export type StoredSubmission = {
  submissionId: string;
  actor: string;
  conversationId: string;
  input: string;
  messageId: string;
  sequence: number;
  committedAt: string;
  replyTo: { clarificationId: string; answeredRevision: string } | null;
};

export type StoredAnalysis = {
  analysisId: string;
  actor: string;
  input: string;
  status: AnalysisJobStatus;
  title: string;
  description: string;
};

export type WorkspaceStore = {
  issues: StoredIssue[];
  conversations: StoredConversation[];
  messages: StoredMessage[];
  clarifications: StoredClarification[];
  creations: StoredCreation[];
  submissions: StoredSubmission[];
  analyses: StoredAnalysis[];
  nextIssueNumber: number;
  nextSequence: Record<string, number>;
};

export const REPOSITORIES = [
  { repositoryId: "repo_service", displayName: "repomesh/order-service", selectable: true, reasons: [] as string[], observedAt: OBSERVED_AT },
  { repositoryId: "repo_admin", displayName: "repomesh/admin-console", selectable: true, reasons: [] as string[], observedAt: OBSERVED_AT },
  { repositoryId: "repo_billing", displayName: "partner/billing-api", selectable: false, reasons: ["APP_PERMISSION_MISSING"], observedAt: OBSERVED_AT },
];

export const CREATION_CONTEXT_REVISION = "ctx_17";

export function seedStore(): WorkspaceStore {
  const issues: StoredIssue[] = [
    { id: "iss_1", number: 1, title: "支付状态筛选", description: "在订单列表增加支付状态筛选，并保持原有导出权限。", acceptanceCriteria: ["无读取权限的用户无法看到筛选结果"], repositoryIds: ["repo_service", "repo_admin"], mainChangeSetId: "cs_1", conversationId: "conv_1", createdAt: "2026-09-10T00:02:00Z", revision: "issrev_1", sourceKind: "issue_page" },
    { id: "iss_2", number: 2, title: "订单导出", description: "支持按当前筛选条件导出订单。", acceptanceCriteria: [], repositoryIds: ["repo_service", "repo_admin"], mainChangeSetId: "cs_2", conversationId: "conv_1", createdAt: "2026-09-10T00:03:00Z", revision: "issrev_1", sourceKind: "issue_page" },
    { id: "iss_3", number: 3, title: "订单归档", description: "支持归档已完成订单，并保留查询记录。归档后仍遵循原有访问权限。", acceptanceCriteria: ["无读取权限的用户无法访问归档订单"], repositoryIds: ["repo_service", "repo_admin"], mainChangeSetId: "cs_3", conversationId: "conv_2", createdAt: "2026-09-10T00:04:00Z", revision: "issrev_1", sourceKind: "issue_page" },
  ];
  const conversations: StoredConversation[] = [
    { id: "conv_1", title: "讨论订单查询体验", createdAt: "2026-09-10T00:01:00Z", revision: "convrev_1" },
    { id: "conv_2", title: "订单归档", createdAt: "2026-09-10T00:04:00Z", revision: "convrev_1" },
  ];
  const messages: StoredMessage[] = [
    { id: "msg_1", conversationId: "conv_1", sequence: 1, authorKind: "user", displayName: "林悦", content: "一起讨论支付筛选和订单导出。", createdAt: "2026-09-10T00:05:00Z", replyToClarificationId: null, clarificationId: null, issueId: null },
    { id: "msg_2", conversationId: "conv_1", sequence: 2, authorKind: "manager", displayName: "Manager", content: "这两个目标可以分别建立 Issue，保留各自的计划、验收和交付记录。", createdAt: "2026-09-10T00:06:00Z", replyToClarificationId: null, clarificationId: null, issueId: null },
    { id: "msg_3", conversationId: "conv_1", sequence: 3, authorKind: "system", displayName: "系统", content: "支付状态筛选", createdAt: "2026-09-10T00:07:00Z", replyToClarificationId: null, clarificationId: null, issueId: "iss_1" },
    { id: "msg_4", conversationId: "conv_1", sequence: 4, authorKind: "system", displayName: "系统", content: "订单导出", createdAt: "2026-09-10T00:07:30Z", replyToClarificationId: null, clarificationId: null, issueId: "iss_2" },
    { id: "msg_5", conversationId: "conv_1", sequence: 5, authorKind: "user", displayName: "林悦", content: "这个也加上日期范围。", createdAt: "2026-09-10T00:08:00Z", replyToClarificationId: null, clarificationId: null, issueId: null },
    { id: "msg_6", conversationId: "conv_1", sequence: 6, authorKind: "manager", displayName: "Manager", content: "你说的“这个”，指的是哪条 Issue？\n支付状态筛选和订单导出都可能涉及日期范围。", createdAt: "2026-09-10T00:08:30Z", replyToClarificationId: null, clarificationId: "cl_1", issueId: null },
    { id: "msg_7", conversationId: "conv_2", sequence: 1, authorKind: "system", displayName: "系统", content: "页面创建了 Issue #3 订单归档，并关联本会话。", createdAt: "2026-09-10T00:04:01Z", replyToClarificationId: null, clarificationId: null, issueId: "iss_3" },
  ];
  const clarifications: StoredClarification[] = [
    { id: "cl_1", conversationId: "conv_1", revision: "rev_open_1", state: "open", sourceMessageId: "msg_5", questionMessageId: "msg_6", answerMessageId: null, candidateIssueIds: ["iss_1", "iss_2"] },
  ];
  return {
    issues,
    conversations,
    messages,
    clarifications,
    creations: [],
    submissions: [],
    analyses: [],
    nextIssueNumber: 4,
    nextSequence: { conv_1: 7, conv_2: 2 },
  };
}

export function mainRoom(_issue: StoredIssue): { availability: RoomAvailability; reason: string | null; roomId: string | null; canEnter: boolean } {
  return { availability: "unavailable", reason: "NOT_ASSOCIATED", roomId: null, canEnter: false };
}

export function projectId(): string {
  return DEMO_PROJECT_ID;
}
