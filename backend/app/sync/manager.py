"""Offline Sync Manager.

Conflict resolution rules (per the blueprint, not naive last-write-wins):
  - completion beats in-progress
  - higher score wins
  - large time deltas are summed rather than overwritten
  - otherwise last-write wins by updated_at
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.fault import evaluator
from app.models import Device, FaultScenario, User, UserProgress
from app.plans import fault_attempt_daily_budget, today_fault_attempts

SYNC_WINDOW_SECONDS = 5 * 60  # treat updates within this delta as concurrent


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ConflictResolution:
    @staticmethod
    def resolve_server_local(server: UserProgress, local: dict) -> tuple[bool, dict]:
        """Decide whether the local change wins over existing server state.

        Returns (local_wins, merged_ints) where merged_ints is a dict of integer
        counter merges (time / attempts) applied to the winning state.
        """
        local_status = local.get("status", "in_progress")
        local_score = float(local.get("score", 0.0))
        local_seconds = int(local.get("time_spent_seconds", 0))
        local_updated = local.get("updated_at")

        merged_time = local_seconds
        if server is not None:
            # large positive delta on one side: the offline session accumulated time.
            remote_delta = local_seconds - server.time_spent_seconds
            if remote_delta > SYNC_WINDOW_SECONDS:
                merged_time = local_seconds
            elif 0 <= remote_delta <= SYNC_WINDOW_SECONDS:
                merged_time = server.time_spent_seconds
            else:
                merged_time = server.time_spent_seconds

        if server is None:
            return True, {"merged_time": merged_time}

        # rule 1: completion beats in-progress
        if local_status == "completed" and server.status != "completed":
            return True, {"merged_time": merged_time}
        if server.status == "completed" and local_status != "completed":
            return False, {}

        # rule 2: higher score wins
        if local_score > server.score:
            return True, {"merged_time": merged_time}
        if local_score < server.score:
            return False, {}

        # rule 4: otherwise later updated_at wins; concurrent updates default to last-write-wins
        if local_updated and server.updated_at:
            return local_updated > server.updated_at, {"merged_time": merged_time}
        return True, {"merged_time": merged_time}


class SyncManager:
    def __init__(self, max_devices: int = 3, max_days_offline: int = 90):
        self.max_devices = max_devices
        self.max_days_offline = max_days_offline
        self.conflict = ConflictResolution()

    # ---------- device binding ----------
    def authorize_device(self, db: Session, user: User, fingerprint: str, label: str | None, platform: str | None) -> Device:
        device = (
            db.query(Device)
            .filter(Device.user_id == user.id, Device.device_fingerprint == fingerprint)
            .first()
        )
        if device:
            device.is_authorized = True
            device.device_label = label or device.device_label or "Unnamed device"
            device.platform = platform or device.platform
            device.last_seen = _now()
            db.commit()
            db.refresh(device)
            return device

        authorized_count = (
            db.query(Device).filter(Device.user_id == user.id, Device.is_authorized.is_(True)).count()
        )
        if authorized_count >= self.max_devices:
            raise PermissionError(
                f"Device limit of {self.max_devices} reached. Revoke an existing device to authorise a new one."
            )
        device = Device(
            user_id=user.id,
            device_fingerprint=fingerprint,
            device_label=label or "Unnamed device",
            platform=platform,
            is_authorized=True,
            last_seen=_now(),
        )
        db.add(device)
        db.commit()
        db.refresh(device)
        return device

    def revoke_device(self, db: Session, user: User, device_id: int) -> bool:
        device = (
            db.query(Device)
            .filter(Device.id == device_id, Device.user_id == user.id)
            .first()
        )
        if not device:
            return False
        device.is_authorized = False
        db.commit()
        return True

    def assert_device_authorized(self, db: Session, user: User, fingerprint: str) -> Device:
        device = (
            db.query(Device)
            .filter(Device.user_id == user.id, Device.device_fingerprint == fingerprint)
            .first()
        )
        if not device or not device.is_authorized:
            raise PermissionError("This device is not authorised. Authorise it before syncing.")
        device.last_seen = _now()
        db.commit()
        return device

    # ---------- sync ----------
    def sync(self, db: Session, user: User, changes: list[dict]) -> dict:
        applied: list[dict] = []
        conflicts: list[dict] = []

        budget = fault_attempt_daily_budget(user)
        synced_attempts = 0

        for change in changes:
            entity = change.get("entity")
            if entity == "fault_attempt":
                if budget is not None and today_fault_attempts(db, user.id) + synced_attempts >= budget:
                    conflicts.append(
                        {
                            "entity": entity,
                            "reason": "Free Sandbox daily Fault Lab limit reached",
                            "payload": change,
                        }
                    )
                    continue
                graded = self._grade_fault_attempt(db, user.id, change.get("payload", {}))
                if graded is None:
                    conflicts.append(
                        {"entity": entity, "reason": "unknown fault_id", "payload": change}
                    )
                else:
                    synced_attempts += 1
                    applied.append(graded)
                continue

            if entity != "progress":
                conflicts.append({"entity": entity, "reason": f"unsupported entity type: {entity}", "payload": change})
                continue

            payload = change.get("payload", {})
            project_id = payload.get("project_id")
            section_key = payload.get("section_key")
            if not project_id or not section_key:
                conflicts.append({"entity": entity, "reason": "missing project_id/section_key", "payload": change})
                continue

            server_row = (
                db.query(UserProgress)
                .filter(
                    UserProgress.user_id == user.id,
                    UserProgress.project_id == project_id,
                    UserProgress.section_key == section_key,
                )
                .first()
            )

            local_wins, merge = self.conflict.resolve_server_local(server_row, payload)

            if local_wins:
                record = self._upsert_progress(db, user.id, project_id, section_key, payload, merge)
                applied.append(
                    {
                        "entity": "progress",
                        "local_key": f"{project_id}:{section_key}",
                        "status": record.status,
                        "score": record.score,
                        "payload": {
                            "project_id": project_id,
                            "section_key": section_key,
                            "status": record.status,
                            "score": record.score,
                        },
                    }
                )
            else:
                conflicts.append(
                    {
                        "entity": "progress",
                        "project_id": project_id,
                        "section_key": section_key,
                        "reason": "server state wins (higher completion/score/newer)",
                        "server_status": server_row.status,
                        "server_score": server_row.score,
                    }
                )

        db.commit()
        server_state = (
            db.query(UserProgress).filter(UserProgress.user_id == user.id).all()
        )
        return {
            "applied": applied,
            "conflicts": conflicts,
            "server_state": server_state,
        }

    def _grade_fault_attempt(self, db: Session, user_id: int, payload: dict) -> dict | None:
        """Grade a fault attempt that was queued while offline and fold it into progress."""
        fault_id = payload.get("fault_id")
        scenario = db.query(FaultScenario).filter(FaultScenario.id == fault_id).first()
        if scenario is None:
            return None

        performed = [
            c.get("check_id") for c in (payload.get("checks") or []) if c.get("performed")
        ]
        result = evaluator.evaluate(
            expected_checks=scenario.expected_checks,
            performed_checks=performed,
            correct_diagnosis_keys=scenario.correct_diagnosis_keys,
            diagnosis_key=payload.get("diagnosis_key"),
            diagnosis_text=payload.get("diagnosis"),
            common_misdiagnoses=scenario.common_misdiagnoses,
        )

        section_key = payload.get("section_key") or "fault_injection"
        status = "completed" if result.correct else "in_progress"
        progress_payload = {
            "status": status,
            "score": round(result.score * 100.0, 2),
            "time_spent_seconds": int(payload.get("time_spent_seconds", 0)),
            "attempts": 1,
            "updated_at": payload.get("updated_at"),
        }

        server_row = (
            db.query(UserProgress)
            .filter(
                UserProgress.user_id == user_id,
                UserProgress.project_id == scenario.project_id,
                UserProgress.section_key == section_key,
            )
            .first()
        )
        local_wins, merge = self.conflict.resolve_server_local(server_row, progress_payload)
        if local_wins:
            self._upsert_progress(
                db, user_id, scenario.project_id, section_key, progress_payload, merge
            )

        return {
            "entity": "fault_attempt",
            "local_key": f"fault:{fault_id}",
            "status": status,
            "score": round(result.score * 100.0, 2),
            "payload": {
                "fault_id": fault_id,
                "project_id": scenario.project_id,
                "section_key": section_key,
                "score": round(result.score, 4),
                "correct": result.correct,
                "checks_correct": result.checks_correct,
                "checks_total": result.checks_total,
                "feedback": result.feedback,
                "correct_diagnosis": scenario.correct_diagnosis,
                "recommended_step": result.recommended_step,
                "progress_applied": local_wins,
            },
        }

    def _upsert_progress(self, db: Session, user_id: int, project_id: int, section_key: str,
                         payload: dict, merge: dict) -> UserProgress:
        status = payload.get("status", "in_progress")
        score = float(payload.get("score", 0.0))
        seconds = int(merge.get("merged_time", payload.get("time_spent_seconds", 0)))
        attempts = int(payload.get("attempts", 1))

        record = (
            db.query(UserProgress)
            .filter(
                UserProgress.user_id == user_id,
                UserProgress.project_id == project_id,
                UserProgress.section_key == section_key,
            )
            .first()
        )
        if record is None:
            status_val = "completed" if status == "completed" else "in_progress"
            record = UserProgress(
                user_id=user_id,
                project_id=project_id,
                section_key=section_key,
                status=status_val,
                score=score,
                time_spent_seconds=seconds,
                attempts=attempts,
            )
            if status_val == "completed":
                record.completed_at = _now()
            db.add(record)
        else:
            record.status = status if status == "completed" else record.status if record.status == "completed" else "in_progress"
            record.score = max(record.score, score)
            record.time_spent_seconds = merge.get("merged_time", seconds)
            record.attempts = max(record.attempts, attempts)
            if status == "completed":
                record.completed_at = record.completed_at or _now()
        return record


sync_manager = SyncManager()