# PRD-002: Safety, Abstention, and Evaluation

## 1. Overview

The defining requirement of this system is not broad coverage alone. It is calibrated trustworthiness. A strong answer is one that is both grounded and honest about its limits.

This document defines:

- refusal behavior
- evidence quality policy
- evaluation strategy
- acceptance thresholds for a credible demo

## 2. Safety Objective

The system must never present unsupported medical claims as established fact. When the evidence base cannot support a safe answer, the system must abstain clearly and specifically.

## 3. Abstention Taxonomy

The system should not use a generic "I don't know" response. It should classify abstentions into meaningful types.

### A1. Insufficient Evidence
Use when relevant evidence cannot be found or is too sparse to support a useful answer.

### A2. Conflicting Evidence
Use when credible sources materially disagree and the system cannot resolve the conflict confidently.

### A3. Missing Clinical Context
Use when the question is answerable in principle but unsafe without more context.

Examples:

- age
- pregnancy status
- setting
- comorbidities
- current medications

### A4. Coverage Gap
Use when the question falls outside supported source coverage.

Examples:

- alternative medicine in the MVP
- image interpretation
- institution-specific protocol lookup

### A5. Recency Gap
Use when the user explicitly asks for the latest evidence but the system cannot verify that its sources are current enough for the claim.

### A6. Ambiguous Query
Use when the question is too broad or underspecified and should trigger clarification before retrieval.

## 4. Required Abstention Output

Every abstention should contain:

- refusal class
- one-sentence explanation
- missing information or limiting factor
- suggested next step

Example next steps:

- provide age and comorbidities
- narrow the clinical scenario
- review current specialty guidelines
- consult a human specialist for case-specific judgment

## 5. Evidence Quality Policy

The system should grade evidence using a simple operational policy for the MVP.

### High

- current guideline
- systematic review or meta-analysis
- strong regulatory source

### Moderate

- randomized controlled trial
- multiple consistent observational studies

### Low

- single observational study
- early or indirect evidence

### Excluded or Flagged

- preprints without peer review
- non-reputable sources
- uncited summaries

This grading is for communication and ranking, not as a substitute for formal evidence appraisal.

## 6. Evaluation Principles

- Evaluate trustworthiness, not style.
- Evaluate abstention quality as seriously as answer quality.
- Use rubric-based review, not exact string matching.
- Include adversarial and recency-sensitive questions.

## 7. Evaluation Set Design

Build a benchmark set with clinician-style prompts across multiple strata:

- direct lookup
- multi-source synthesis
- drug safety
- differential-style knowledge questions
- latest-evidence questions
- should-refuse questions
- adversarial nonsense or fabricated entities
- ambiguous queries requiring clarification

Recommended benchmark size for the assignment:

- 40 to 60 questions

## 8. Evaluation Rubric

Each answer should be scored on:

- grounding: are the claims supported by cited sources?
- citation quality: are the sources trusted and relevant?
- answer correctness: is the summary faithful to the evidence?
- uncertainty handling: are caveats and conflicts surfaced?
- abstention correctness: did the system abstain when it should have?
- clarification correctness: did the system ask for more context when necessary?
- freshness: did the system address recency-sensitive wording appropriately?

## 9. Core Failure Modes To Test

- fabricated citation
- real citation, wrong claim
- outdated evidence presented as current
- overconfident synthesis from weak evidence
- failure to ask for missing context
- failure to abstain on impossible or unsupported queries
- susceptibility to made-up drugs, diseases, or journals

## 10. Acceptance Criteria For A Strong MVP

- No fabricated citations in the benchmark set.
- No answer should contain a material unsupported claim.
- The system should abstain correctly on most deliberately unanswerable or unsafe prompts.
- Recency-sensitive prompts should show explicit date awareness.
- Answers should prefer higher-quality evidence when multiple sources are available.

## 11. Observability Requirements

For each benchmark run, store:

- input question
- interpreted query structure
- retrieval plan
- retrieved sources
- evidence excerpts or extracted claims
- final answer or abstention
- evaluator score

This turns the take-home from a black-box demo into an inspectable engineering artifact.

## 12. Reviewer-Facing Deliverable

The demo should include an evaluation table showing:

- question
- expected behavior
- actual behavior
- evidence sources used
- pass or fail notes

This is likely more impressive to engineers than a purely conversational demo.
