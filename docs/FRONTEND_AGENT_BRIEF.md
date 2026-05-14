# Frontend Agent Brief

## Purpose

This document is for the agent responsible for scaffolding the `Chiron` frontend.

The goal is not to implement the full product logic. The goal is to create a clean frontend foundation for a clinician-facing medical evidence assistant so that the UI can integrate with the backend later without major restructuring.

## Product Context

`Chiron` is an open-domain medical evidence assistant.

A medical professional asks a question in natural language. The system should then do one of three things:

- answer with grounded evidence and citations
- ask a clarifying question
- abstain when the evidence is insufficient, conflicting, outdated, or outside supported scope

The frontend should make those three outcomes obvious and easy to inspect.

## Frontend Objective

Scaffold a frontend application that is ready for:

- session-based chat
- evidence-first answer presentation
- citation and source inspection
- clarification loops
- abstention states

The frontend should feel serious, modern, and trustworthy, not like a generic chatbot demo.

## Recommended Stack

If the repository does not already contain a frontend, scaffold with:

- React
- TypeScript
- a separate `frontend/` app
- a styling system that supports strong design direction and reusable tokens

The exact data-fetching library and routing solution do not need to be over-optimized at scaffolding time.

## UX Principles

- The user experience should feel like a clinical research workspace, not a casual assistant.
- Answers should foreground citations, dates, and limitations.
- The assistant should not look overconfident when it is clarifying or abstaining.
- The UI should support long, detailed answers without becoming visually noisy.
- The default view should emphasize trust, traceability, and readability.

## Screens To Scaffold

### 1. Main Chat Workspace

This is the primary screen.

It should include:

- conversation/session list or placeholder sidebar
- active conversation pane
- message composer
- answer area that supports rich medical responses
- evidence or citation panel, drawer, or expandable section

This screen should be the central experience of the product.

### 2. Empty State

Before the first question is asked, the interface should show:

- product identity
- short explanation of what the system does
- example clinician-style prompts

This should guide the user toward realistic medical questions without overpromising.

### 3. Clarification State

When the backend asks for more context, the UI should display that as a meaningful workflow state, not as a failure.

The user should be able to:

- see what is missing
- respond naturally
- continue in the same conversation

### 4. Abstention State

When the system refuses to answer, the interface should show:

- clear reason
- what limitation caused the abstention
- suggested next step if available

This should feel intentional and trustworthy, not like an error page.

### 5. Evidence Inspection Surface

This can be a side panel, drawer, tabs, or inline expansion.

It should support:

- source title
- source type
- publication or update date
- external link
- evidence snippets or summary bullets

This is a core part of the product, not optional metadata.

### 6. Error / Retry State

The UI should handle operational failures cleanly:

- network failures
- temporary backend errors
- failed response loading

The user should be able to retry without losing the conversation context.

## Optional Screens

These are useful if time permits, but not required for the first scaffold:

- run-inspection or trace view for demos
- benchmark/evaluation viewer
- settings panel for model/source preferences

## Core UI Regions

The scaffold should anticipate these regions even if they are initially simple:

- app shell
- sidebar
- main message timeline
- composer/input area
- evidence panel
- response status indicator

## Conversation States To Support

The UI must be designed to represent at least these states:

- idle
- loading
- answered
- clarification needed
- abstained
- error

These states should be visually distinct.

## Message Types To Anticipate

The frontend should be prepared to render:

- user questions
- assistant answers
- assistant clarification prompts
- assistant abstention responses
- evidence summaries
- citations and limitations

The renderer should not assume every assistant message is a simple blob of text.

## Design Direction

The design should feel:

- clinical but not sterile
- intelligent but not flashy
- trustworthy without looking bureaucratic
- modern without looking like a generic AI app

Avoid:

- purple-on-white generic AI styling
- toy chatbot aesthetics
- excessive dashboard chrome
- burying citations below the fold

## Suggested Information Hierarchy

For a successful answer, the user should immediately see:

1. the answer
2. how strong the evidence is
3. where it came from
4. what the limitations are

For clarification:

1. what is missing
2. what the user should provide next

For abstention:

1. why the system is not answering
2. what boundary or evidence gap caused it
3. what the user can do next

## Integration Expectations

Do not hardcode backend routes in this brief.

The frontend should simply be prepared for a backend that returns structured assistant states and evidence metadata. The frontend scaffold should keep API integration isolated behind a client layer so routes and payload details can be adjusted later without rewriting the UI.

## Suggested Folder Shape

The scaffold should roughly support:

```text
frontend/
  src/
    app/
    components/
    features/
    lib/
    styles/
```

Suggested feature areas:

- `chat`
- `evidence`
- `sessions`
- `ui`

## What The Scaffolding Agent Should Deliver

- a bootable frontend app in `frontend/`
- a main chat workspace shell
- placeholders for conversation history and evidence panel
- reusable UI primitives for assistant states
- mock or stub data support so the interface can be developed before backend completion
- a structure that can absorb real backend integration later

## What The Scaffolding Agent Should Not Do Yet

- implement final backend integration details
- invent medical logic in the frontend
- overbuild settings, auth, or dashboards
- optimize for every edge case before the main chat experience exists

## Definition Of Done

The frontend scaffold is good enough when:

- the app starts locally
- the main workspace is present
- empty, loading, answer, clarification, abstention, and error states all have UI shells
- citations and evidence have a clear visual home
- the structure is clean enough for another agent or engineer to continue implementation without reworking the app foundation
