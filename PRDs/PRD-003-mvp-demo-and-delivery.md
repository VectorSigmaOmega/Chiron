# PRD-003: MVP Demo and Delivery

## 1. Purpose

This PRD defines what to build for the assignment. The goal is not to solve open-domain medical intelligence in full. The goal is to demonstrate sound engineering judgment through a credible, inspectable MVP.

## 2. Demo Thesis

The MVP should prove four things:

- arbitrary medical questions can be accepted
- trusted evidence can be retrieved dynamically
- answers can be generated with explicit citations
- the system refuses when it should

## 3. Recommended MVP Scope

### Build

- a single-question medical evidence assistant
- dynamic retrieval planning over a small set of trusted sources
- grounded answer generation with citations
- structured abstention and clarification
- a benchmark and evaluation harness

### Do Not Build

- a polished production UI
- long-term user accounts
- complete clinical decision support
- full conversational memory
- broad source integration for every publisher

## 4. Suggested Source Set For MVP

Strong candidate source mix:

- PubMed
- Europe PMC
- ClinicalTrials.gov
- DailyMed
- one or more public guideline sources where access is practical

This is enough to demonstrate the workflow without overpromising source completeness.

## 5. System Components

### C1. Query Intake
Simple text box or CLI-style input for the medical question.

### C2. Planner
A general agent that determines:

- whether clarification is needed
- which source connectors to call
- what evidence types are required

### C3. Retrieval Layer
Adapters for trusted sources that return normalized metadata and document content where available.

### C4. Evidence Extractor
Transforms retrieved items into structured evidence statements with provenance.

### C5. Answer Composer
Produces the final grounded summary, citations, and limitation notes.

### C6. Verifier
Checks that each substantive claim is backed by retrieved evidence and triggers abstention if grounding is inadequate.

### C7. Evaluation Harness
Runs a benchmark set and records pass or fail outcomes.

## 6. User Experience Requirements

The interface can be minimal, but each result must clearly show:

- answer status: answered, needs clarification, or abstained
- answer text
- evidence strength
- citations
- dates
- caveats

For abstentions, show:

- abstention class
- reason
- recommended next step

## 7. Technical Priorities

Priority order:

1. retrieval correctness
2. citation grounding
3. abstention behavior
4. evaluator visibility
5. UI polish

If time is constrained, cut polish before cutting evaluation and provenance.

## 8. Engineering Deliverables

- source adapters for selected evidence sources
- normalization schema for retrieved evidence
- planner and verifier loop
- final response schema
- benchmark set
- evaluation script or notebook
- short architecture document or diagram

## 9. Demo Script

The final presentation should show at least:

- one straightforward answerable question
- one multi-source question
- one recency-sensitive question
- one ambiguous question that triggers clarification
- one impossible or unsafe question that triggers abstention

This demonstrates both capability and restraint.

## 10. Success Criteria

The MVP is successful if reviewers can see that:

- the team understood the real problem
- the system does not bluff
- the system can inspect sources rather than just paraphrase priors
- the architecture can scale to more connectors and tighter validation

## 11. Risks And Mitigations

### Risk: Overengineering
Mitigation: keep the source set small and the contract strict.

### Risk: Demo looks like generic RAG
Mitigation: foreground abstention, evidence ranking, and evaluation traces.

### Risk: Source access limitations
Mitigation: use public APIs and open-access full text where possible.

### Risk: Reviewers challenge completeness
Mitigation: state clearly that the MVP demonstrates a safe open-domain evidence workflow, not total medical coverage.

## 12. Recommended Submission Package

- PRD set
- architecture diagram
- source policy note
- benchmark questions with expected behavior
- working MVP
- short demo walkthrough

This combination is more convincing than code alone.
