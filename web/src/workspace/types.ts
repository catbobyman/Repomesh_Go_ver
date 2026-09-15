export const DEMO_PROJECT_ID = "prj_orders";
export const DEMO_CSRF = "demo-csrf";
export const DEMO_ACTOR = "usr_demo";

export type SourceKind = "issue_page" | "manager_mcp";
export type RoomAvailability = "ready" | "preparing" | "unavailable" | "unknown";
export type AuthorKind = "user" | "manager" | "system";
export type ClarificationState = "open" | "answer_saved" | "resolved" | "superseded" | "invalidated";
export type GraphNodeKind = "upstream_task" | "coordination" | "verification";
export type NativeTaskStatus = "planned" | "assigned" | "in_progress" | "submitted" | "completed" | "revision" | "blocked" | "cancelled";
export type WorkflowTaskStatus = "pending" | "delegated" | "in-progress" | "completed" | "revision" | "blocked";
export type DispatchState = "not_dispatched" | "attempt_active" | "completed" | "not_applicable";
export type RoomRole = "main" | "leader";
export type RoomMessageRole = "user" | "manager" | "leader" | "worker" | "system";
export type UpstreamRoomKind = "task_room" | "team_room" | "worker_room" | "direct_room";
export type AnalysisAvailability = "available" | "disabled" | "unavailable";
export type AnalysisJobStatus = "queued" | "running" | "recovering" | "succeeded" | "failed";
export type AnalysisQuality = "complete" | "partial";

export type IssueSource = { kind: SourceKind; conversationId: string };
export type IssueListItem = {
  id: string;
  number: number;
  title: string;
  repositoryIds: string[];
  mainChangeSetId: string;
  source: IssueSource;
  createdAt: string;
  revision: string;
};
export type IssueSnapshot = IssueListItem & {
  projectId: string;
  description: string;
  acceptanceCriteria: string[];
};
export type IssueList = { items: IssueListItem[]; nextCursor: string | null };
export type ConversationListItem = { id: string; title: string; createdAt: string; revision: string };
export type ConversationList = { items: ConversationListItem[]; nextCursor: string | null };
export type LinkedIssue = { id: string; number: number; title: string };
export type ConversationSnapshot = ConversationListItem & {
  projectId: string;
  linkedIssues: LinkedIssue[];
  actions: { canSend: boolean };
};
export type CreationRepository = {
  repositoryId: string;
  displayName: string;
  selectable: boolean;
  reasons: string[];
  observedAt: string;
};
export type IssueCreationOptions = {
  projectId: string;
  creationContextRevision: string;
  defaultConversationMode: "new";
  allowedConversationModes: Array<"new" | "existing">;
  canSubmit: boolean;
  blockingReasons: string[];
  repositories: CreationRepository[];
  nextCursor: string | null;
  repositoryAnalysis: { availability: AnalysisAvailability; reasonCodes: string[] };
};
export type IssueCreationConversations = { items: Array<{ id: string; title: string }>; nextCursor: string | null };
export type IssueCreationReceipt = {
  creationId: string;
  status: "committed";
  projectId: string;
  createdAt: string;
  source: { kind: "issue_page" };
  issue: { id: string; number: number };
  mainChangeSet: { id: string };
  conversation: { id: string };
  links: { issue: string; rooms: string; operation: string };
};
export type RoomObservation = {
  conversationId: string | null;
  availability: RoomAvailability;
  reason: string | null;
  roomId: string | null;
  canEnter: boolean;
  observedAt: string;
};
export type LeaderRoom = RoomObservation & {
  repositoryIssueId: string;
  repositoryId: string;
  displayName: string;
  readOnly: true;
};
export type IssueRooms = { issueId: string; main: RoomObservation; leaders: LeaderRoom[] };
export type MessageReplyTo = { clarificationId: string };
export type Message = {
  id: string;
  sequence: string;
  author: { kind: AuthorKind; displayName: string };
  content: string;
  createdAt: string;
  replyTo: MessageReplyTo | null;
  clarificationId: string | null;
  issueCard: LinkedIssue | null;
};
export type MessagePage = { items: Message[]; nextCursor: string | null };
export type MessageSubmission = {
  submissionId: string;
  status: "committed";
  conversationId: string;
  messageId: string;
  sequence: string;
  committedAt: string;
  replyTo: { clarificationId: string; answeredRevision: string } | null;
  links: { message: string; operation: string };
};
export type ClarificationCandidate = { issueId: string; number: number; title: string };
export type ClarificationSnapshot = {
  id: string;
  revision: string;
  state: ClarificationState;
  sourceMessageId: string;
  questionMessageId: string;
  answerMessageId: string | null;
  candidates: ClarificationCandidate[];
  resolution: { id: string; outcome: "issue_target" | "no_work"; issueId: string | null } | null;
  supersededBy: string | null;
  actions: { canReply: boolean };
  reasonCodes: string[];
};
export type PlanGraphNode = {
  id: string;
  kind: GraphNodeKind;
  title: string;
  owner: string;
  repositoryId: string | null;
  nativeStatus: NativeTaskStatus | null;
  workflowStatus: WorkflowTaskStatus | null;
  inNext: boolean;
  dispatchState: DispatchState;
  detail: string;
};
export type NativeTask = {
  taskId: string;
  title: string;
  assignedTo: string;
  dependsOn: string[];
  status: NativeTaskStatus;
};
export type WorkflowNode = { id: string; name: string; status: WorkflowTaskStatus; assignee: string };
export type WorkflowEdge = { source: string; target: string; conditional: boolean };
export type UpstreamProjectGraph = {
  projectId: string;
  repositoryId: string;
  teamId: string;
  native: { status: "active" | "paused" | "completed"; planType: "dag" | "loop"; tasks: NativeTask[] };
  workflow: {
    nodes: WorkflowNode[];
    edges: WorkflowEdge[];
    next: string[];
    interrupts: Array<{ type: string; message: string }>;
    values: { projectId: string; status: string; planType: string; taskCount: Record<string, number> };
  };
};
export type PlanGraph = {
  issueId: string;
  planVersion: string;
  round: number;
  readOnly: true;
  observedAt: string;
  upstreamProjects: UpstreamProjectGraph[];
  businessOverlay: {
    readyIsNotDispatch: true;
    crossRepoEdges: Array<{ from: { projectId: string; taskId: string }; to: { projectId: string; taskId: string } }>;
    blockingReasons: Record<string, string[]>;
    dispatchState: Record<string, DispatchState>;
  };
  nodes: PlanGraphNode[];
  edges: Array<{ from: string; to: string }>;
};
export type RoomParticipant = { role: RoomMessageRole; displayName: string };
export type RoomSnapshotMessage = {
  id: string;
  sequence: string;
  author: { role: RoomMessageRole; displayName: string };
  content: string;
  createdAt: string;
  kind: "text";
};
export type RoomSnapshot = {
  issueId: string;
  roomId: string;
  roomRole: RoomRole;
  readOnly: boolean;
  displayName: string;
  conversationId: string | null;
  availability: RoomAvailability;
  canEnter: boolean;
  observedAt: string;
  repositoryId: string | null;
  repositoryIssueId: string | null;
  upstream: { roomKind: UpstreamRoomKind; lifecycle: "persistent" | "ephemeral"; createdBy: string; schemaVersion: number };
  participants: RoomParticipant[];
  messages: RoomSnapshotMessage[];
  composer: { enabled: boolean; target: "manager" | "none" };
  environment: { repositoryDisplayName: string; changeSetId: string; attemptLabel: string; workDirNote: string } | null;
  navigation: { issueId: string; conversationId: string };
};
export type DeliveryRepository = {
  repositoryId: string;
  displayName: string;
  evidenceStatus: "candidate" | "ready" | "missing";
};
export type IssueDelivery = {
  issueId: string;
  mainChangeSetId: string;
  combination: { status: "not_formed" | "formed"; label: string };
  verification: { status: "pending" | "running" | "passed" | "failed"; label: string };
  delivery: { status: "not_delivered" | "in_progress" | "delivered"; label: string };
  repositories: DeliveryRepository[];
  observedAt: string;
};
export type AnalysisAccepted = {
  analysisId: string;
  status: AnalysisJobStatus;
  links: { analysis: string };
};
export type AnalysisRecommendation = {
  repositoryId: string;
  displayName: string;
  reason: string;
  relation: string;
  selectable: boolean;
};
export type AnalysisSnapshot = AnalysisAccepted & {
  quality: AnalysisQuality | null;
  title: string;
  description: string;
  coverageNote: string | null;
  recommendations: AnalysisRecommendation[];
};
