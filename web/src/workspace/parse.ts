import { identifier, isUuid, object, text, timestamp } from "../values";
import type {
  AnalysisAccepted,
  AnalysisJobStatus,
  AnalysisSnapshot,
  AuthorKind,
  ClarificationSnapshot,
  ConversationList,
  ConversationSnapshot,
  GraphNodeKind,
  GraphNodeStatus,
  IssueCreationConversations,
  IssueCreationOptions,
  IssueCreationReceipt,
  IssueDelivery,
  IssueList,
  IssueListItem,
  IssueRooms,
  IssueSnapshot,
  LinkedIssue,
  Message,
  MessagePage,
  MessageSubmission,
  PlanGraph,
  RoomAvailability,
  RoomObservation,
} from "./types";

function member<const T extends string>(value: unknown, values: readonly T[]): T {
  for (const item of values) if (value === item) return item;
  throw new Error("Invalid choice");
}

function integer(value: unknown, minimum: number, maximum: number): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < minimum || value > maximum) throw new Error("Invalid integer");
  return value;
}

function strings(value: unknown, maximumItems: number, maximumLength: number): string[] {
  if (!Array.isArray(value) || value.length > maximumItems) throw new Error("Invalid list");
  return value.map((item: unknown) => text(item, maximumLength));
}

function cursor(value: unknown): string | null {
  return value === null ? null : text(value, 8192);
}

const sourceKinds = ["issue_page", "manager_mcp"] as const;
const roomAvailabilities = ["ready", "preparing", "unavailable", "unknown"] as const;
const authorKinds = ["user", "manager", "system"] as const;
const clarificationStates = ["open", "answer_saved", "resolved", "superseded", "invalidated"] as const;
const graphKinds = ["repo_task", "coordination", "verification"] as const;
const graphStatuses = ["accepted", "running", "ready_candidate", "waiting", "pending"] as const;
const analysisAvailabilities = ["available", "disabled", "unavailable"] as const;
const analysisStatuses = ["queued", "running", "recovering", "succeeded", "failed"] as const;
const conversationModes = ["new", "existing"] as const;

function parseSource(value: unknown): IssueListItem["source"] {
  const data = object(value);
  return { kind: member(data.kind, sourceKinds), conversationId: identifier(data.conversationId) };
}

function parseLinkedIssue(value: unknown): LinkedIssue {
  const data = object(value);
  return { id: identifier(data.id), number: integer(data.number, 1, 1_000_000), title: text(data.title, 200) };
}

export function parseIssueListItem(value: unknown): IssueListItem {
  const data = object(value);
  return {
    id: identifier(data.id),
    number: integer(data.number, 1, 1_000_000),
    title: text(data.title, 200),
    repositoryIds: strings(data.repositoryIds, 100, 128),
    mainChangeSetId: identifier(data.mainChangeSetId),
    source: parseSource(data.source),
    createdAt: timestamp(data.createdAt),
    revision: identifier(data.revision),
  };
}

export function parseIssueList(value: unknown): IssueList {
  const data = object(value);
  if (!Array.isArray(data.items) || data.items.length > 100) throw new Error("Invalid issue list");
  return { items: data.items.map(parseIssueListItem), nextCursor: cursor(data.nextCursor) };
}

export function parseIssueSnapshot(value: unknown): IssueSnapshot {
  const data = object(value);
  return {
    ...parseIssueListItem(data),
    projectId: identifier(data.projectId),
    description: text(data.description, 20_000),
    acceptanceCriteria: Array.isArray(data.acceptanceCriteria) ? strings(data.acceptanceCriteria, 100, 2000) : [],
  };
}

export function parseConversationList(value: unknown): ConversationList {
  const data = object(value);
  if (!Array.isArray(data.items) || data.items.length > 100) throw new Error("Invalid conversation list");
  return {
    items: data.items.map((item: unknown) => {
      const row = object(item);
      return { id: identifier(row.id), title: text(row.title, 200), createdAt: timestamp(row.createdAt), revision: identifier(row.revision) };
    }),
    nextCursor: cursor(data.nextCursor),
  };
}

export function parseConversationSnapshot(value: unknown): ConversationSnapshot {
  const data = object(value);
  if (!Array.isArray(data.linkedIssues) || data.linkedIssues.length > 100) throw new Error("Invalid linked issues");
  const actions = object(data.actions);
  if (typeof actions.canSend !== "boolean") throw new Error("Invalid conversation actions");
  return {
    id: identifier(data.id),
    title: text(data.title, 200),
    createdAt: timestamp(data.createdAt),
    revision: identifier(data.revision),
    projectId: identifier(data.projectId),
    linkedIssues: data.linkedIssues.map(parseLinkedIssue),
    actions: { canSend: actions.canSend },
  };
}

export function parseIssueCreationOptions(value: unknown): IssueCreationOptions {
  const data = object(value);
  if (!Array.isArray(data.repositories) || data.repositories.length > 100) throw new Error("Invalid repositories");
  if (!Array.isArray(data.allowedConversationModes) || data.allowedConversationModes.length < 1) throw new Error("Invalid conversation modes");
  const analysis = object(data.repositoryAnalysis);
  return {
    projectId: identifier(data.projectId),
    creationContextRevision: identifier(data.creationContextRevision),
    defaultConversationMode: member(data.defaultConversationMode, ["new"]),
    allowedConversationModes: data.allowedConversationModes.map((item: unknown) => member(item, conversationModes)),
    canSubmit: data.canSubmit === true,
    blockingReasons: strings(data.blockingReasons, 20, 128),
    repositories: data.repositories.map((item: unknown) => {
      const repo = object(item);
      return {
        repositoryId: identifier(repo.repositoryId),
        displayName: text(repo.displayName, 512),
        selectable: repo.selectable === true,
        reasons: strings(repo.reasons, 20, 128),
        observedAt: timestamp(repo.observedAt),
      };
    }),
    nextCursor: cursor(data.nextCursor),
    repositoryAnalysis: { availability: member(analysis.availability, analysisAvailabilities), reasonCodes: strings(analysis.reasonCodes, 20, 128) },
  };
}

export function parseIssueCreationConversations(value: unknown): IssueCreationConversations {
  const data = object(value);
  if (!Array.isArray(data.items) || data.items.length > 100) throw new Error("Invalid conversations");
  return {
    items: data.items.map((item: unknown) => {
      const row = object(item);
      return { id: identifier(row.id), title: text(row.title, 200) };
    }),
    nextCursor: cursor(data.nextCursor),
  };
}

export function parseIssueCreationReceipt(value: unknown): IssueCreationReceipt {
  const data = object(value);
  const issue = object(data.issue);
  const changeSet = object(data.mainChangeSet);
  const conversation = object(data.conversation);
  const links = object(data.links);
  const source = object(data.source);
  const creationId = text(data.creationId, 36);
  if (!isUuid(creationId)) throw new Error("Invalid creation id");
  if (member(source.kind, ["issue_page"]) !== "issue_page") throw new Error("Invalid source");
  return {
    creationId: creationId.toLowerCase(),
    status: member(data.status, ["committed"]),
    projectId: identifier(data.projectId),
    createdAt: timestamp(data.createdAt),
    source: { kind: "issue_page" },
    issue: { id: identifier(issue.id), number: integer(issue.number, 1, 1_000_000) },
    mainChangeSet: { id: identifier(changeSet.id) },
    conversation: { id: identifier(conversation.id) },
    links: { issue: text(links.issue, 512), rooms: text(links.rooms, 512), operation: text(links.operation, 512) },
  };
}

function parseRoomObservation(value: unknown): RoomObservation {
  const data = object(value);
  return {
    conversationId: data.conversationId === null ? null : identifier(data.conversationId),
    availability: member(data.availability, roomAvailabilities) as RoomAvailability,
    reason: data.reason === null ? null : text(data.reason, 128),
    roomId: data.roomId === null ? null : identifier(data.roomId),
    canEnter: data.canEnter === true,
    observedAt: timestamp(data.observedAt),
  };
}

export function parseIssueRooms(value: unknown): IssueRooms {
  const data = object(value);
  if (!Array.isArray(data.leaders) || data.leaders.length > 50) throw new Error("Invalid leaders");
  return {
    issueId: identifier(data.issueId),
    main: parseRoomObservation(data.main),
    leaders: data.leaders.map((item: unknown) => {
      const row = object(item);
      const base = parseRoomObservation(row);
      if (row.readOnly !== true) throw new Error("Invalid leader room");
      return { ...base, repositoryIssueId: identifier(row.repositoryIssueId), repositoryId: identifier(row.repositoryId), displayName: text(row.displayName, 512), readOnly: true as const };
    }),
  };
}

export function parseMessage(value: unknown): Message {
  const data = object(value);
  const author = object(data.author);
  let replyTo: Message["replyTo"] = null;
  if (data.replyTo !== null) {
    const reply = object(data.replyTo);
    replyTo = { clarificationId: identifier(reply.clarificationId) };
  }
  return {
    id: identifier(data.id),
    sequence: text(data.sequence, 32),
    author: { kind: member(author.kind, authorKinds) as AuthorKind, displayName: text(author.displayName, 200) },
    content: text(data.content, 20_000),
    createdAt: timestamp(data.createdAt),
    replyTo,
    clarificationId: data.clarificationId === null ? null : identifier(data.clarificationId),
    issueCard: data.issueCard === null || data.issueCard === undefined ? null : parseLinkedIssue(data.issueCard),
  };
}

export function parseMessagePage(value: unknown): MessagePage {
  const data = object(value);
  if (!Array.isArray(data.items) || data.items.length > 100) throw new Error("Invalid messages");
  return { items: data.items.map(parseMessage), nextCursor: cursor(data.nextCursor) };
}

export function parseMessageSubmission(value: unknown): MessageSubmission {
  const data = object(value);
  const links = object(data.links);
  const submissionId = text(data.submissionId, 36);
  if (!isUuid(submissionId)) throw new Error("Invalid submission id");
  let replyTo: MessageSubmission["replyTo"] = null;
  if (data.replyTo !== null) {
    const reply = object(data.replyTo);
    replyTo = { clarificationId: identifier(reply.clarificationId), answeredRevision: identifier(reply.answeredRevision) };
  }
  return {
    submissionId: submissionId.toLowerCase(),
    status: member(data.status, ["committed"]),
    conversationId: identifier(data.conversationId),
    messageId: identifier(data.messageId),
    sequence: text(data.sequence, 32),
    committedAt: timestamp(data.committedAt),
    replyTo,
    links: { message: text(links.message, 512), operation: text(links.operation, 512) },
  };
}

export function parseClarification(value: unknown): ClarificationSnapshot {
  const data = object(value);
  const actions = object(data.actions);
  if (typeof actions.canReply !== "boolean") throw new Error("Invalid clarification actions");
  if (!Array.isArray(data.candidates) || data.candidates.length > 20) throw new Error("Invalid candidates");
  let resolution: ClarificationSnapshot["resolution"] = null;
  if (data.resolution !== null) {
    const row = object(data.resolution);
    const outcome = member(row.outcome, ["issue_target", "no_work"]);
    resolution = { id: identifier(row.id), outcome, issueId: row.issueId === null ? null : identifier(row.issueId) };
  }
  return {
    id: identifier(data.id),
    revision: identifier(data.revision),
    state: member(data.state, clarificationStates),
    sourceMessageId: identifier(data.sourceMessageId),
    questionMessageId: identifier(data.questionMessageId),
    answerMessageId: data.answerMessageId === null ? null : identifier(data.answerMessageId),
    candidates: data.candidates.map((item: unknown) => {
      const row = object(item);
      return { issueId: identifier(row.issueId), number: integer(row.number, 1, 1_000_000), title: text(row.title, 200) };
    }),
    resolution,
    supersededBy: data.supersededBy === null ? null : identifier(data.supersededBy),
    actions: { canReply: actions.canReply },
    reasonCodes: strings(data.reasonCodes, 20, 128),
  };
}

export function parsePlanGraph(value: unknown): PlanGraph {
  const data = object(value);
  if (!Array.isArray(data.nodes) || data.nodes.length > 100) throw new Error("Invalid graph nodes");
  if (!Array.isArray(data.edges) || data.edges.length > 200) throw new Error("Invalid graph edges");
  if (data.readOnly !== true) throw new Error("Invalid graph");
  return {
    issueId: identifier(data.issueId),
    planVersion: text(data.planVersion, 32),
    round: integer(data.round, 1, 1000),
    readOnly: true,
    observedAt: timestamp(data.observedAt),
    nodes: data.nodes.map((item: unknown) => {
      const row = object(item);
      return {
        id: identifier(row.id),
        kind: member(row.kind, graphKinds) as GraphNodeKind,
        title: text(row.title, 200),
        owner: text(row.owner, 200),
        repositoryId: row.repositoryId === null ? null : identifier(row.repositoryId),
        status: member(row.status, graphStatuses) as GraphNodeStatus,
        detail: text(row.detail, 2000),
      };
    }),
    edges: data.edges.map((item: unknown) => {
      const row = object(item);
      return { from: identifier(row.from), to: identifier(row.to) };
    }),
  };
}

export function parseIssueDelivery(value: unknown): IssueDelivery {
  const data = object(value);
  const combination = object(data.combination);
  const verification = object(data.verification);
  const delivery = object(data.delivery);
  if (!Array.isArray(data.repositories) || data.repositories.length > 100) throw new Error("Invalid delivery repositories");
  return {
    issueId: identifier(data.issueId),
    mainChangeSetId: identifier(data.mainChangeSetId),
    combination: { status: member(combination.status, ["not_formed", "formed"]), label: text(combination.label, 200) },
    verification: { status: member(verification.status, ["pending", "running", "passed", "failed"]), label: text(verification.label, 200) },
    delivery: { status: member(delivery.status, ["not_delivered", "in_progress", "delivered"]), label: text(delivery.label, 200) },
    repositories: data.repositories.map((item: unknown) => {
      const row = object(item);
      return { repositoryId: identifier(row.repositoryId), displayName: text(row.displayName, 512), evidenceStatus: member(row.evidenceStatus, ["candidate", "ready", "missing"]) };
    }),
    observedAt: timestamp(data.observedAt),
  };
}

function parseAnalysisStatus(value: unknown): AnalysisJobStatus {
  return member(value, analysisStatuses);
}

export function parseAnalysisAccepted(value: unknown): AnalysisAccepted {
  const data = object(value);
  const analysisId = text(data.analysisId, 36);
  if (!isUuid(analysisId)) throw new Error("Invalid analysis id");
  const links = object(data.links);
  return { analysisId: analysisId.toLowerCase(), status: parseAnalysisStatus(data.status), links: { analysis: text(links.analysis, 512) } };
}

export function parseAnalysisSnapshot(value: unknown): AnalysisSnapshot {
  const data = object(value);
  const accepted = parseAnalysisAccepted(data);
  if (!Array.isArray(data.recommendations) || data.recommendations.length > 100) throw new Error("Invalid recommendations");
  return {
    ...accepted,
    quality: data.quality === null ? null : member(data.quality, ["complete", "partial"]),
    title: text(data.title, 200),
    description: text(data.description, 20_000),
    coverageNote: data.coverageNote === null ? null : text(data.coverageNote, 2000),
    recommendations: data.recommendations.map((item: unknown) => {
      const row = object(item);
      return {
        repositoryId: identifier(row.repositoryId),
        displayName: text(row.displayName, 512),
        reason: text(row.reason, 2000),
        relation: text(row.relation, 128),
        selectable: row.selectable === true,
      };
    }),
  };
}
