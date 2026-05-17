import type {
  ChatSession,
  AssistantResponse,
  EvidenceItem,
  TraceStep,
} from "./types";

// Realistic clinician-style examples. Every state the brief calls out is
// represented here so the UI can be exercised without a backend.

const isoNow = "2026-05-14T10:24:00Z";
const isoYesterday = "2026-05-13T16:02:00Z";
const isoThreeDaysAgo = "2026-05-11T09:15:00Z";

/* ---------- Evidence: drug-resistant TB in pregnancy ---------- */

const tbEvidence: EvidenceItem[] = [
  {
    evidence_id: "ev_001",
    source_id: "src_who_2024",
    source_type: "guideline",
    title:
      "WHO consolidated guidelines on tuberculosis. Module 4: Treatment — drug-resistant tuberculosis treatment, 2024 update",
    url: "https://www.who.int/publications/i/item/9789240007048",
    publication_date: "2024-08-15",
    publisher: "World Health Organization",
    population: "Adults with RR/MDR-TB, including pregnant individuals",
    intervention: "BPaL / BPaLM regimens",
    outcome:
      "All-oral 6-month regimen recommended over longer injectable-containing regimens",
    key_claim:
      "BPaLM is the preferred regimen for rifampicin-resistant TB; in pregnancy, pretomanid use requires individualized risk-benefit assessment due to limited human reproductive data.",
    safety_notes: [
      "Pretomanid: reproductive toxicity observed in animal studies; human data limited.",
      "Linezolid: monitor for myelosuppression and peripheral neuropathy across pregnancy.",
      "Bedaquiline: QT prolongation, monitor with serial ECGs.",
    ],
    limitations: [
      "Pregnancy-specific outcome data drawn from observational cohorts.",
    ],
    evidence_strength: "high",
  },
  {
    evidence_id: "ev_002",
    source_id: "src_lancet_2025",
    source_type: "review",
    title:
      "Management of multidrug-resistant tuberculosis in pregnancy: a systematic review",
    url: "https://www.thelancet.com/journals/lanres/article/PIIS2213-2600(25)00040-9/fulltext",
    publication_date: "2025-03-04",
    publisher: "The Lancet Respiratory Medicine",
    population:
      "456 pregnancies across 14 cohort studies, 2015–2024",
    intervention: "All-oral MDR-TB regimens including bedaquiline",
    outcome:
      "Favorable treatment outcomes in 78% (95% CI 71–84); no signal of major congenital anomaly attributable to bedaquiline exposure.",
    key_claim:
      "Bedaquiline-containing all-oral regimens in pregnancy are associated with favorable treatment outcomes and no detected increase in congenital anomalies; pretomanid data remain too sparse to recommend routine use.",
    safety_notes: [
      "Low birthweight reported in 22% of exposed pregnancies; multifactorial.",
      "No congenital anomaly pattern attributable to bedaquiline detected.",
    ],
    limitations: [
      "Observational data only; confounding by indication is likely.",
      "Pretomanid n=18, insufficient to characterize fetal safety.",
    ],
    evidence_strength: "moderate",
  },
  {
    evidence_id: "ev_003",
    source_id: "src_ct_001",
    source_type: "trial",
    title:
      "Pregnancy outcomes among women treated with bedaquiline-containing regimens for MDR-TB (IMPAACT 2026)",
    url: "https://clinicaltrials.gov/study/NCT05012345",
    publication_date: "2025-11-20",
    publisher: "ClinicalTrials.gov",
    population: "210 enrolled, 184 completed follow-up",
    intervention: "Bedaquiline + linezolid + clofazimine",
    outcome:
      "Treatment success 81%; preterm birth 12%; no major congenital anomaly attributable to study drugs.",
    key_claim:
      "Prospective trial data support the safety and effectiveness of bedaquiline-based regimens during pregnancy when pretomanid is avoided.",
    safety_notes: [
      "Two cases of optic neuropathy attributed to linezolid; reversible on dose reduction.",
    ],
    limitations: ["Single-arm; not powered for rare anomaly outcomes."],
    evidence_strength: "moderate",
  },
  {
    evidence_id: "ev_004",
    source_id: "src_dailymed_pretomanid",
    source_type: "label",
    title: "PRETOMANID — full prescribing information",
    url: "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=pretomanid",
    publication_date: "2024-12-10",
    publisher: "DailyMed / FDA",
    population: "Adults",
    intervention: "Pretomanid",
    outcome:
      "Pregnancy category: limited human data; testicular and reproductive toxicity in animals.",
    key_claim:
      "Pretomanid label notes insufficient human pregnancy data and reproductive toxicity signals in animals; counseling and contraception recommended.",
    safety_notes: [
      "Hepatotoxicity warnings; monitor LFTs.",
      "Reproductive toxicity in animal models.",
    ],
    limitations: [],
    evidence_strength: "high",
  },
];

const tbAnswer = `Current guidance favors an **all-oral, bedaquiline-containing regimen** for rifampicin-resistant TB in pregnancy, with **pretomanid avoided** in most cases due to insufficient human reproductive data.[1][4]

The 2024 WHO update positions BPaLM (bedaquiline, pretomanid, linezolid, moxifloxacin) as the preferred 6-month regimen for non-pregnant adults. In pregnancy, recent systematic and prospective data support bedaquiline + linezolid + a companion drug such as clofazimine or moxifloxacin, while pretomanid use should be reserved for individualized risk-benefit decisions where alternatives have failed.[2][3]

**Safety priorities across pregnancy**: serial ECG monitoring for QT prolongation on bedaquiline; monthly CBC and neurological exams on linezolid; LFTs at baseline and monthly; pyridoxine supplementation; and coordinated maternal-fetal medicine follow-up. Reported treatment success in observational cohorts is **~78%**, with no detected pattern of congenital anomaly attributable to bedaquiline.[2][3]`;

const tbResponse: AssistantResponse = {
  status: "answered",
  answer: tbAnswer,
  clarification_question: null,
  abstention_class: null,
  abstention_reason: null,
  evidence_summary: [
    "WHO 2024 recommends all-oral 6-month regimens for RR/MDR-TB; pretomanid use in pregnancy requires individualized assessment.",
    "Systematic review of 456 pregnancies: 78% favorable outcomes on bedaquiline-containing regimens; no anomaly signal attributable to bedaquiline.",
    "Prospective IMPAACT 2026 data support bedaquiline-based regimens; pretomanid n=18 across the literature, insufficient to recommend.",
    "Pretomanid label notes insufficient human data and animal reproductive toxicity.",
  ],
  evidence_strength: "moderate",
  limitations: [
    "Pregnancy-specific data remain dominated by observational cohorts.",
    "Pretomanid pregnancy data are too sparse for routine recommendation.",
    "Recommendation does not address breastfeeding, addressed separately in WHO Module 4.",
  ],
  citations: [
    {
      label: "1",
      source_id: "src_who_2024",
      title:
        "WHO consolidated guidelines on tuberculosis. Module 4: Treatment — drug-resistant tuberculosis, 2024 update",
      url: "https://www.who.int/publications/i/item/9789240007048",
      publication_date: "2024-08-15",
      source_type: "guideline",
      publisher: "World Health Organization",
    },
    {
      label: "2",
      source_id: "src_lancet_2025",
      title:
        "Management of multidrug-resistant tuberculosis in pregnancy: a systematic review",
      url: "https://www.thelancet.com/journals/lanres/article/PIIS2213-2600(25)00040-9/fulltext",
      publication_date: "2025-03-04",
      source_type: "review",
      publisher: "The Lancet Respiratory Medicine",
    },
    {
      label: "3",
      source_id: "src_ct_001",
      title:
        "Pregnancy outcomes among women treated with bedaquiline-containing regimens for MDR-TB (IMPAACT 2026)",
      url: "https://clinicaltrials.gov/study/NCT05012345",
      publication_date: "2025-11-20",
      source_type: "trial",
      publisher: "ClinicalTrials.gov",
    },
    {
      label: "4",
      source_id: "src_dailymed_pretomanid",
      title: "PRETOMANID — full prescribing information",
      url: "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=pretomanid",
      publication_date: "2024-12-10",
      source_type: "label",
      publisher: "DailyMed / FDA",
    },
  ],
  evidence_items: tbEvidence,
  last_literature_check_at: isoNow,
};

/* ---------- Clarification: ambiguous statin question ---------- */

const statinClarification: AssistantResponse = {
  status: "needs_clarification",
  answer: null,
  clarification_question:
    "Before I retrieve evidence, is this for **primary prevention** in someone without prior cardiovascular events, or **secondary prevention** after an established event? The risk benefit and target intensity differ substantially.",
  clarification_options: [
    "Primary prevention, no prior event",
    "Secondary prevention, established ASCVD",
    "Familial hypercholesterolemia",
    "Patient is intolerant to statins",
  ],
  abstention_class: null,
  abstention_reason: null,
  evidence_summary: [],
  evidence_strength: null,
  limitations: [],
  citations: [],
  evidence_items: [],
  last_literature_check_at: null,
};

/* ---------- Abstention: out-of-scope financial question ---------- */

const abstentionResponse: AssistantResponse = {
  status: "abstained",
  answer: null,
  clarification_question: null,
  abstention_class: "out_of_scope",
  abstention_reason:
    "This question is outside the medical evidence scope I am gated to answer. I retrieve from guideline, literature, drug safety, and trial registries; not insurance, billing, or coverage policy databases. A clinical decision support team or payer-facing resource would be a better fit.",
  evidence_summary: [],
  evidence_strength: null,
  limitations: [
    "Coverage and prior-authorization data are not in the indexed source set.",
    "Policy language varies by payer and region.",
  ],
  citations: [],
  evidence_items: [],
  last_literature_check_at: null,
};

/* ---------- Sessions ---------- */

export const mockSessions: ChatSession[] = [
  {
    id: "sess_tb",
    title: "Drug-resistant TB in pregnancy",
    created_at: isoNow,
    preview:
      "Latest treatment options for rifampicin-resistant TB during pregnancy",
    pinned: true,
    messages: [
      {
        id: "msg_u1",
        kind: "user",
        content:
          "What is the current evidence-based approach to drug-resistant TB in pregnancy, and what are the main safety considerations across pregnancy with the all-oral regimens?",
        created_at: "2026-05-14T10:23:30Z",
      },
      {
        id: "msg_a1",
        kind: "assistant",
        run_id: "run_001",
        created_at: isoNow,
        response: tbResponse,
      },
    ],
  },
  {
    id: "sess_statin",
    title: "Statin choice and intensity",
    created_at: isoYesterday,
    preview: "Which statin to start for a 58-year-old with elevated LDL",
    messages: [
      {
        id: "msg_u2",
        kind: "user",
        content:
          "Which statin should I start for a 58-year-old with LDL 162, BMI 29, no prior events?",
        created_at: isoYesterday,
      },
      {
        id: "msg_a2",
        kind: "assistant",
        run_id: "run_002",
        created_at: isoYesterday,
        response: statinClarification,
      },
    ],
  },
  {
    id: "sess_billing",
    title: "Prior authorization question",
    created_at: isoThreeDaysAgo,
    preview: "Coverage criteria for GLP-1 prescription",
    messages: [
      {
        id: "msg_u3",
        kind: "user",
        content:
          "What are the prior authorization criteria for semaglutide for weight management under most commercial plans in the US?",
        created_at: isoThreeDaysAgo,
      },
      {
        id: "msg_a3",
        kind: "assistant",
        run_id: "run_003",
        created_at: isoThreeDaysAgo,
        response: abstentionResponse,
      },
    ],
  },
];

export const examplePrompts = [
  {
    category: "Recent evidence",
    prompt:
      "What does the most recent evidence say about SGLT2 inhibitors in heart failure with preserved ejection fraction?",
  },
  {
    category: "Drug safety",
    prompt:
      "Sumatriptan in a patient with controlled hypertension and recent TIA, is it contraindicated?",
  },
  {
    category: "Guideline lookup",
    prompt:
      "First-line therapy for newly-diagnosed advanced non-small cell lung cancer with PD-L1 ≥50%.",
  },
  {
    category: "Multi-source synthesis",
    prompt:
      "Compare GLP-1 agonists for cardiovascular outcomes in type 2 diabetes with established ASCVD.",
  },
];

/* ---------- Trace template for the orchestration loop ---------- */

export const exampleTrace: TraceStep[] = [
  {
    id: "t1",
    label: "Parsing the question",
    agent: "parser",
    status: "done",
    started_at: isoNow,
    ended_at: isoNow,
  },
  {
    id: "t2",
    label: "Consulting clinical guidelines",
    agent: "guideline",
    status: "done",
    source_count: 3,
    started_at: isoNow,
  },
  {
    id: "t3",
    label: "Searching literature for recent evidence",
    agent: "literature",
    status: "running",
    source_count: 12,
    started_at: isoNow,
  },
  {
    id: "t4",
    label: "Checking drug safety records",
    agent: "drug_safety",
    status: "pending",
  },
  {
    id: "t5",
    label: "Synthesizing evidence",
    agent: "synthesizer",
    status: "pending",
  },
  {
    id: "t6",
    label: "Verifying claim support",
    agent: "verifier",
    status: "pending",
  },
];

export { tbResponse, statinClarification, abstentionResponse };
