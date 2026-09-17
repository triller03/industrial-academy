"""Fault Diagnosis evaluation — grades a student's check-list and diagnosis."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvaluationResult:
    score: float
    correct: bool
    checks_correct: int
    checks_total: int
    missable: bool
    feedback: list[str] = field(default_factory=list)
    recommended_step: str | None = None
    correct_diagnosis: str = ""


class FaultDiagnosisEvaluator:
    """Scores a student attempt against a reference of expected checks + diagnosis.

    Scoring model:
      - 60% weight for correct checks (with penalty for missed + wrong checks)
      - 40% weight for the diagnosis
      - partial credit, no negative to a floor; missable = zero checks reported.
    """

    CHECK_WEIGHT = 0.6
    DIAGNOSIS_WEIGHT = 0.4

    def evaluate(
        self,
        expected_checks: list[str],
        performed_checks: list[str],
        correct_diagnosis_keys: list[str],
        diagnosis_key: str | None,
        common_misdiagnoses: list[str] | None = None,
        diagnosis_text: str | None = None,
    ) -> EvaluationResult:
        expected_set = set(expected_checks)
        performed_set = set(performed_checks or [])
        common = common_misdiagnoses or []

        correct_hits = expected_set & performed_set
        wrong_hits = performed_set - expected_set
        missed = expected_set - performed_set

        checks_total = len(expected_set) + len(wrong_hits)
        checks_correct = len(correct_hits)
        check_score = checks_correct / checks_total if checks_total else 0.0

        feedback: list[str] = []
        if missed:
            feedback.append(
                f"Missed checks: {', '.join(sorted(missed))}. A technician would have run these before diagnosing."
            )
        if wrong_hits:
            feedback.append(f"Unnecessary/incorrect checks performed: {', '.join(sorted(wrong_hits))}.")

        # A diagnosis counts as correct if an exact key matches or any key appears in the free text.
        submitted = " ".join(p for p in [diagnosis_key, diagnosis_text] if p).strip().lower()
        keys = [k.lower() for k in correct_diagnosis_keys]
        diagnosis_correct = bool(submitted) and (
            (diagnosis_key or "").strip().lower() in keys
            or any(k in submitted for k in keys)
        )
        diagnosis_score = 1.0 if diagnosis_correct else 0.0
        if not diagnosis_correct:
            if submitted and any(k in submitted for k in common):
                feedback.append("That diagnosis is a known misdiagnosis for this scenario — review the abnormal condition again.")
            else:
                feedback.append("The diagnosis does not match the expected root cause for this injected fault.")

        score = round((check_score * self.CHECK_WEIGHT) + (diagnosis_score * self.DIAGNOSIS_WEIGHT), 3)
        correct = diagnosis_correct and check_score >= 0.7
        missable = not performed_checks or not diagnosis_key
        recommendation = None if correct_diagnosis_keys else None

        if check_score < 1.0:
            recommendation = (
                "Better check sequence: verify instrument power -> verify signal -> verify command -> "
                "verify actuation -> verify permissive. Re-run the diagnostic tree before committing to a cause."
            )

        return EvaluationResult(
            score=score,
            correct=correct,
            checks_correct=checks_correct,
            checks_total=checks_total,
            missable=missable,
            feedback=feedback,
            recommended_step=recommendation,
        )


evaluator = FaultDiagnosisEvaluator()