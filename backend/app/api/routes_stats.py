"""Learner dashboard + admin analytics aggregation endpoints.

Everything is computed from the existing tables (user_progress, activity_logs,
certificates, projects) so there is no new storage. Time buckets are UTC.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import (
    ActivityLog,
    Certificate,
    Project,
    ProjectSection,
    User,
    UserProgress,
)
from app.schemas import (
    AdminAnalyticsOut,
    AdminIndustryStats,
    AdminProjectStats,
    AdminUserRow,
    DailyActivityOut,
    LearnerStatsOut,
    ProjectStatsOut,
)

router = APIRouter(prefix="/stats", tags=["stats"])

DAY_ACTIONS = ("section.completed", "fault.diagnose", "credential.issued", "sync.apply")


def _utc(dt: datetime | None) -> datetime:
    """Attach UTC to naive datetimes (SQLite returns them naive) and normalise."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _day(dt: datetime) -> str:
    return _utc(dt).date().isoformat()


def _bucket_days(n: int) -> list[str]:
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def _streaks(days: set[str]) -> tuple[int, int]:
    """Return (current_streak, longest_streak) from a set of 'yyyy-mm-dd' days."""
    if not days:
        return 0, 0
    ordered = sorted(days)
    longest = 1
    run = 1
    for prev, cur in zip(ordered, ordered[1:]):
        if (datetime.fromisoformat(cur) - datetime.fromisoformat(prev)).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    today = datetime.now(timezone.utc).date().isoformat()
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    if today not in days and yesterday not in days:
        current = 0
    else:
        current = 0
        probe = today if today in days else yesterday
        p = datetime.fromisoformat(probe).date()
        while p.isoformat() in days:
            current += 1
            p -= timedelta(days=1)
    return current, longest


def _daily_bucket(rows: list[ActivityLog], days: list[str]) -> dict[str, DailyActivityOut]:
    buckets = {d: DailyActivityOut(date=d) for d in days}
    per_user: dict[str, set[int]] = defaultdict(set)
    for r in rows:
        d = _day(r.created_at)
        if d not in buckets:
            continue
        buckets[d].actions += 1
        per_user[d].add(r.user_id)
        if r.action == "section.completed":
            buckets[d].sections += 1
        elif r.action == "fault.diagnose":
            buckets[d].faults += 1
    for d, users in per_user.items():
        buckets[d].users_active = len(users)
    return buckets


# ---------- learner ----------
@router.get("/learner", response_model=LearnerStatsOut)
def learner_stats(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    progress = db.query(UserProgress).filter(UserProgress.user_id == current.id).all()
    activities = (
        db.query(ActivityLog).filter(ActivityLog.user_id == current.id).all()
    )
    faults = [a for a in activities if a.action == "fault.diagnose"]
    fault_scores = [float((a.detail or {}).get("score", 0.0)) for a in faults]
    fault_correct = sum(1 for a in faults if (a.detail or {}).get("correct") is True)
    certs = db.query(Certificate).filter(Certificate.user_id == current.id).count()

    active_days = {_day(a.created_at) for a in activities}
    current_streak, longest = _streaks(active_days)

    days = _bucket_days(14)
    daily = [_daily_bucket(activities, days)[d] for d in days]

    projects: list[ProjectStatsOut] = []
    by_project: dict[int, list[UserProgress]] = defaultdict(list)
    for p in progress:
        by_project[p.project_id].append(p)
    for project_id, rows in by_project.items():
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            continue
        total = db.query(ProjectSection).filter(ProjectSection.project_id == project_id).count()
        completed = sum(1 for r in rows if r.status == "completed")
        percent = round((completed / total * 100) if total else 0.0, 1)
        status = "completed" if total and completed == total else "in_progress"
        projects.append(ProjectStatsOut(
            project_id=project_id,
            slug=project.slug,
            title=project.title,
            industry=project.industry,
            difficulty=project.difficulty,
            hours=project.hours,
            total_sections=total,
            completed_sections=completed,
            percent=percent,
            status=status,
        ))
    projects.sort(key=lambda p: (p.status == "completed", -p.percent))

    return LearnerStatsOut(
        sections_completed=sum(1 for r in progress if r.status == "completed"),
        projects_started=len(by_project),
        certificates=certs,
        time_spent_seconds=sum(r.time_spent_seconds or 0 for r in progress),
        fault_attempts=len(faults),
        faults_correct=fault_correct,
        fault_score_avg=round(mean(fault_scores), 3) if fault_scores else 0.0,
        streak_days=current_streak,
        longest_streak=longest,
        active_days=len(active_days),
        daily=daily,
        projects=projects,
    )


# ---------- admin ----------
@router.get("/admin", response_model=AdminAnalyticsOut)
def admin_analytics(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if not current.is_admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required")

    users = db.query(User).all()
    projects = db.query(Project).all()
    progress = db.query(UserProgress).all()
    activities = db.query(ActivityLog).all()
    certs = db.query(Certificate).all()

    enrolled: dict[tuple[int, int], int] = {}
    for p in progress:
        enrolled[(p.user_id, p.project_id)] = enrolled.get((p.user_id, p.project_id), 0) + 1
    enrollments = sum(
        1 for key in set((u_id, p_id) for (u_id, p_id) in enrolled)
    )

    now = datetime.now(timezone.utc)
    cut7 = now - timedelta(days=7)
    cut30 = now - timedelta(days=30)
    active7 = {a.user_id for a in activities if _utc(a.created_at) >= cut7}
    active30 = {a.user_id for a in activities if _utc(a.created_at) >= cut30}

    faults = [a for a in activities if a.action == "fault.diagnose"]
    fault_scores = [float((a.detail or {}).get("score", 0.0)) for a in faults]

    cert_by_project: dict[int, int] = defaultdict(int)
    for c in certs:
        cert_by_project[c.project_id] += 1

    by_project_list: list[AdminProjectStats] = []
    for project in projects:
        project_enrollments = {
            u_id for (u_id, p_id) in enrolled if p_id == project.id
        }
        n = len(project_enrollments)
        completed = cert_by_project[project.id]
        total = db.query(ProjectSection).filter(ProjectSection.project_id == project.id).count()
        per_user_percent: list[float] = []
        for user_id in project_enrollments:
            done = sum(
                1 for p in progress if p.user_id == user_id and p.project_id == project.id and p.status == "completed"
            )
            per_user_percent.append(round((done / total * 100) if total else 0.0, 1))
        avg_progress = round(mean(per_user_percent), 1) if per_user_percent else 0.0
        by_project_list.append(AdminProjectStats(
            project_id=project.id,
            slug=project.slug,
            title=project.title,
            industry=project.industry,
            difficulty=project.difficulty,
            hours=project.hours,
            enrollments=n,
            completions=completed,
            completion_rate=round((completed / n) if n else 0.0, 3),
            avg_progress=avg_progress,
        ))
    by_project_list.sort(key=lambda p: (-p.enrollments, p.title))

    by_industry_list: list[AdminIndustryStats] = []
    for industry in sorted({p.industry for p in projects}):
        group = [p for p in by_project_list if p.industry == industry]
        enrolls = sum(p.enrollments for p in group)
        completions = sum(p.completions for p in group)
        by_industry_list.append(AdminIndustryStats(
            industry=industry,
            projects=len(group),
            enrollments=enrolls,
            completions=completions,
            completion_rate=round((completions / enrolls) if enrolls else 0.0, 3),
        ))

    days = _bucket_days(14)
    daily = [_daily_bucket(activities, days)[d] for d in days]

    recent_users = [
        AdminUserRow(
            id=u.id,
            full_name=u.full_name,
            email=u.email,
            institution=u.institution,
            is_admin=u.is_admin,
            created_at=u.created_at,
        )
        for u in sorted(users, key=lambda u: u.created_at, reverse=True)[:8]
    ]

    learners = [u for u in users if not u.is_admin]
    return AdminAnalyticsOut(
        users_total=len(users),
        learners_total=len(learners),
        users_active_7d=len(active7),
        users_active_30d=len(active30),
        projects_total=len(projects),
        projects_published=sum(1 for p in projects if p.status == "published"),
        sections_completed_total=sum(1 for p in progress if p.status == "completed"),
        certificates_total=len(certs),
        enrollments_total=enrollments,
        fault_attempts_total=len(faults),
        fault_accuracy=round(mean(fault_scores), 3) if fault_scores else 0.0,
        completion_rate=round((len(certs) / enrollments) if enrollments else 0.0, 3),
        daily=daily,
        by_project=by_project_list,
        by_industry=by_industry_list,
        recent_users=recent_users,
    )