"""AI Mentor Engine — Socratic-first tutor with safety override.

Mode ladder (per the blueprint's mentor design):
    socratic  -> default. Asks one guiding question, never gives away the answer.
    guided    -> escalates when frustration is detected or on explicit request for help.
    safety    -> hardcoded override: any safety keyword forces direct, unambiguous,
                 non-negotiable guidance (never a Socratic question).
"""

from __future__ import annotations

import re

SAFETY_KEYWORDS = [
    "emergency stop",
    "e-stop",
    "estop",
    "lockout",
    "tagout",
    "loto",
    "live wire",
    "live terminal",
    "live panel",
    "live circuit",
    "live conductor",
    "live busbar",
    "panel is live",
    "still live",
    "working live",
    "arc flash",
    "arc blast",
    "energized",
    "high voltage",
    "hv",
    "confined space",
    "hot work",
    "ppe",
    "isolation",
    "de-energize",
    "de-energise",
    "energised",
    "lockable breaker",
    "breaker off",
    "verify zero energy",
    "zero energy",
]

FRUSTRATION_KEYWORDS = [
    "i don't understand",
    "i dont understand",
    "i don't get it",
    "i give up",
    "i'm stuck",
    "im stuck",
    "i am stuck",
    "confused",
    "lost",
    "this is too hard",
    "too difficult",
    "i can't do this",
    "i cant do this",
    "what is the answer",
    "just tell me",
    "give me the answer",
    "i need help",
    "help me",
    "struggling",
    "wasting my time",
    "i have no idea",
]

ASK_ANSWER_KEYWORDS = [
    "what is the answer",
    "give me the answer",
    "just tell me",
    "tell me the solution",
    "what do i do",
]

TOPIC_LEVELS = {
    "safety": 0,
    "ladder": 1,
    "plc": 1,
    "pid": 2,
    "io": 1,
    "p&id": 2,
    "hmi": 1,
    "scada": 2,
    "alarm": 1,
    "interlock": 2,
    "networking": 2,
    "commissioning": 2,
    "fault": 2,
    "troubleshoot": 2,
}

SOCRATIC_QUESTION_BANK = [
    "Before we go further, what does the symptom tell you? Is the loop live or dead at the point of failure?",
    "Walk me through your mental model: what has to be true for that pump to start?",
    "If you could only check one thing first, what would it be and why?",
    "Think about the chain from the field device to the processor. Where in that chain does the signal get lost?",
    "What is the difference between the value you are reading and the value you expect? What could create that difference?",
    "Did the process behave differently a moment ago? Changes in behaviour are clues — what changed?",
    "If this were a 4-20 mA loop reading 0 mA, what are the two possible causes?",
    "Which interlock could be silently holding this start command? How would you confirm it?",
]

GUIDED_STEPS = [
    "Let's work through this together. First, isolate what you can observe safely: the actual process value, the command, and the feedback.",
    "Second, confirm the input side: is the sensor powered and reporting a plausible value? 4 mA on a loop usually means something is open.",
    "Third, check the output side: is the PLC actually commanding the device, and is the actuator responding to that command?",
    "Finally, check the permissives and interlocks between the command and the device. A start command that never reaches the device is often a permissive problem, not a wiring problem.",
]

FULL_SOLUTION_INTRO = (
    "Here is the full reasoning. Read it after you have attempted the checks yourself — "
    "the point is to see how a working technician thinks, not to have the work done for you."
)

SAFETY_PREFACE = (
    "STOP. This is a safety-critical situation. I am not going to turn this into a guessing game. "
    "Follow these steps exactly, in order, without skipping any:"
)

SAFETY_STEPS = {
    "default": [
        "1. STOP work immediately and remove power from the equipment.",
        "2. Apply lockout/tagout (LOTO) so the only person who can re-energize is you.",
        "3. Verify zero-energy state with your own meter — never assume.",
        "4. Only then identify the fault. Do not troubleshoot live if the equipment can injure you.",
    ],
    "arc flash": [
        "1. STOP. Do NOT open, close, or touch that enclosure.",
        "2. Establish an arc-flash boundary and keep everyone outside it.",
        "3. If switching must occur, only a qualified person in proper PPE may operate it.",
        "4. Report immediately to supervision before any further action.",
    ],
    "confined space": [
        "1. STOP. Do NOT enter.",
        "2. A confined space requires a permit, gas testing, an attendant, and rescue equipment.",
        "3. If someone is inside and unwell, do NOT rush in after them — call for rescue.",
        "4. Follow your site's confined-space entry procedure exactly.",
    ],
}


def _contains_any(text: str, keywords: list[str]) -> tuple[bool, str | None]:
    lowered = text.lower()
    for kw in keywords:
        if kw in lowered:
            return True, kw
    return False, None


def _detect_safety(section_key: str | None, topic: str | None) -> str | None:
    """Return a safety category if the context itself is safety-critical."""
    title = topic
    if not title:
        return None
    if title in ("arc flash", "arc blast"):
        return "arc flash"
    if "confined space" in title:
        return "confined space"
    if any(k in title for k in ("emergency", "loto", "lockout", "tagout", "safety")):
        return "default"
    return None


class MentorRequest:
    def __init__(
        self,
        message: str,
        section_key: str | None = None,
        topic: str | None = None,
        requested_level: int = 1,
        frustration_streak: int = 0,
    ):
        self.message = message
        self.section_key = section_key
        self.topic = topic
        self.requested_level = max(1, min(5, requested_level))
        self.frustration_streak = frustration_streak


class MentorResponse:
    def __init__(self, reply: str, mode: str, level: int, safety_triggered: bool, frustration_detected: bool):
        self.reply = reply
        self.mode = mode
        self.level = level
        self.safety_triggered = safety_triggered
        self.frustration_detected = frustration_detected

    def as_dict(self) -> dict:
        return {
            "reply": self.reply,
            "mode": self.mode,
            "level": self.level,
            "safety_triggered": self.safety_triggered,
            "frustration_detected": self.frustration_detected,
        }


class AIMentorEngine:
    """Rule-based Socratic mentor. Extensible to an LLM backend later."""

    def __init__(self) -> None:
        self.socratic_questions = SOCRATIC_QUESTION_BANK
        self._question_index: dict[str, int] = {}
        self.guided_steps = GUIDED_STEPS
        self.topic_levels = TOPIC_LEVELS

    def respond(self, request: MentorRequest) -> MentorResponse:
        safety_triggered, safety_kw = _contains_any(request.message, SAFETY_KEYWORDS)
        if not safety_triggered:
            safety_triggered = bool(_detect_safety(request.section_key, request.topic))

        # Rule 1: safety always wins. No Socratic games with a live hazard.
        if safety_triggered:
            return self._safety_response(request, safety_kw)

        frustration_detected, _ = _contains_any(request.message, FRUSTRATION_KEYWORDS)
        asking_answer, _ = _contains_any(request.message, ASK_ANSWER_KEYWORDS)

        # Rule 2: explicit answer request or detected frustration escalates.
        if asking_answer or frustration_detected or request.frustration_streak >= 2:
            mode = "guided"
        else:
            mode = "socratic"

        # Rule 3: requested assistance level maps to depth.
        level = self._resolve_level(request, mode)
        reply = self._build_reply(request, mode, level)

        return MentorResponse(
            reply=reply,
            mode=mode,
            level=level,
            safety_triggered=False,
            frustration_detected=frustration_detected,
        )

    def solution(self, message: str, topic: str | None, requested_level: int) -> MentorResponse:
        """Explicit /mentor/solution endpoint — hands over guidance at a chosen depth."""
        safety_triggered, safety_kw = _contains_any(message, SAFETY_KEYWORDS)
        if safety_triggered:
            return self._safety_response(MentorRequest(message, topic=topic), safety_kw)

        level = max(1, min(5, requested_level))
        req = MentorRequest(message, topic=topic, requested_level=level)
        reply = self._build_reply(req, "guided", level)
        return MentorResponse(
            reply=reply,
            mode="guided",
            level=level,
            safety_triggered=False,
            frustration_detected=False,
        )

    def _resolve_level(self, request: MentorRequest, mode: str) -> int:
        if mode == "guided" and request.requested_level > 1:
            return request.requested_level
        topic_key = None
        if request.topic:
            for key, _lvl in self.topic_levels.items():
                if key in request.topic.lower():
                    topic_key = key
                    break
        if mode == "guided":
            return self.topic_levels.get(topic_key, 2)
        return 1

    def _build_reply(self, request: MentorRequest, mode: str, level: int) -> str:
        parts: list[str] = []
        if mode == "socratic":
            question = self._next_question(request)
            if level >= 2:
                parts.append("A small nudge: keep the signal chain in mind — input, logic, output, feedback.")
            parts.append(question)
            return "\n\n".join(parts)

        # guided mode escalates with level
        if level == 1:
            parts.append("Okay — here is your next step to try on your own:")
            parts.append(self.guided_steps[0])
        elif level == 2:
            parts.append("Let's walk it together. Here is the check sequence a technician would run:")
            parts.extend(self.guided_steps)
        elif level == 3:
            parts.append("Here is the walkthrough with reasoning attached:")
            parts.extend(self.guided_steps[:3])
            parts.append(
                "Why this order? You diagnose from the observable signal towards the cause, "
                "never from a guess backwards. Cheap, safe checks first."
            )
        elif level == 4:
            parts.append(FULL_SOLUTION_INTRO)
            parts.extend(self.guided_steps)
            parts.append(
                "In this project, the most common root causes in this section are: an interlock "
                "permissive not satisfied, a sensor on an open (4 mA) wire, or an output forced off "
                "in the diagnostic table. Confirm those three before suspecting the processor."
            )
        else:  # level 5 — expert industrial perspective
            parts.append(FULL_SOLUTION_INTRO)
            parts.extend(self.guided_steps)
            parts.append(
                "Expert perspective: log your checks as you go — time-stamped, in the maintenance log. "
                "A loop that reads 4.0 mA exactly on HART is a signature of an open circuit, not a real "
                "0% reading; a real 0% will read 4.0–4.1 mA with noise. If this were a HART device, "
                "your first action after checking power would be to read the live device variables, "
                "because the deviation can be read on the HART layer without touching field wiring."
            )
        return "\n\n".join(parts)

    def _next_question(self, request: MentorRequest) -> str:
        key = request.topic or request.section_key or "general"
        idx = self._question_index.get(key, 0)
        question = self.socratic_questions[idx % len(self.socratic_questions)]
        self._question_index[key] = idx + 1
        return question

    def _safety_response(self, request: MentorRequest, keyword: str | None) -> MentorResponse:
        category = "default"
        if keyword:
            if "arc" in keyword:
                category = "arc flash"
        elif request.topic and "arc" in request.topic.lower():
            category = "arc flash"
        if request.topic and "confined space" in (request.topic or "").lower():
            category = "confined space"

        steps = SAFETY_STEPS.get(category, SAFETY_STEPS["default"])
        reply = SAFETY_PREFACE + "\n\n" + "\n".join(steps)
        if category != "default":
            reply += "\n\n" + (
                "If you are not trained and equipped for this task, your only correct action "
                "is to stop and call for a competent person. This is not a matter of judgement to be debated."
            )
        return MentorResponse(
            reply=reply,
            mode="safety",
            level=0,
            safety_triggered=True,
            frustration_detected=False,
        )


mentor_engine = AIMentorEngine()