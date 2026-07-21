# Stock research report evaluation

This directory contains versioned, offline datasets for repeatable product
evaluation. The suite grades the assembled report contract rather than an
unstructured screenshot or a live provider response. It does not need network
access, an API key, a database, or an LLM judge.

## Run the suite

From `backend/`:

```bash
python -m app.evaluation evals/stock_research_reports.v1.json
```

The default output is JSON and the exit status is `1` when a threshold fails.
Write a CI artifact with:

```bash
python -m app.evaluation evals/stock_research_reports.v1.json \
  --output /tmp/finsight-evaluation.json
```

To catch relative regressions as well as absolute threshold failures, compare
against a previously retained result:

```bash
python -m app.evaluation evals/stock_research_reports.v1.json \
  --baseline /path/to/previous-evaluation.json \
  --output /tmp/finsight-evaluation.json
```

`--allow-failures` keeps the JSON pass/fail result but returns exit status `0`.
It is useful for exploratory runs, not for a required quality gate.

## The eight dimensions

| Dimension | Deterministic measurement |
|---|---|
| Citation coverage | Share of generated factual statements whose citations resolve to allowed, provenance-bearing support in the same report section |
| Numeric accuracy | Reference-value comparisons plus checks that numbers in generated statements occur in their cited evidence |
| Source freshness | Share of provenance nodes labeled `fresh` within the configured age window, or correctly labeled `historical` |
| Contradiction handling | Expected conflicting facts remain present, the Evidence Auditor detects them, and the report explicitly acknowledges the disagreement |
| Important-information coverage | Required prices, drivers, risks, two-sided evidence, events, or other dataset-defined report paths are present |
| Readability | Language-aware sentence-density and long-word heuristics over selected narrative paths; CJK text uses characters per sentence |
| Personalization consistency | Profile variants preserve the same sourced-fact fingerprint while matching their declared section order, depth, and highlights |
| Multilingual consistency | Language variants preserve sourced facts, numeric claims, citation targets, and presentation/highlight contracts, and contain dataset-defined locale markers |

Every dimension is scored from `0` to `1`. The dataset defines an absolute
threshold for each dimension, an overall threshold, a maximum evidence age,
and the maximum permitted drop from a baseline. A run passes only when all
dimension thresholds, the overall threshold, and the regression limit pass.

## Dataset contract

`stock_research_reports.v1.json` has one complete `base_report` validated as a
`ResearchReportDraft`. Each case applies a recursive object override; arrays are
replaced as a unit. A case may also apply scalar `report_path_overrides` to
existing list members, such as profile-specific highlight flags. Shared
expectations define known numeric facts, important information, intentional
source contradictions, and text paths for readability.

Cases can join two comparison groups:

- `personalization_group` compares profile-driven presentation variants;
- `multilingual_group` compares localized narratives over the same evidence.

When adding a case:

1. Keep inputs fixed and offline; never fetch live prices in the fixture.
2. Use provenance-bearing `DataPoint` and `Evidence` objects from the production
   report schema.
3. Add ground-truth numeric expectations for decision-relevant values.
4. Include both risk and opportunity information and at least one current event.
5. If a conflict is intentional, name both fact paths and the acknowledgement
   that explains it.
6. For localized cases, keep numeric content and citation targets invariant and
   add unambiguous language markers.
7. Increment the filename and `schema_version` only for a breaking dataset
   contract change; add new non-breaking cases to the current version.

The test suite also mutates the reference fixture to prove that each class of
regression is detected. A perfect score on the reference data therefore means
the evaluators recognize the known-good contract; it is not a claim that any
live stock report is inherently correct.
