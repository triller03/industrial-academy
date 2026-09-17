from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class UserRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    institution: str | None = None


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    is_admin: bool
    institution: str | None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


# ---------- Devices ----------
class DeviceAuthorizeIn(BaseModel):
    device_fingerprint: str = Field(min_length=16, max_length=256)
    device_label: str | None = None
    platform: str | None = None


class DeviceOut(ORMModel):
    id: int
    device_fingerprint: str
    device_label: str
    platform: str | None
    is_authorized: bool
    authorized_at: datetime
    last_seen: datetime | None


class DeviceRevokeIn(BaseModel):
    device_id: int


# ---------- Projects ----------
class ProjectSectionOut(ORMModel):
    id: int
    order: int
    key: str
    title: str
    content: str


class ProjectOut(ORMModel):
    id: int
    slug: str
    title: str
    industry: str
    description: str
    difficulty: str
    hours: int
    status: str
    sections: list[ProjectSectionOut] = []


class ProjectListItem(BaseModel):
    id: int
    slug: str
    title: str
    industry: str
    difficulty: str
    hours: int
    description: str


# ---------- Mentor ----------
class MentorChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    project_id: int | None = None
    section_key: str | None = None
    fault_id: int | None = None
    history: list[dict] = []


class MentorChatOut(BaseModel):
    reply: str
    mode: str
    level: int
    safety_triggered: bool
    frustration_detected: bool


# ---------- Fault ----------
class FaultCheckIn(BaseModel):
    check_id: str
    performed: bool
    note: str | None = None


class FaultDiagnoseIn(BaseModel):
    fault_id: int
    symptom: str | None = None
    checks: list[FaultCheckIn] = []
    diagnosis: str | None = None
    diagnosis_key: str | None = None


class FaultDiagnoseOut(BaseModel):
    fault_id: int
    score: float
    correct: bool
    checks_correct: int
    checks_total: int
    missable: bool
    feedback: list[str]
    correct_diagnosis: str
    recommended_step: str | None = None


class FaultScenarioListItem(ORMModel):
    id: int
    slug: str
    title: str
    symptom: str
    difficulty: int


class FaultDetailOut(BaseModel):
    id: int
    slug: str
    title: str
    description: str
    symptom: str
    operation_notes: str
    available_checks: list[str]
    difficulty: int


# ---------- Progress ----------
class ProgressUpdateIn(BaseModel):
    project_id: int
    section_key: str
    status: str = "in_progress"
    score: float = 0.0
    time_spent_seconds: int = 0


class ProgressOut(ORMModel):
    user_id: int
    project_id: int
    section_key: str
    status: str
    score: float
    attempts: int
    time_spent_seconds: int
    started_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None


class ProjectProgressOut(BaseModel):
    project_id: int
    total_sections: int
    completed_sections: int
    percent: float
    sections: list[ProgressOut]


# ---------- Sync ----------
class SyncChange(BaseModel):
    entity: str
    entity_id: int | None = None
    local_key: str
    payload: dict
    status: str
    score: float | None = None
    time_spent_seconds: int | None = None
    updated_at: datetime | None = None


class SyncRequest(BaseModel):
    device_fingerprint: str
    changes: list[SyncChange] = []


class SyncResult(BaseModel):
    applied: list[SyncChange]
    conflicts: list[dict]
    server_state: list[ProgressOut]


class OfflineManifestItem(BaseModel):
    project_id: int
    slug: str
    title: str
    industry: str
    difficulty: str
    version: str
    checksum: str
    size_bytes: int
    section_count: int
    fault_count: int
    generated_at: datetime


class FaultAttemptResult(BaseModel):
    fault_id: int
    score: float
    correct: bool
    checks_correct: int
    checks_total: int
    feedback: list[str]
    correct_diagnosis: str
    recommended_step: str | None = None


# ---------- Certificates / Portfolio ----------
class CertificateOut(ORMModel):
    id: int
    project_id: int
    certificate_ref: str
    score: float
    issued_at: datetime
    verification_token: str


class PortfolioOut(ORMModel):
    id: int
    project_id: int
    entry_ref: str
    title: str
    summary: str
    created_at: datetime