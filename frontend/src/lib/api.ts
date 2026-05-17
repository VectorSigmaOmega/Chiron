import type {
  AbstentionClass,
  AssistantResponse,
  ChatMessage,
  ChatSession,
  Citation,
  EvidenceStrength,
  ErrorMessage,
  PendingMessage,
  SourceType,
  TraceStep,
} from "./types";
import {
  abstentionResponse,
  exampleTrace,
  mockSessions,
  statinClarification,
  tbResponse,
} from "./mockData";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000/api";
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

const id = (prefix: string) =>
  `${prefix}_${Math.random().toString(36).slice(2, 10)}`;

interface BackendSession {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

interface BackendMessage {
  id: string;
  session_id: string;
  role: string;
  content: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

interface BackendSubmitResponse {
  run_id: string;
  response: Record<string, unknown>;
}

export interface ChatClient {
  listSessions(): Promise<ChatSession[]>;
  listMessages(sessionId: string): Promise<ChatMessage[]>;
  createSession(firstMessage: string): Promise<ChatSession>;
  sendMessage(
    sessionId: string,
    content: string,
    onTrace: (steps: TraceStep[]) => void,
  ): Promise<{ run_id: string; response: AssistantResponse }>;
}

function basePendingTrace(): TraceStep[] {
  return exampleTrace.map((step) => ({ ...step, status: "pending" }));
}

function deriveTitle(firstMessage: string): string {
  const compact = firstMessage.trim().replace(/\s+/g, " ");
  return compact.slice(0, 64) + (compact.length > 64 ? "…" : "");
}

function derivePreview(messages: ChatMessage[]): string {
  const lastUser = [...messages].reverse().find((message) => message.kind === "user");
  if (lastUser && lastUser.kind === "user") {
    return lastUser.content;
  }
  const lastAssistant = [...messages]
    .reverse()
    .find((message) => message.kind === "assistant");
  if (lastAssistant && lastAssistant.kind === "assistant") {
    return (
      lastAssistant.response.answer ??
      lastAssistant.response.clarification_question ??
      lastAssistant.response.abstention_reason ??
      ""
    );
  }
  return "";
}

function asSourceType(value: unknown): SourceType {
  return value === "guideline" ||
    value === "review" ||
    value === "trial" ||
    value === "label" ||
    value === "registry" ||
    value === "study"
    ? value
    : "study";
}

function asEvidenceStrength(value: unknown): EvidenceStrength | null {
  return value === "high" ||
    value === "moderate" ||
    value === "low" ||
    value === "unknown"
    ? value
    : null;
}

function asAbstentionClass(value: unknown): AbstentionClass | null {
  return value === "insufficient_evidence" ||
    value === "conflicting_evidence" ||
    value === "missing_clinical_context" ||
    value === "coverage_gap" ||
    value === "recency_gap" ||
    value === "ambiguous_query" ||
    value === "out_of_scope"
    ? value
    : null;
}

function normalizeCitation(
  raw: Record<string, unknown>,
  evidenceBySourceId: Map<string, Record<string, unknown>>,
): Citation {
  const sourceId = typeof raw.source_id === "string" ? raw.source_id : "";
  const evidence = evidenceBySourceId.get(sourceId);
  const inferredSourceType =
    asSourceType(
      typeof raw.source_type === "string"
        ? raw.source_type
        : evidence?.source_type,
    );
  const inferredPublisher =
    typeof raw.publisher === "string"
      ? raw.publisher
      : typeof evidence?.publisher === "string"
        ? evidence.publisher
        : null;
  const snippet =
    typeof raw.snippet === "string"
      ? raw.snippet
      : typeof evidence?.key_claim === "string"
        ? evidence.key_claim
        : undefined;

  return {
    label: typeof raw.label === "string" ? raw.label : "0",
    source_id: sourceId,
    title: typeof raw.title === "string" ? raw.title : "Untitled source",
    url: typeof raw.url === "string" ? raw.url : "#",
    publication_date:
      typeof raw.publication_date === "string" ? raw.publication_date : null,
    source_type: inferredSourceType,
    publisher: inferredPublisher,
    snippet,
  };
}

function normalizeResponse(raw: Record<string, unknown>): AssistantResponse {
  const rawEvidence = Array.isArray(raw.evidence_items)
    ? (raw.evidence_items as Record<string, unknown>[])
    : [];
  const evidence_items = rawEvidence.map((item, index) => ({
    evidence_id:
      typeof item.evidence_id === "string" ? item.evidence_id : `ev_${index + 1}`,
    source_id: typeof item.source_id === "string" ? item.source_id : `src_${index + 1}`,
    source_type: asSourceType(item.source_type),
    title: typeof item.title === "string" ? item.title : "Untitled evidence",
    url: typeof item.url === "string" ? item.url : "#",
    publication_date:
      typeof item.publication_date === "string" ? item.publication_date : null,
    publisher: typeof item.publisher === "string" ? item.publisher : null,
    population: typeof item.population === "string" ? item.population : null,
    intervention: typeof item.intervention === "string" ? item.intervention : null,
    outcome: typeof item.outcome === "string" ? item.outcome : null,
    key_claim: typeof item.key_claim === "string" ? item.key_claim : "No claim extracted.",
    safety_notes: Array.isArray(item.safety_notes)
      ? item.safety_notes.filter((note): note is string => typeof note === "string")
      : [],
    limitations: Array.isArray(item.limitations)
      ? item.limitations.filter((note): note is string => typeof note === "string")
      : [],
    evidence_strength: asEvidenceStrength(item.evidence_strength) ?? "unknown",
  }));
  const evidenceBySourceId = new Map(
    rawEvidence.map((item) => [
      typeof item.source_id === "string" ? item.source_id : "",
      item,
    ]),
  );

  return {
    status:
      raw.status === "answered" ||
      raw.status === "needs_clarification" ||
      raw.status === "abstained"
        ? raw.status
        : "abstained",
    answer: typeof raw.answer === "string" ? raw.answer : null,
    clarification_question:
      typeof raw.clarification_question === "string"
        ? raw.clarification_question
        : null,
    clarification_options: Array.isArray(raw.clarification_options)
      ? raw.clarification_options.filter((item): item is string => typeof item === "string")
      : undefined,
    abstention_class: asAbstentionClass(raw.abstention_class),
    abstention_reason:
      typeof raw.abstention_reason === "string" ? raw.abstention_reason : null,
    evidence_summary: Array.isArray(raw.evidence_summary)
      ? raw.evidence_summary.filter((item): item is string => typeof item === "string")
      : [],
    evidence_strength: asEvidenceStrength(raw.evidence_strength),
    limitations: Array.isArray(raw.limitations)
      ? raw.limitations.filter((item): item is string => typeof item === "string")
      : [],
    citations: Array.isArray(raw.citations)
      ? raw.citations
          .filter((item): item is Record<string, unknown> => !!item && typeof item === "object")
          .map((citation) => normalizeCitation(citation, evidenceBySourceId))
      : [],
    evidence_items,
    last_literature_check_at:
      typeof raw.last_literature_check_at === "string"
        ? raw.last_literature_check_at
        : null,
  };
}

function normalizeMessage(raw: BackendMessage): ChatMessage | null {
  if (raw.role === "user") {
    return {
      id: raw.id,
      kind: "user",
      content: raw.content,
      created_at: raw.created_at,
    };
  }

  if (raw.role === "assistant") {
    return {
      id: raw.id,
      kind: "assistant",
      run_id:
        typeof raw.metadata_json.run_id === "string" ? raw.metadata_json.run_id : raw.id,
      created_at: raw.created_at,
      response: normalizeResponse(raw.metadata_json),
    };
  }

  return null;
}

function normalizeSession(raw: BackendSession): ChatSession {
  return {
    id: raw.id,
    title: raw.title ?? "untitled consult",
    created_at: raw.created_at,
    preview: "",
    messages: [],
    messagesLoaded: false,
  };
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

function selectMockResponse(content: string): AssistantResponse {
  const c = content.toLowerCase();
  if (
    c.includes("billing") ||
    c.includes("prior auth") ||
    c.includes("insurance") ||
    c.includes("coverage")
  ) {
    return abstentionResponse;
  }
  if (c.length < 40 || c.includes("which statin") || c.includes("ambiguous")) {
    return statinClarification;
  }
  return tbResponse;
}

async function streamMockTrace(
  onTrace: (steps: TraceStep[]) => void,
  responseStatus: AssistantResponse["status"],
) {
  const trace: TraceStep[] = JSON.parse(JSON.stringify(exampleTrace));
  const isClarification = responseStatus === "needs_clarification";
  const isAbstain = responseStatus === "abstained";

  trace[0].status = "running";
  onTrace([...trace]);
  await sleep(380);
  trace[0].status = "done";
  onTrace([...trace]);

  if (isClarification) {
    trace.slice(1).forEach((s) => (s.status = "skipped"));
    onTrace([...trace]);
    await sleep(220);
    return;
  }

  if (isAbstain) {
    trace[1].status = "skipped";
    trace[2].status = "skipped";
    trace[3].status = "skipped";
    trace[4].status = "skipped";
    trace[5].status = "running";
    onTrace([...trace]);
    await sleep(420);
    trace[5].status = "done";
    onTrace([...trace]);
    return;
  }

  trace[1].status = "running";
  trace[2].status = "running";
  onTrace([...trace]);
  await sleep(520);
  trace[1].status = "done";
  onTrace([...trace]);
  await sleep(640);
  trace[2].status = "done";
  trace[3].status = "running";
  onTrace([...trace]);
  await sleep(520);
  trace[3].status = "done";
  trace[4].status = "running";
  onTrace([...trace]);
  await sleep(640);
  trace[4].status = "done";
  trace[5].status = "running";
  onTrace([...trace]);
  await sleep(420);
  trace[5].status = "done";
  onTrace([...trace]);
}

class MockChatClient implements ChatClient {
  private sessions: ChatSession[] = JSON.parse(JSON.stringify(mockSessions));

  async listSessions(): Promise<ChatSession[]> {
    await sleep(80);
    return this.sessions;
  }

  async listMessages(sessionId: string): Promise<ChatMessage[]> {
    await sleep(80);
    return this.sessions.find((session) => session.id === sessionId)?.messages ?? [];
  }

  async createSession(firstMessage: string): Promise<ChatSession> {
    await sleep(120);
    const session: ChatSession = {
      id: id("sess"),
      title: deriveTitle(firstMessage),
      created_at: new Date().toISOString(),
      preview: firstMessage,
      messages: [],
      messagesLoaded: true,
    };
    this.sessions = [session, ...this.sessions];
    return session;
  }

  async sendMessage(
    _sessionId: string,
    content: string,
    onTrace: (steps: TraceStep[]) => void,
  ): Promise<{ run_id: string; response: AssistantResponse }> {
    const response = selectMockResponse(content);
    await streamMockTrace(onTrace, response.status);
    return { run_id: id("run"), response };
  }
}

class HttpChatClient implements ChatClient {
  async listSessions(): Promise<ChatSession[]> {
    const sessions = await fetchJson<BackendSession[]>("/sessions");
    return sessions.map(normalizeSession);
  }

  async listMessages(sessionId: string): Promise<ChatMessage[]> {
    const messages = await fetchJson<BackendMessage[]>(`/sessions/${sessionId}/messages`);
    return messages
      .map(normalizeMessage)
      .filter((message): message is ChatMessage => message !== null);
  }

  async createSession(firstMessage: string): Promise<ChatSession> {
    const session = await fetchJson<BackendSession>("/sessions", {
      method: "POST",
      body: JSON.stringify({ title: deriveTitle(firstMessage) }),
    });
    return {
      ...normalizeSession(session),
      preview: firstMessage,
      messagesLoaded: true,
    };
  }

  async sendMessage(
    sessionId: string,
    content: string,
    onTrace: (steps: TraceStep[]) => void,
  ): Promise<{ run_id: string; response: AssistantResponse }> {
    const trace = basePendingTrace();
    let stageIndex = 0;
    const stageOrder = [0, 1, 2, 3, 4, 5];

    const tick = () => {
      const next = stageOrder[stageIndex];
      if (next === undefined) return;
      if (stageIndex > 0) {
        const previous = stageOrder[stageIndex - 1];
        if (previous !== undefined && trace[previous]) {
          trace[previous] = { ...trace[previous], status: "done" };
        }
      }
      if (trace[next]) {
        trace[next] = { ...trace[next], status: "running" };
      }
      onTrace([...trace]);
      stageIndex += 1;
    };

    tick();
    const timer = globalThis.setInterval(tick, 1200);

    try {
      const payload = await fetchJson<BackendSubmitResponse>(`/sessions/${sessionId}/messages`, {
        method: "POST",
        body: JSON.stringify({ role: "user", content }),
      });
      trace.forEach((step, index) => {
        trace[index] = {
          ...step,
          status: step.status === "skipped" ? "skipped" : "done",
        };
      });
      onTrace([...trace]);
      return {
        run_id: payload.run_id,
        response: normalizeResponse(payload.response),
      };
    } finally {
      globalThis.clearInterval(timer);
    }
  }
}

export function withSessionMessages(session: ChatSession, messages: ChatMessage[]): ChatSession {
  return {
    ...session,
    preview: derivePreview(messages),
    messages,
    messagesLoaded: true,
  };
}

export function buildPendingMessage(): PendingMessage {
  return {
    id: id("pending"),
    kind: "pending",
    run_id: id("run"),
    created_at: new Date().toISOString(),
    trace: basePendingTrace(),
  };
}

export function buildErrorMessage(reason: string): ErrorMessage {
  return {
    id: id("err"),
    kind: "error",
    created_at: new Date().toISOString(),
    reason,
    retryable: true,
  };
}

export const chatClient: ChatClient = USE_MOCKS ? new MockChatClient() : new HttpChatClient();
