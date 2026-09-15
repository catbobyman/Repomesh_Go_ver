import type { Result } from "../api";
import { request } from "../api";
import {
  parseAnalysisAccepted,
  parseAnalysisSnapshot,
  parseClarification,
  parseConversationList,
  parseConversationSnapshot,
  parseIssueCreationConversations,
  parseIssueCreationOptions,
  parseIssueCreationReceipt,
  parseIssueDelivery,
  parseIssueList,
  parseIssueRooms,
  parseIssueSnapshot,
  parseMessagePage,
  parseMessageSubmission,
  parsePlanGraph,
  parseRoomSnapshot,
} from "./parse";
import { DEMO_CSRF, DEMO_PROJECT_ID } from "./types";
import type {
  AnalysisAccepted,
  AnalysisSnapshot,
  ClarificationSnapshot,
  ConversationList,
  ConversationSnapshot,
  IssueCreationConversations,
  IssueCreationOptions,
  IssueCreationReceipt,
  IssueDelivery,
  IssueList,
  IssueRooms,
  IssueSnapshot,
  MessagePage,
  MessageSubmission,
  PlanGraph,
  RoomSnapshot,
} from "./types";

const project = DEMO_PROJECT_ID;
const csrf = DEMO_CSRF;

export const workspaceCsrf = csrf;
export const workspaceProjectId = project;

export const readIssueList = (query = "") =>
  request({ path: `/api/projects/${project}/issues${query}`, parse: parseIssueList });

export const readConversationList = () =>
  request({ path: `/api/projects/${project}/conversations`, parse: parseConversationList });

export const readConversation = (conversationId: string) =>
  request({ path: `/api/projects/${project}/conversations/${encodeURIComponent(conversationId)}`, parse: parseConversationSnapshot });

export const readMessages = (conversationId: string) =>
  request({ path: `/api/projects/${project}/conversations/${encodeURIComponent(conversationId)}/messages`, parse: parseMessagePage });

export const readClarification = (conversationId: string, clarificationId: string) =>
  request({ path: `/api/projects/${project}/conversations/${encodeURIComponent(conversationId)}/clarifications/${encodeURIComponent(clarificationId)}`, parse: parseClarification });

export const sendMessage = (conversationId: string, key: string, body: { content: string; replyTo?: { clarificationId: string; expectedRevision: string } }) =>
  request({
    path: `/api/projects/${project}/conversations/${encodeURIComponent(conversationId)}/messages`,
    method: "POST",
    body,
    key,
    csrfToken: csrf,
    parse: parseMessageSubmission,
    successStatuses: [200, 201],
  });

export const readIssue = (issueId: string) => request({ path: `/api/issues/${encodeURIComponent(issueId)}`, parse: parseIssueSnapshot });
export const readIssueRooms = (issueId: string) => request({ path: `/api/issues/${encodeURIComponent(issueId)}/rooms`, parse: parseIssueRooms });
export const readRoom = (issueId: string, roomId: string) =>
  request({ path: `/api/issues/${encodeURIComponent(issueId)}/rooms/${encodeURIComponent(roomId)}`, parse: parseRoomSnapshot });
export const readPlanGraph = (issueId: string) => request({ path: `/api/issues/${encodeURIComponent(issueId)}/plan-graph`, parse: parsePlanGraph });
export const readDelivery = (issueId: string) => request({ path: `/api/issues/${encodeURIComponent(issueId)}/delivery`, parse: parseIssueDelivery });

export const readCreationOptions = () =>
  request({ path: `/api/projects/${project}/issue-creation-options`, parse: parseIssueCreationOptions });

export const readCreationConversations = () =>
  request({ path: `/api/projects/${project}/issue-creation-conversations`, parse: parseIssueCreationConversations });

export const createIssue = (key: string, body: object): Promise<Result<IssueCreationReceipt>> =>
  request({
    path: `/api/projects/${project}/issues`,
    method: "POST",
    body,
    key,
    csrfToken: csrf,
    parse: parseIssueCreationReceipt,
    successStatuses: [200, 201],
  });

export const readIssueCreation = (creationId: string) =>
  request({ path: `/api/projects/${project}/issue-creations/${encodeURIComponent(creationId)}`, parse: parseIssueCreationReceipt });

export const startRepositoryAnalysis = (key: string, body: object): Promise<Result<AnalysisAccepted>> =>
  request({
    path: `/api/projects/${project}/repository-analyses`,
    method: "POST",
    body,
    key,
    csrfToken: csrf,
    parse: parseAnalysisAccepted,
    successStatuses: [200, 202],
  });

export const readRepositoryAnalysis = (analysisId: string): Promise<Result<AnalysisSnapshot>> =>
  request({ path: `/api/projects/${project}/repository-analyses/${encodeURIComponent(analysisId)}`, parse: parseAnalysisSnapshot });

export const resetWorkspaceDemo = () =>
  request({ path: "/api/demo/workspace/reset", method: "POST", body: {}, csrfToken: csrf, parse: (value: unknown) => value, successStatuses: [200] });

export type {
  AnalysisAccepted,
  AnalysisSnapshot,
  ClarificationSnapshot,
  ConversationList,
  ConversationSnapshot,
  IssueCreationConversations,
  IssueCreationOptions,
  IssueCreationReceipt,
  IssueDelivery,
  IssueList,
  IssueRooms,
  IssueSnapshot,
  MessagePage,
  MessageSubmission,
  PlanGraph,
  RoomSnapshot,
};
