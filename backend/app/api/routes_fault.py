from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.core.security import get_current_user
from app.database import get_db
from app.fault import evaluator
from app.models import FaultScenario, User
from app.schemas import FaultDiagnoseIn, FaultDiagnoseOut

router = APIRouter(prefix="/fault", tags=["fault"])


@router.post("/diagnose", response_model=FaultDiagnoseOut)
def diagnose(
    body: FaultDiagnoseIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    scenario = db.query(FaultScenario).filter(FaultScenario.id == body.fault_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Fault scenario not found")

    performed = [c.check_id for c in body.checks if c.performed]
    result = evaluator.evaluate(
        expected_checks=scenario.expected_checks,
        performed_checks=performed,
        correct_diagnosis_keys=scenario.correct_diagnosis_keys,
        diagnosis_key=body.diagnosis_key,
        diagnosis_text=body.diagnosis,
        common_misdiagnoses=scenario.common_misdiagnoses,
    )

    log_activity(
        db,
        current.id,
        "fault.diagnose",
        entity=f"fault:{scenario.id}",
        detail={"score": result.score, "correct": result.correct, "checks": f"{result.checks_correct}/{result.checks_total}"},
    )
    db.commit()

    return FaultDiagnoseOut(
        fault_id=scenario.id,
        score=result.score,
        correct=result.correct,
        checks_correct=result.checks_correct,
        checks_total=result.checks_total,
        missable=result.missable,
        feedback=result.feedback,
        correct_diagnosis=scenario.correct_diagnosis,
        recommended_step=result.recommended_step,
    )