"""Schemas for the product-evaluation dataset and machine-readable results."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..models.schemas import (
    AuditIssueCode,
    ExplanationDepth,
    PreferredLanguage,
    ReportDepth,
    ReportSection,
)


class EvaluationDimension(str, Enum):
    CITATION_COVERAGE = "citation_coverage"
    NUMERIC_ACCURACY = "numeric_accuracy"
    SOURCE_FRESHNESS = "source_freshness"
    CONTRADICTION_HANDLING = "contradiction_handling"
    IMPORTANT_INFORMATION_COVERAGE = "important_information_coverage"
    READABILITY = "readability"
    PERSONALIZATION_CONSISTENCY = "personalization_consistency"
    MULTILINGUAL_CONSISTENCY = "multilingual_consistency"


class NumericExpectation(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    path: str = Field(min_length=1, max_length=500)
    expected: float
    relative_tolerance: float = Field(default=1e-6, ge=0, le=1)
    absolute_tolerance: float = Field(default=1e-9, ge=0)


class ImportantInformationExpectation(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    paths: list[str] = Field(min_length=1)
    mode: Literal["any", "all"] = "any"


class ContradictionExpectation(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    fact_paths: list[str] = Field(min_length=2)
    required_issue_code: AuditIssueCode = AuditIssueCode.CONFLICTING_SOURCES
    acknowledgement_paths: list[str] = Field(min_length=1)
    acknowledgement_terms: list[str] = Field(min_length=1)


class PresentationExpectation(BaseModel):
    personalized: bool = True
    section_order: list[ReportSection]
    explanation_depth: ExplanationDepth
    report_depth: ReportDepth
    highlighted_insight_codes: list[str] = Field(default_factory=list)
    highlighted_metric_keys: list[str] = Field(default_factory=list)
    industry_match: bool


class EvaluationCase(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    locale: PreferredLanguage
    report_overrides: dict[str, Any] = Field(default_factory=dict)
    report_path_overrides: dict[str, Any] = Field(default_factory=dict)
    personalization_group: str | None = Field(default=None, max_length=120)
    multilingual_group: str | None = Field(default=None, max_length=120)
    language_markers: list[str] = Field(default_factory=list)
    expected_presentation: PresentationExpectation | None = None


class EvaluationDataset(BaseModel):
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    thresholds: dict[EvaluationDimension, float]
    overall_threshold: float = Field(default=0.9, ge=0, le=1)
    maximum_regression: float = Field(default=0.02, ge=0, le=1)
    maximum_source_age_days: int = Field(default=30, ge=0, le=3650)
    base_report: dict[str, Any]
    numeric_expectations: list[NumericExpectation] = Field(default_factory=list)
    important_information: list[ImportantInformationExpectation] = Field(
        default_factory=list
    )
    contradictions: list[ContradictionExpectation] = Field(default_factory=list)
    readability_paths: list[str] = Field(min_length=1)
    cases: list[EvaluationCase] = Field(min_length=1)

    @field_validator("thresholds")
    @classmethod
    def thresholds_cover_every_dimension(cls, values):
        missing = set(EvaluationDimension) - set(values)
        if missing:
            names = ", ".join(sorted(item.value for item in missing))
            raise ValueError(f"missing thresholds: {names}")
        if any(value < 0 or value > 1 for value in values.values()):
            raise ValueError("thresholds must be between zero and one")
        return values

    @model_validator(mode="after")
    def case_ids_and_comparison_groups_are_valid(self):
        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("evaluation case ids must be unique")

        missing_presentations = [
            case.id
            for case in self.cases
            if case.personalization_group and case.expected_presentation is None
        ]
        if missing_presentations:
            raise ValueError(
                "personalization cases require expected_presentation: "
                + ", ".join(missing_presentations)
            )

        missing_markers = [
            case.id
            for case in self.cases
            if case.multilingual_group and not case.language_markers
        ]
        if missing_markers:
            raise ValueError(
                "multilingual cases require language_markers: "
                + ", ".join(missing_markers)
            )

        for attribute in ("personalization_group", "multilingual_group"):
            groups: dict[str, list[EvaluationCase]] = {}
            for case in self.cases:
                group = getattr(case, attribute)
                if group:
                    groups.setdefault(group, []).append(case)
            invalid = [name for name, cases in groups.items() if len(cases) < 2]
            if invalid:
                raise ValueError(
                    f"{attribute} requires at least two cases: {', '.join(invalid)}"
                )
        return self


class EvaluationDetail(BaseModel):
    id: str
    passed: bool
    score: float = Field(ge=0, le=1)
    message: str
    observed: Any = None
    expected: Any = None


class DimensionResult(BaseModel):
    score: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    passed: bool
    evaluated_items: int = Field(ge=0)
    passed_items: int = Field(ge=0)
    details: list[EvaluationDetail] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    schema_version: Literal[1] = 1
    dataset_name: str
    case_ids: list[str]
    dimensions: dict[EvaluationDimension, DimensionResult]
    overall_score: float = Field(ge=0, le=1)
    overall_threshold: float = Field(ge=0, le=1)
    regressions: dict[EvaluationDimension, float] = Field(default_factory=dict)
    maximum_regression: float = Field(ge=0, le=1)
    passed: bool
