from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import AIConversation, FaultScenario, ProjectSection, User
from app.mentor import MentorRequest, mentor_engine
from app.plans import can_full_solutions
from app.schemas import MentorChatIn, MentorChatOut

router = APIRouter(prefix="/mentor", tags=["mentor"])


@router.get("/status")
def mentor_status():
    """Which mentor backend is active (LLM provider vs deterministic engine)."""
    return mentor_engine.status()


def _topic_for(section_key: str | None, fault: FaultScenario | None) -> str | None:
    if fault:
        return fault.title
    if section_key:
        return section_key.replace("_", " ").title()
    return None


@router.post("/chat", response_model=MentorChatOut)
def chat(
    body: MentorChatIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    fault = None
    if body.fault_id:
        fault = db.query(FaultScenario).filter(FaultScenario.id == body.fault_id).first()

    frustration_streak = 0
    recent = (
        db.query(AIConversation)
        .filter(AIConversation.user_id == current.id)
        .order_by(AIConversation.id.desc())
        .limit(8)
        .all()
    )
    history = [
        {"role": ("user" if msg.role == "user" else "assistant"), "content": msg.content}
        for msg in reversed(recent)
        if msg.role in ("user", "mentor")
    ]
    for msg in recent:
        if msg.role == "user" and msg.mode == "guided":
            frustration_streak += 1

    # requested assistance level is carried in from the client history if present
    requested_level = 1
    for item in reversed(body.history or []):
        if item.get("role") == "user" and item.get("level"):
            requested_level = int(item["level"])
            break

    topic = _topic_for(body.section_key, fault)
    request = MentorRequest(
        message=body.message,
        section_key=body.section_key,
        topic=topic,
        requested_level=requested_level,
        frustration_streak=frustration_streak,
    )
    response = mentor_engine.respond(request, history=history)

    db.add(AIConversation(user_id=current.id, project_id=body.project_id, section_key=body.section_key,
                          role="user", content=body.message, mode=response.mode,
                          level=max(1, requested_level)))
    db.add(AIConversation(user_id=current.id, project_id=body.project_id, section_key=body.section_key,
                          role="mentor", content=response.reply, mode=response.mode, level=response.level))
    db.commit()

    return MentorChatOut(
        reply=response.reply,
        mode=response.mode,
        level=response.level,
        safety_triggered=response.safety_triggered,
        frustration_detected=response.frustration_detected,
    )


@router.post("/solution", response_model=MentorChatOut)
def solution(
    body: MentorChatIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    fault = None
    if body.fault_id:
        fault = db.query(FaultScenario).filter(FaultScenario.id == body.fault_id).first()

    if not can_full_solutions(current):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Full solutions are a Student Pro feature. Upgrade to unlock the step-by-step solution walkthrough.",
        )

    topic = _topic_for(body.section_key, fault)
    response = mentor_engine.solution(body.message, topic, body.history[0]["level"] if body.history else 4)

    db.add(AIConversation(user_id=current.id, project_id=body.project_id, section_key=body.section_key,
                          role="user", content=f"[solution request] {body.message}", mode="guided",
                          level=response.level))
    db.add(AIConversation(user_id=current.id, project_id=body.project_id, section_key=body.section_key,
                          role="mentor", content=response.reply, mode=response.mode, level=response.level))
    db.commit()

    return MentorChatOut(
        reply=response.reply,
        mode=response.mode,
        level=response.level,
        safety_triggered=response.safety_triggered,
        frustration_detected=response.frustration_detected,
    )