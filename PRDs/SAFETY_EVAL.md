# Safety and Evaluation Specification

## 1. Overview

The central requirement of `Chiron` is calibrated trustworthiness. The system must not only answer questions from evidence, but also refuse or narrow scope when the evidence does not support a safe answer.

## 2. Safety Objective

The system must never present unsupported medical claims as established fact. When a safe grounded answer cannot be produced, it must ask for clarification or abstain.

## 3. Abstention Taxonomy

The system should use structured abstentions rather than a generic "I don't know."

### A1. Insufficient Evidence
Relevant evidence cannot be found or is too sparse to support a useful answer.

### A2. Conflicting Evidence
Credible sources disagree in a way that cannot be resolved confidently.

### A3. Missing Clinical Context
The question is answerable in principle but unsafe without more context.

Examples:

- age
- pregnancy status
- setting
- comorbidities
- concurrent medications

### A4. Coverage Gap
The question is outside the supported source or task coverage of the MVP.

Examples:

- alternative medicine
- image interpretation
- institution-specific protocol lookup

### A5. Recency Gap
The user asks for the latest evidence, but the system cannot justify that its evidence base is current enough.

### A6. Ambiguous Query
The prompt is too broad or underspecified and should trigger clarification before retrieval.

## 4. Required Abstention Output

Each abstention should include:

- refusal class
- short explanation
- what is missing or limiting
- recommended next step

## 5. Clarification Policy

The system should ask a follow-up question instead of answering when:

- multiple materially different interpretations are possible
- the population or setting materially changes the answer
- a safe answer depends on missing case context

## 6. Evidence Quality Policy

Use a simple operational grading policy for the MVP.

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

This grading supports ranking and communication. It does not replace full critical appraisal.

## 7. Evaluation Principles

- Evaluate trustworthiness, not writing style.
- Evaluate abstention quality as seriously as answer quality.
- Use rubric-based scoring rather than exact-match output checks.
- Include recency-sensitive and adversarial prompts.

## 8. Benchmark Design

Create a benchmark set across these strata:

- direct lookup
- multi-source synthesis
- drug safety
- differential-style knowledge questions
- latest-evidence questions
- should-refuse prompts
- adversarial nonsense or fabricated entities
- ambiguous prompts requiring clarification

Recommended size for the assignment:

- 40 to 60 questions

## 9. Evaluation Rubric

Score each result on:

- grounding
- citation quality
- answer correctness
- uncertainty handling
- abstention correctness
- clarification correctness
- freshness awareness

## 10. Failure Modes To Test

- fabricated citation
- correct citation attached to the wrong claim
- outdated evidence presented as current
- overconfident synthesis from weak evidence
- failure to ask for missing context
- failure to abstain on impossible or unsupported prompts
- susceptibility to made-up drugs, diseases, or journals

## 11. Acceptance Criteria

- No fabricated citations in the benchmark set
- No materially unsupported answer claims
- High abstention correctness on deliberately unanswerable or unsafe prompts
- Explicit date awareness on recency-sensitive prompts
- Clear preference for stronger evidence when multiple sources are available

## 12. Observability Requirements

For each benchmark run, store:

- input question
- parsed query structure
- retrieval plan
- retrieved sources
- extracted evidence
- final response
- evaluator score

## 13. Reviewer-Facing Output

The demo should include an evaluation artifact showing:

- question
- expected behavior
- actual behavior
- evidence used
- pass or fail notes

This will likely be more convincing to engineers than a purely conversational demo.
