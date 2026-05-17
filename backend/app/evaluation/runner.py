from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.main import create_app
from app.schemas.common import AssistantResponse


class BenchmarkCase(BaseModel):
    case_id: str
    question: str
    expected_status: str
    expected_abstention_class: str | None = None
    expected_substrings: list[str] = Field(default_factory=list)
    expected_min_citations: int = 0
    expected_min_evidence_items: int = 0


class CaseResult(BaseModel):
    case_id: str
    passed: bool
    expected_status: str
    actual_status: str
    expected_abstention_class: str | None = None
    actual_abstention_class: str | None = None
    citation_count: int = 0
    evidence_item_count: int = 0
    missing_substrings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    benchmark_path: str
    generated_at: datetime
    total_cases: int
    passed_cases: int
    results: list[CaseResult]


def load_benchmark(path: str | Path) -> list[BenchmarkCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [BenchmarkCase.model_validate(case) for case in payload.get("cases", [])]


def compare_case(case: BenchmarkCase, response: AssistantResponse) -> CaseResult:
    notes: list[str] = []
    missing_substrings: list[str] = []
    actual_status = response.status
    actual_abstention_class = response.abstention_class
    answer_text = " ".join(
        part
        for part in [
            response.answer or "",
            response.clarification_question or "",
            response.abstention_reason or "",
            " ".join(response.evidence_summary),
        ]
        if part
    ).lower()

    if actual_status != case.expected_status:
        notes.append(f"Expected status {case.expected_status}, got {actual_status}.")
    if case.expected_abstention_class and actual_abstention_class != case.expected_abstention_class:
        notes.append(
            f"Expected abstention class {case.expected_abstention_class}, got {actual_abstention_class}."
        )

    for substring in case.expected_substrings:
        if substring.lower() not in answer_text:
            missing_substrings.append(substring)

    citation_count = len(response.citations)
    evidence_item_count = len(response.evidence_items)
    if citation_count < case.expected_min_citations:
        notes.append(f"Expected at least {case.expected_min_citations} citations, got {citation_count}.")
    if evidence_item_count < case.expected_min_evidence_items:
        notes.append(
            f"Expected at least {case.expected_min_evidence_items} evidence items, got {evidence_item_count}."
        )

    if missing_substrings:
        notes.append("Expected substrings missing from the response payload.")

    passed = not notes
    return CaseResult(
        case_id=case.case_id,
        passed=passed,
        expected_status=case.expected_status,
        actual_status=actual_status,
        expected_abstention_class=case.expected_abstention_class,
        actual_abstention_class=actual_abstention_class,
        citation_count=citation_count,
        evidence_item_count=evidence_item_count,
        missing_substrings=missing_substrings,
        notes=notes,
    )


def run_benchmark(path: str | Path) -> EvaluationReport:
    benchmark_cases = load_benchmark(path)
    results: list[CaseResult] = []

    with TestClient(create_app()) as client:
        for case in benchmark_cases:
            session = client.post("/api/sessions", json={"title": case.case_id})
            session.raise_for_status()
            session_id = session.json()["id"]

            response = client.post(
                f"/api/sessions/{session_id}/messages",
                json={"role": "user", "content": case.question},
            )
            response.raise_for_status()
            payload = response.json()
            assistant_response = AssistantResponse.model_validate(payload["response"])
            results.append(compare_case(case, assistant_response))

    return EvaluationReport(
        benchmark_path=str(path),
        generated_at=datetime.now(UTC),
        total_cases=len(results),
        passed_cases=sum(1 for result in results if result.passed),
        results=results,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Chiron benchmark harness.")
    parser.add_argument(
        "--benchmark",
        default=str(Path(__file__).resolve().parents[3] / "eval" / "benchmark.json"),
        help="Path to the benchmark JSON file.",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[3] / "eval" / "reports" / "latest.json"),
        help="Path to write the JSON report.",
    )
    args = parser.parse_args()

    report = run_benchmark(args.benchmark)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "benchmark_path": report.benchmark_path,
                "passed_cases": report.passed_cases,
                "total_cases": report.total_cases,
                "output": str(output_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
