# Semantic Layer

## Purpose

Chiron now treats medical meaning as an LLM responsibility rather than a code-level heuristic responsibility.

Code still owns:

- workflow control
- connector interfaces
- persistence
- tracing
- safety and policy guardrails

The semantic layer owns:

- query normalization
- intent understanding
- entity and constraint extraction
- evidence planning
- evidence coverage assessment
- evidence relevance assessment
- answer drafting
- verification support

## Two-Step Query Understanding

### Step 1. `NormalizedQuery`

The first LLM call cleans and interprets the raw user input.

Responsibilities:

- correct obvious spelling and phrasing issues
- expand shorthand or acronyms only when the intended meaning is highly likely
- preserve uncertainty when meaning is ambiguous
- use session context for follow-up turns
- decide whether the question is in scope
- decide whether clarification is needed before retrieval

Schema:

```python
class NormalizedQuery(BaseModel):
    raw_question: str
    normalized_question: str
    intent_summary: str
    scope: ScopeDecision
    needs_clarification: bool
    clarification_question: str | None
    ambiguity_notes: list[str]
    entities: list[QueryEntity]
    constraints: list[QueryConstraint]
    recency_focus: bool
    session_context_used: bool
    normalization_notes: list[NormalizationNote]
```

Supporting types:

```python
class QueryEntity(BaseModel):
    text: str
    normalized_text: str
    category: str
    role: str | None = None
    salience: str | None = None

class QueryConstraint(BaseModel):
    text: str
    normalized_text: str | None = None
    category: str
    importance: str = "primary"

class ScopeDecision(BaseModel):
    in_scope: bool = True
    reason: str | None = None

class NormalizationNote(BaseModel):
    original_text: str
    normalized_text: str
    reason: str | None = None
```

Important design rule:

- there are no hardcoded medical modifier lists
- there are no hardcoded accepted disease lists
- there is no special-case `pregnancy_status` field

### Step 2. `EvidencePlan`

The second LLM call plans how evidence should be gathered.

Responsibilities:

- define the primary answer goal
- break the question into useful subquestions
- decide which retrieval lanes are necessary
- generate source-facing retrieval specs per lane

Schema:

```python
class EvidencePlan(BaseModel):
    normalized_question: str
    primary_goal: str
    answer_strategy: str
    subquestions: list[PlannedSubquestion]
    retrieval_specs: list[RetrievalSpec]
```

Supporting types:

```python
class PlannedSubquestion(BaseModel):
    question: str
    priority: str = "medium"
    success_criteria: str | None = None

class RetrievalSpec(BaseModel):
    spec_id: str
    lane: str
    objective: str
    rationale: str
    query_text: str
    source_query: str | None
    focus_terms: list[str]
    must_concepts: list[str]
    supporting_concepts: list[str]
    population_terms: list[str]
    intervention_terms: list[str]
    question_focus_terms: list[str]
    exclude_concepts: list[str]
    preferred_evidence_types: list[str]
    recency_years: int | None
    desired_result_count: int
    priority: str
    depends_on: list[str]
```

The allowed retrieval lanes are operational, not medical:

- `guideline`
- `literature`
- `trials`
- `drug_safety`

The planner may choose any combination of these lanes.

Current connector interpretation:

- `guideline` means guideline discovery plus accessible original-document extraction
- `literature` means PubMed discovery and literature retrieval
- `trials` means trial-registry retrieval
- `drug_safety` means label or safety-source retrieval

## Coverage Assessment

After retrieval, a third LLM call decides whether another retrieval pass is needed.

Schema:

```python
class EvidenceCoverageDecision(BaseModel):
    answerable_now: bool
    needs_follow_up: bool
    rationale: str
    remaining_gaps: list[str]
    follow_up_specs: list[RetrievalSpec]
```

This replaces hardcoded follow-up rules such as:

- “if safety words are present, add drug safety”
- “if recency is present, add trials”

Instead, the model decides whether more work is actually needed based on the evidence already retrieved.

## Evidence Assessment

Evidence is normalized into `EvidenceItem` objects first. Then the semantic layer assesses how each item should be used.

Schema:

```python
class EvidenceAssessment(BaseModel):
    evidence_id: str
    question_role: str | None = None
    claim_type: str | None = None
    applicability: str | None = None
    supports_question_dimensions: list[str]
    semantic_relevance: int
    include_in_answer: bool = True
    assessment_summary: str | None = None
```

Important design rule:

- these are open text fields, not a fixed medical ontology in code

## Session Context

Session context is now compact structured state rather than disease-specific slots.

Current stored context shape:

- `active_entities`
- `active_constraints`
- `active_terms`
- `last_question`
- `last_normalized_question`
- `last_intent_summary`
- `last_answer_status`
- `last_question_roles`

This context is used by step 1 normalization on follow-up turns.

## Non-Goals

This refactor does not make all connectors semantically perfect. It does:

- remove hardcoded medical meaning from query parsing and planning
- move evidence planning into the LLM semantic layer
- remove connector-side accepted-disease whitelists
- make source queries come from the planner rather than code heuristics

It does not yet:

- guarantee that every discovered guideline source is fetchable
- eliminate all source-format-specific parsing logic
- solve answer quality fully without further retrieval and synthesis tuning
