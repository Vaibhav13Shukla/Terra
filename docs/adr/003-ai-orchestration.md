# ADR 003 — Deterministic core, LLM only for language (intent + explanation)

## Context

The brief is explicit and non-negotiable on this (§8, §61): "The LLM must
not be allowed to directly perform scientific calculations when deterministic
code can do them," and "the core scientific workflow must NOT depend
completely on an LLM." We had to decide exactly where the language/AI
boundary sits and how the system behaves when Bedrock is disabled,
misconfigured, or fails at request time.

## Decision

Two independent responsibilities, two independent modules, one shared
contract type (`app.domain.models.AnalysisIntent`):

1. **Intent parsing** (natural language -> structured `AnalysisIntent`):
   - Default: `app.agents.intent_parser.parse_intent` -- deterministic
     keyword rules. Always available, zero dependencies beyond the domain
     model. Covers the brief's own evaluation examples (§37): an
     out-of-domain question ("best place for a nuclear reactor") returns
     `supported=False` with a clear reason rather than being silently
     reinterpreted; a question demanding unwarranted certainty ("definitely
     needs irrigation") stays supported but is flagged for an explicit
     no-certainty caution.
   - Optional: `app.agents.bedrock.parse_intent_bedrock` -- same output
     contract, via Amazon Bedrock, for more flexible phrasing.

2. **Result explanation** (`AnalysisResult` -> natural-language summary):
   - Default: `app.agents.explain.explain_result` -- a template that only
     ever references fields already present on the result. It cannot invent
     a number that wasn't computed by `app.services.analysis_engine`.
   - Optional: `app.agents.bedrock.explain_result_bedrock` -- same job, via
     Bedrock, given the result as JSON and instructed not to introduce
     values not present in it.

Every Bedrock function raises a single `BedrockUnavailableError` on any
failure (missing `boto3`, auth, throttling, malformed output, schema
validation) -- see `app/agents/bedrock.py`. `app/api/main.py`'s `_explain`
helper catches it and falls back to the deterministic explainer
unconditionally; `create_analysis` does the same for intent parsing. Bedrock
is therefore never a single point of failure for the request path (§61) --
verified directly: the offline test suite runs with `boto3` not installed at
all and all Bedrock-touching tests still pass, exercising exactly this
fallback.

`app.services.analysis_engine` imports neither `app.agents.intent_parser` nor
`app.agents.bedrock` -- the engine only ever sees a fully-resolved
`AnalysisRequest`. This is enforced by module boundaries, not convention.

## Consequences

- Terra runs its full pipeline -- discovery, filtering, NDVI, comparison,
  API -- with zero AWS credentials and zero LLM calls. This is what the
  fixtures-based integration/contract/e2e tests exercise.
- Adding Bedrock-backed intent parsing to a request costs one settings flag
  (`BEDROCK_ENABLED`); removing it (or losing connectivity to it) costs
  nothing -- the deterministic path is not a "degraded mode," it's the
  primary, always-correct path that Bedrock supplements.
- Trade-off: the deterministic intent parser is keyword-based, not a full
  NLU model, so it will misclassify unusual phrasings the keyword lists
  don't anticipate. This is an accepted, documented limitation (§37) rather
  than something papered over with an LLM call that could silently fail.
