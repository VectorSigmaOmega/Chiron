# PRD: Chiron

## 1. Overview

### Problem
Medical professionals need access to current, trustworthy medical information, but cannot rely on general-purpose chatbots that may hallucinate, omit uncertainty, or present unsupported claims with confidence.

### Product Statement
Build an open-domain medical evidence assistant that accepts arbitrary medical questions in natural language and returns either:

- a grounded answer composed only from trusted evidence, with explicit citations and dates, or
- a structured abstention when the system cannot support a safe answer.

### Core Product Contract
The input space is open-ended. A doctor may ask any medical question. The output space is constrained:

- answer only from supported evidence
- ask for clarification when the query is underspecified
- abstain when the evidence is insufficient, conflicting, outdated, or outside supported coverage

## 2. Goals

- Accept open-ended medical questions without relying on a closed set of fixed query types.
- Retrieve evidence from trusted medical and regulatory sources.
- Synthesize answers only from retrieved evidence.
- Show citations, dates, and limitations clearly.
- Refuse safely when a grounded answer cannot be produced.

## 3. Non-Goals

- Autonomous diagnosis or treatment without evidence support.
- Replacing physician judgment.
- Full production clinical decision support.
- EHR integration in the MVP.
- Image-based diagnosis in the MVP.
- Alternative medicine coverage in the MVP, including Ayurveda and homeopathy.

## 4. Users

- Primary: doctors, residents, pharmacists, clinical researchers, medical affairs teams
- Secondary: students and internal evaluators

## 5. Scope

### In Scope

- Open-domain medical questions in free text
- Literature search and evidence synthesis
- Drug, disease, symptom, treatment, side-effect, trial, and study questions
- Clarification for ambiguous or unsafe-to-answer prompts
- Structured abstention

### Out of Scope for MVP

- Personalized patient-specific decision support beyond provided prompt context
- Institution-specific protocol lookup unless sources are explicitly integrated
- Alternative medicine
- Persistent longitudinal case management across sessions

## 6. Product Principles

- Evidence first: no load-bearing claim without source support
- Transparency over fluency: show uncertainty and provenance
- Open-domain input, bounded output
- Abstention is a success case when warranted
- Retrieval quality matters more than eloquence

## 7. User Stories

- As a doctor, I want to ask a medical question in natural language and get a concise, cited answer.
- As a doctor, I want to know when evidence is weak, conflicting, or outdated.
- As a doctor, I want the system to say it cannot answer rather than fabricate.
- As an evaluator, I want to inspect the source trail behind the answer.

## 8. Functional Requirements

### FR1. Open-Domain Query Intake
The system must accept arbitrary medical questions in natural language.

### FR2. Query Understanding
The system must extract relevant medical entities and constraints when present, including:

- diseases and conditions
- drugs and interventions
- symptoms and findings
- population constraints
- outcomes of interest
- recency language such as "latest" or "current"

### FR3. Clarification
The system must ask a clarifying question when the prompt is too ambiguous to answer safely.

### FR4. Dynamic Evidence Planning
The system must choose a retrieval plan based on the information need instead of routing only through fixed intent pipelines.

### FR5. Trusted Source Retrieval
The system must retrieve documents from supported medical and regulatory sources and preserve provenance metadata.

### FR6. Evidence Extraction
The system must convert retrieved items into structured evidence objects or claims with source attribution.

### FR7. Grounded Synthesis
The system must generate answers only from retrieved evidence.

### FR8. Citation Binding
Each substantive claim in the final answer must map to one or more supporting sources.

### FR9. Structured Response
Each result must indicate one of:

- answered
- needs clarification
- abstained

### FR10. Auditability
The system must preserve enough trace data to inspect:

- user query
- parsed query
- retrieval plan
- sources used
- extracted evidence
- final response

### FR11. Session-Scoped Context Handling
The system must support short multi-turn interactions within a single conversation thread, including:

- clarification questions
- user-provided follow-up constraints
- re-answering based on newly supplied context

This does not require long-term cross-session memory or persistent case management in the MVP.

## 9. Response Contract

### Answered Response
Must include:

- direct answer
- evidence summary
- evidence quality or strength indicator
- citations
- source dates
- limitations or uncertainty note

### Clarification Response
Must include:

- the missing or ambiguous dimension
- a focused follow-up question

### Abstained Response
Must include:

- abstention reason
- why answering would be unsafe or unsupported
- suggested next step when appropriate

## 10. Source Policy

Preferred source categories:

- clinical guidelines
- systematic reviews and meta-analyses
- randomized controlled trials
- observational studies
- regulatory and label sources for drug safety and approvals
- trial registries

The system should rank evidence by authority, study type, recency, and applicability rather than journal prestige alone.

## 11. MVP Definition

### MVP Objective
Demonstrate that an open-domain medical question can be handled through dynamic evidence retrieval, grounded synthesis, and safe abstention.

### MVP Must Include

- one general medical evidence agent
- a deployable backend scaffold with agent and connector interfaces
- mock connectors for end-to-end orchestration before broad real-source work
- a small set of trusted real source integrations
- clarification handling
- structured abstention
- citation-grounded answers
- an evaluation benchmark and scoring method

### MVP Does Not Need

- polished production UX
- account systems
- exhaustive source coverage
- persistent cross-session memory

## 12. Suggested MVP Source Set

- PubMed
- ClinicalTrials.gov
- DailyMed if integration proves straightforward in the first pass
- one narrow guideline source or curated guideline fixture layer for the demo
- optional stretch source: openFDA or Drugs@FDA for additional drug-safety signals
- deferred source expansions: Europe PMC, PMC open-access full text, broader guideline coverage

## 13. Workflow

1. Accept user query.
2. Parse entities, constraints, and ambiguity.
3. Ask for clarification if required.
4. Build retrieval plan.
5. Search trusted sources.
6. Extract structured evidence.
7. Rank evidence by quality and relevance.
8. Produce grounded answer or structured abstention.
9. Present citations, dates, and limitations.

## 14. Non-Functional Requirements

- Favor factual grounding over completeness.
- Preserve provenance visibly.
- Degrade safely when coverage is limited.
- Support extension to additional sources without redesigning the core contract.

## 15. Success Metrics

- citation coverage
- unsupported-claim rate
- appropriate abstention rate
- freshness compliance on recency-sensitive prompts
- evaluator-rated usefulness

## 16. Risks

- fluent but weak synthesis
- false confidence under conflicting evidence
- poor handling of ambiguous prompts
- limited access to full text
- demo collapsing into generic RAG without visible verification

## 17. Deliverables

- main PRD
- safety and evaluation specification
- architecture document
- implementation plan
- benchmark set
- working MVP

## 18. Working Decisions For Architecture

- The product will use a chat interface with conversation history, while the retrieval agent can remain stateless per invocation aside from receiving session context.
- The MVP will support session-scoped multi-turn clarification and follow-up, but not persistent longitudinal memory across sessions.
- The MVP may accept user-provided patient context as constraints, but it will remain an evidence assistant rather than a personalized clinical decision engine.
- The MVP should prove the orchestration contract with a deployable backend scaffold first, then add real connectors incrementally.
- The initial real source priority is PubMed, ClinicalTrials.gov, and a narrow drug-safety/guideline layer rather than broad scraping coverage.
- The default scope is global evidence-based medicine; geography-specific weighting is a future extension.
- The MVP will use a lightweight evidence-strength scale rather than a full formal grading framework.
