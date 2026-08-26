"""
Falcon Phase 7 — Risk Gate Engine (M4)

Structured, auditable risk veto layer. Replaces the ad-hoc
if/elif risk flag checks in DecisionEngine v1.

Design principles:
  - Pure function: same DecisionContext → same RiskGateResult.
  - No side effects, no I/O.
  - Emits structured DecisionEvidence for every veto/warning.
  - Downstream DecisionGenerator reads gate.decision to short-circuit.

Usage:
    gate = RiskGate()
    result = gate.evaluate(context)
    if result.decision == RiskGateDecision.VETO:
        # Issue NO_TRADE immediately
"""
from app.schemas.decision_context import DecisionContext
from app.schemas.risk_gate import RiskGateDecision, RiskGateResult
from app.schemas.evaluator_result import DecisionEvidence, EvidenceImpact, EvidenceStatus
from app.schemas.risk_assessment import RiskLevel
from app.schemas.validation_result import ValidationStatus
from app.schemas.execution_readiness import ExecutionReadinessStatus


# Thresholds
_MAX_DATA_AGE_SECONDS = 60   # data older than 60s is stale
_HIGH_SPREAD_THRESHOLD = 3.0  # spread above 3.0 is a warning


class RiskGate:
    """
    Evaluates DecisionContext for blocking veto conditions and non-blocking warnings.

    Veto conditions (any one causes VETO):
      - RiskLevel.EXTREME
      - ValidationStatus.FAILED
      - ExecutionReadinessStatus.BLOCKED

    Warning conditions (non-blocking):
      - Spread > threshold
      - High-impact news
      - RiskLevel.MEDIUM (warn, not veto)
      - Data age > threshold
    """

    def evaluate(self, context: DecisionContext) -> RiskGateResult:
        vetoes: list[DecisionEvidence] = []
        warnings: list[DecisionEvidence] = []
        risk_score = 0.0

        # ── Pull artifact values safely ──────────────────────────────────
        risk = context.risk
        validation = context.validation
        readiness = context.readiness

        risk_level = getattr(risk, "level", None) or getattr(risk, "riskLevel", None)
        val_status = getattr(validation, "status", None) or getattr(validation, "validationStatus", None)
        exec_status = getattr(readiness, "status", None)

        # ── Veto 1: Extreme Risk ─────────────────────────────────────────
        if risk_level is not None and str(risk_level).upper() in ("EXTREME",):
            risk_score += 40.0
            vetoes.append(DecisionEvidence(
                indicator="RISK_LEVEL",
                observedValue="EXTREME",
                weight=1.0,
                impact=EvidenceImpact.CONTRADICTING,
                status=EvidenceStatus.FAIL,
                explanation="Risk assessment is EXTREME. No trade is permissible under this condition.",
                category="RISK"
            ))

        # ── Veto 2: Validation Failed ─────────────────────────────────────
        if val_status is not None and str(val_status).upper() in ("FAILED",):
            risk_score += 30.0
            vetoes.append(DecisionEvidence(
                indicator="VALIDATION_STATUS",
                observedValue="FAILED",
                weight=1.0,
                impact=EvidenceImpact.CONTRADICTING,
                status=EvidenceStatus.FAIL,
                explanation="Validation pipeline failed. Signal does not meet minimum quality thresholds.",
                category="VALIDATION"
            ))

        # ── Veto 3: Execution Blocked ─────────────────────────────────────
        if exec_status is not None and str(exec_status).upper() in ("BLOCKED",):
            risk_score += 30.0
            vetoes.append(DecisionEvidence(
                indicator="EXECUTION_STATUS",
                observedValue="BLOCKED",
                weight=1.0,
                impact=EvidenceImpact.CONTRADICTING,
                status=EvidenceStatus.FAIL,
                explanation="Execution readiness engine has blocked this trade.",
                category="EXECUTION"
            ))

        # ── Warning 1: Medium Risk ────────────────────────────────────────
        if risk_level is not None and str(risk_level).upper() in ("MEDIUM",):
            risk_score += 15.0
            warnings.append(DecisionEvidence(
                indicator="RISK_LEVEL",
                observedValue="MEDIUM",
                weight=0.6,
                impact=EvidenceImpact.NEUTRAL,
                status=EvidenceStatus.WARN,
                explanation="Risk level is MEDIUM. Exercise position sizing discipline.",
                category="RISK"
            ))

        # ── Warning 2: High Impact News ───────────────────────────────────
        if context.newsImpact and context.newsImpact.upper() in ("HIGH",):
            risk_score += 10.0
            warnings.append(DecisionEvidence(
                indicator="NEWS_IMPACT",
                observedValue="HIGH",
                weight=0.5,
                impact=EvidenceImpact.NEUTRAL,
                status=EvidenceStatus.WARN,
                explanation="High-impact news event active. Volatility spike risk is elevated.",
                category="NEWS"
            ))

        # ── Warning 3: High Spread ────────────────────────────────────────
        if context.spread and context.spread > _HIGH_SPREAD_THRESHOLD:
            risk_score += 8.0
            warnings.append(DecisionEvidence(
                indicator="SPREAD",
                observedValue=f"{context.spread:.2f}",
                weight=0.4,
                impact=EvidenceImpact.NEUTRAL,
                status=EvidenceStatus.WARN,
                explanation=f"Spread ({context.spread:.2f}) exceeds the safe threshold ({_HIGH_SPREAD_THRESHOLD}).",
                category="SPREAD"
            ))

        # ── Warning 4: Stale Data ─────────────────────────────────────────
        if context.dataAgeSeconds and context.dataAgeSeconds > _MAX_DATA_AGE_SECONDS:
            risk_score += 5.0
            warnings.append(DecisionEvidence(
                indicator="DATA_AGE",
                observedValue=f"{context.dataAgeSeconds}s",
                weight=0.3,
                impact=EvidenceImpact.NEUTRAL,
                status=EvidenceStatus.WARN,
                explanation=f"Market data is {context.dataAgeSeconds}s old (threshold: {_MAX_DATA_AGE_SECONDS}s).",
                category="DATA_QUALITY"
            ))

        # ── Final gate decision ───────────────────────────────────────────
        risk_score = min(100.0, risk_score)

        if vetoes:
            gate_decision = RiskGateDecision.VETO
            summary = (
                f"VETO — {len(vetoes)} blocking condition(s): "
                + ", ".join(v.indicator for v in vetoes)
            )
        elif warnings:
            gate_decision = RiskGateDecision.WARN
            summary = (
                f"WARN — {len(warnings)} non-blocking concern(s): "
                + ", ".join(w.indicator for w in warnings)
            )
        else:
            gate_decision = RiskGateDecision.PASS
            summary = "PASS — All risk conditions acceptable."

        return RiskGateResult(
            decision=gate_decision,
            score=round(risk_score, 2),
            vetoes=vetoes,
            warnings=warnings,
            summary=summary,
        )
