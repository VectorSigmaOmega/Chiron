// Mirrors the backend response contract documented in docs/ARCHITECTURE.md §11.
// The frontend treats the backend as the source of truth for assistant state.

export type AssistantStatus =
  | "answered"
  | "needs_clarification"
  | "abstained";

export type EvidenceStrength = "high" | "moderate" | "low" | "unknown";

export type SourceType =
  | "guideline"
  | "review"
  | "trial"
  | "label"
  | "registry"
  | "study";

export type AbstentionClass =
  | "insufficient_evidence"
  | "conflicting_evidence"
  | "missing_clinical_context"
  | "coverage_gap"
  | "recency_gap"
  | "ambiguous_query"
  | "out_of_scope";

export interface Citation {
  label: string;
  source_id: string;
  title: string;
  url: string;
  publication_date: string | null;
  source_type: SourceType;
  publisher: string | null;
  snippet?: string;
}

export interface EvidenceItem {
  evidence_id: string;
  source_id: string;
  source_type: SourceType;
  title: string;
  url: string;
  publication_date: string | null;
  publisher: string | null;
  population: string | null;
  intervention: string | null;
  outcome: string | null;
  key_claim: string;
  safety_notes: string[];
  limitations: string[];
  evidence_strength: EvidenceStrength;
}

export interface AssistantResponse {
  status: AssistantStatus;
  answer: string | null;
  clarification_question: string | null;
  clarification_options?: string[];
  abstention_class: AbstentionClass | null;
  abstention_reason: string | null;
  evidence_summary: string[];
  evidence_strength: EvidenceStrength | null;
  limitations: string[];
  citations: Citation[];
  evidence_items: EvidenceItem[];
  last_literature_check_at: string | null;
}

export interface UserMessage {
  id: string;
  kind: "user";
  content: string;
  created_at: string;
}

export interface AssistantMessage {
  id: string;
  kind: "assistant";
  run_id: string;
  created_at: string;
  response: AssistantResponse;
}

export interface PendingMessage {
  id: string;
  kind: "pending";
  run_id: string;
  created_at: string;
  trace: TraceStep[];
}

export interface ErrorMessage {
  id: string;
  kind: "error";
  created_at: string;
  reason: string;
  retryable: boolean;
}

export type ChatMessage =
  | UserMessage
  | AssistantMessage
  | PendingMessage
  | ErrorMessage;

export interface TraceStep {
  id: string;
  label: string;
  agent: "parser" | "guideline" | "literature" | "drug_safety" | "trials" | "synthesizer" | "verifier";
  status: "pending" | "running" | "done" | "skipped";
  source_count?: number;
  started_at?: string;
  ended_at?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  preview: string;
  messages: ChatMessage[];
  messagesLoaded?: boolean;
  pinned?: boolean;
}
