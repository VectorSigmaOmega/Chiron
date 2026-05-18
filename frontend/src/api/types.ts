/* ============================================================
   Backend contract — mirrors FRONTEND_AGENT_BRIEF.md exactly.
   Nothing else in the app should redefine these shapes.
   ============================================================ */

export type AssistantStatus = 'answered' | 'needs_clarification' | 'abstained'

export type EvidenceStrength = 'high' | 'moderate' | 'low' | 'unknown'

export interface Session {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export interface Citation {
  label: string
  source_id: string
  title: string
  url: string
  publication_date: string | null
  source_type: string | null
  publisher: string | null
  snippet: string | null
}

export interface EvidenceItem {
  evidence_id: string
  source_id: string
  source_type: string
  title: string
  url: string
  publication_date: string | null
  publisher: string | null
  population: string | null
  intervention: string | null
  outcome: string | null
  key_claim: string
  claim_type: string | null
  applicability: string | null
  supports_question_dimensions: string[]
  safety_notes: string[]
  limitations: string[]
  uncertainty_notes: string[]
  evidence_strength: string
  source_priority: number
  extracted_entities: string[]
}

export interface AssistantResponse {
  status: AssistantStatus
  answer: string | null
  clarification_question: string | null
  abstention_class: string | null
  abstention_reason: string | null
  evidence_summary: string[]
  evidence_strength: EvidenceStrength | null
  limitations: string[]
  citations: Citation[]
  evidence_items: EvidenceItem[]
  last_literature_check_at: string | null
  /* present on reloaded assistant messages, used for local keys */
  run_id?: string
}

export type MessageRole = 'user' | 'assistant'

export interface BackendMessage {
  id: string
  session_id: string
  role: MessageRole
  content: string
  metadata_json: Record<string, unknown> | null
  created_at: string
}

export interface SendMessageResult {
  run_id: string
  response: AssistantResponse
}

export interface RunStartResult {
  run_id: string
}

export interface RunRecord {
  id: string
  session_id: string
  message_id: string | null
  status: string
  iteration_count: number
  final_status: string | null
  final_response_json: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface RunStep {
  id: string
  run_id: string
  node_name: string
  step_order: number
  status: string
  input_json: Record<string, unknown> | null
  output_json: Record<string, unknown> | null
  created_at: string
}

export interface RunProgressEvent {
  type: 'status' | 'progress' | 'final' | 'error'
  timestamp: string
  message?: string
  node_name?: string
  step_order?: number
  agent_type?: string
  connector?: string
  response?: AssistantResponse & { run_id?: string }
}

export interface Health {
  status: string
  service: string
  llm_mode: string
}
