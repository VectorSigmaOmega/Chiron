# PRD-001: Open-Domain Medical Evidence Assistant

## 1. Overview

### Problem
Medical professionals need access to current, trustworthy medical information, but cannot rely on general-purpose chatbots that may hallucinate, omit uncertainty, or present unsupported claims with unwarranted confidence.

### Product Statement
Build an open-domain medical evidence assistant that accepts arbitrary medical questions in natural language and returns either:

- a grounded answer composed only from trusted evidence, with explicit citations and dates, or
- a structured abstention when the system cannot support a safe answer.

### Why This Matters
The problem is not "generate medical text." The problem is "support evidence-based clinical information retrieval and synthesis with an honesty floor."

## 2. Goals

- Accept open-ended medical questions without predefining a closed set of query types.
- Retrieve evidence from trusted medical and regulatory sources.
- Synthesize answers only from retrieved evidence.
- Surface uncertainty, conflicting evidence, and missing context explicitly.
- Abstain when the evidence base is insufficient, unsafe, outdated, or outside supported coverage.

## 3. Non-Goals

- Autonomous diagnosis or treatment recommendation without source-backed evidence.
- Replacing physician judgment.
- Supporting every medical source on day one.
- Covering Ayurveda, homeopathy, or other alternative systems in the MVP.
- Providing patient-specific clinical decision support beyond the supplied question context.

## 4. Target Users

- Primary users: doctors, residents, clinical researchers, pharmacists, medical affairs professionals.
- Secondary users: medical students and internal pharma teams exploring evidence.

## 5. Scope

### In Scope

- Open-domain medical questions in free text.
- Literature search and synthesis across trusted sources.
- Drug, disease, symptom, treatment, side-effect, trial, and evidence-summary questions.
- Clarification when the user question is underspecified.
- Structured abstention when support is inadequate.

### Out of Scope for MVP

- Image-based diagnosis.
- EHR integration.
- Real-time bedside decision support.
- Personalized dosing engines.
- Non-evidence-based medicine content.

## 6. Product Principles

- Evidence first: no load-bearing claim without source support.
- Transparency over fluency: citation quality and uncertainty matter more than polished prose.
- Open-domain input, bounded output: any question may be asked, but the system only answers within supported evidence.
- Safe abstention is a success case, not a failure case.

## 7. User Stories

- As a doctor, I want to ask a medical question in natural language and quickly receive a cited, concise answer.
- As a doctor, I want to know when evidence is weak, conflicting, or outdated.
- As a doctor, I want the system to say it cannot answer rather than fabricate.
- As a doctor, I want to inspect the underlying sources and publication dates.
- As an evaluator, I want to see why a specific answer was produced and which sources were used.

## 8. Functional Requirements

### FR1. Open-Domain Question Intake
The system must accept arbitrary medical questions in natural language.

### FR2. Query Understanding
The system must extract medical entities and constraints when present, including:

- diseases and conditions
- drugs and interventions
- symptoms and findings
- population constraints
- outcomes of interest
- recency language such as "latest" or "current"

### FR3. Clarification
The system must ask a clarifying question when the query is too ambiguous to answer safely.

Examples:

- "Best treatment for pneumonia" without population or setting.
- "Is this drug safe?" without drug identity or context.

### FR4. Evidence Planning
The system must dynamically choose an evidence retrieval strategy based on the information need instead of using fixed intent pipelines.

### FR5. Source Retrieval
The system must retrieve documents from trusted medical and regulatory sources and preserve provenance metadata.

### FR6. Grounded Synthesis
The system must generate answers only from retrieved evidence objects and must not invent unsupported claims.

### FR7. Citation Binding
Each substantive claim in the final answer must map to one or more retrieved sources.

### FR8. Evidence Transparency
The system must display:

- source title
- source type
- publication or update date
- link or identifier

### FR9. Abstention
The system must return a structured refusal when evidence is insufficient, contradictory, stale, or outside supported coverage.

### FR10. Auditability
The system must retain the reasoning trace at the level of:

- query
- retrieval plan
- sources used
- evidence snippets or extracted claims
- final answer or abstention reason

## 9. Response Contract

Each answer must contain:

- direct answer
- evidence summary
- evidence quality or strength indicator
- inline citations or numbered citations
- source dates
- limitations or uncertainty note

Each abstention must contain:

- abstention reason
- what is missing or unsafe
- suggested next step, if appropriate

## 10. Source Policy

Preferred source categories:

- clinical guidelines
- systematic reviews and meta-analyses
- randomized controlled trials
- observational studies
- regulatory and label sources for drug safety and approvals
- trial registries for ongoing or recent studies

The system should rank evidence by source authority, evidence type, recency, and clinical applicability rather than journal prestige alone.

## 11. Proposed Workflow

1. Accept the user query.
2. Parse entities, constraints, and ambiguity.
3. Ask a clarifying question if needed.
4. Build a retrieval plan.
5. Search trusted sources.
6. Extract structured evidence claims.
7. Rank evidence by quality and relevance.
8. Generate either a grounded answer or a structured abstention.
9. Present citations, dates, and limitations.

## 12. Non-Functional Requirements

- Accuracy must be favored over response verbosity.
- Provenance must be visible to the user.
- The system must degrade safely when source coverage is limited.
- The architecture must support adding new trusted sources without redesigning the core workflow.

## 13. Success Metrics

- Citation coverage: percentage of answer claims with explicit supporting citations.
- Unsupported-claim rate: percentage of answers containing ungrounded statements.
- Appropriate abstention rate on unanswerable or unsafe queries.
- Freshness compliance on recency-sensitive questions.
- Evaluator-rated usefulness for grounded answers.

## 14. Risks

- Fluent unsupported synthesis despite retrieval.
- False confidence when evidence is weak or conflicting.
- Retrieval overfitting to high-profile but clinically lower-priority sources.
- Inability to access full text for some journals.
- Ambiguous questions being answered too early without clarification.

## 15. Open Questions

- Which geography-specific sources, if any, should be added after the MVP?
- How far should patient context be supported in the first version?
- Should evidence strength use a lightweight internal scale or a formal framework such as GRADE?
