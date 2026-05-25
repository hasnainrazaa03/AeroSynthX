# Phase 3 -- Intent Parsing Layer

Target release: `v0.3.0`.
Status: **In progress.**
Goal: Convert free-form natural-language requests into a strict,
validated, fully-provenanced `DesignIntent`. The LLM lives only here;
it never emits engineering values that bypass the physics or geometry
layers.

---

## Acceptance Criteria

- [x] `aerosynthx.intent` package implemented:
  - [x] `errors` -- typed exceptions rooted under `AeroSynthXError`.
  - [x] `schemas` -- Pydantic v2 models: `AirfoilSpec`, `FlowCondition`,
        `Assumption`, `DesignIntent`, `ParseResult`, `Provenance`.
  - [x] `llm` -- provider-agnostic `LLMClient` Protocol; no provider
        hardcoded in core; `StaticLLMClient` for tests.
  - [x] `parser` -- `IntentParser.parse(text)` that validates LLM JSON
        output against the schema and retries on validation failure
        (bounded retries) before raising.
  - [x] `offline` -- deterministic regex-based parser for tests and a
        zero-network fallback path.
- [x] Operating envelope enforced in the schema validators:
  - 2D, incompressible: Mach < 0.3.
  - NACA 4-digit only (family `"naca4"`, 4-digit designation).
  - Exactly one of `velocity_m_s` or `mach` provided; the other is
    derived downstream.
  - Positive chord; finite numeric fields.
- [x] Provenance: every leaf field of `DesignIntent` is tagged as
      `user_provided` or `inferred` in `Provenance.fields`.
- [x] Coverage gate met (>= 90% line / branch on `aerosynthx.intent`).
- [x] All quality gates green.
- [x] `CHANGELOG.md` updated; tagged `v0.3.0`.

---

## Public Surface

```python
class AirfoilSpec(BaseModel):
    family: Literal["naca4"]
    designation: str            # e.g. "2412"
    chord_m: PositiveFloat

class FlowCondition(BaseModel):
    altitude_m: float | None
    velocity_m_s: PositiveFloat | None
    mach: float | None          # 0 <= mach < 0.3 if set
    angle_of_attack_deg: float  # |alpha| <= 20
    reynolds_target: PositiveFloat | None  # advisory only

class Assumption(BaseModel):
    field_path: str
    value: Any
    reason: str

class Provenance(BaseModel):
    fields: dict[str, Literal["user_provided", "inferred"]]

class DesignIntent(BaseModel):
    airfoil: AirfoilSpec
    flow: FlowCondition
    assumptions: list[Assumption]
    provenance: Provenance
    notes: str | None

class ParseResult(BaseModel):
    intent: DesignIntent
    raw_input: str
    model: str                  # LLM identifier or "offline"
    attempts: int

class LLMClient(Protocol):
    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]: ...

class IntentParser:
    def __init__(self, client: LLMClient, *, max_retries: int = 2,
                 model_name: str = "unknown") -> None: ...
    def parse(self, text: str) -> ParseResult: ...

def parse_offline(text: str) -> ParseResult: ...
```

## Out of Scope

- Any specific provider (OpenAI, Anthropic, Azure, etc.) -- the core
  ships only the Protocol; providers are wired in Phase 6/7.
- Any networking inside the package (tests must run offline).
- Computing physics values from the intent (that is Phase 5's job).
