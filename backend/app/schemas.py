from decimal import Decimal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


def http_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("value must be an absolute http:// or https:// URL")
    return value


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in {"freelancer", "client"}:
            raise ValueError("role must be freelancer or client")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str = Field(max_length=255)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=20, max_length=128)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=128)
    password: str = Field(min_length=8, max_length=128)


class SessionResponse(BaseModel):
    token: str
    role: str
    verification_token: str | None = None


class ProjectCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10, max_length=10000)
    required_skills: str = Field(default="", max_length=2000)
    budget: Decimal = Field(gt=0, decimal_places=7)
    asset: str = "XLM"
    deadline: str | None = None


class InvitationCreate(BaseModel):
    freelancer_id: str


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(default="", max_length=5000)
    amount: Decimal = Field(gt=0, decimal_places=7)
    due_date: str | None = None


class AgreementCreate(BaseModel):
    freelancer_id: str
    amount: Decimal = Field(gt=0, decimal_places=7)
    asset: str = "XLM"
    description: str = Field(min_length=10, max_length=10000)
    milestones: list[MilestoneCreate] = Field(min_length=1, max_length=50)

    @field_validator("asset")
    @classmethod
    def validate_asset(cls, value: str) -> str:
        if value != "XLM":
            raise ValueError("Only native Testnet XLM is currently supported")
        return value


class MilestoneUpdate(BaseModel):
    deliverable_url: str | None = Field(default=None, max_length=1000)
    feedback: str | None = Field(default=None, max_length=2000)

    @field_validator("deliverable_url")
    @classmethod
    def validate_deliverable_url(cls, value: str | None) -> str | None:
        return http_url(value) if value else value


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    stellar_address: str | None = Field(default=None, min_length=56, max_length=56)
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    hourly_rate: Decimal | None = Field(default=None, gt=0)
    skills: str | None = Field(default=None, max_length=2000)
    project_rate: Decimal | None = Field(default=None, gt=0)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=10, max_length=10000)
    required_skills: str | None = Field(default=None, max_length=2000)
    budget: Decimal | None = Field(default=None, gt=0, decimal_places=7)
    deadline: str | None = None


class AvailabilityUpdate(BaseModel):
    available: bool
    availability_note: str = Field(default="", max_length=500)


class PortfolioCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    url: str = Field(min_length=8, max_length=1000)
    description: str = Field(default="", max_length=1000)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return http_url(value)


class AgreementRevisionCreate(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=7)
    description: str = Field(min_length=10, max_length=10000)
    milestones: list[MilestoneCreate] = Field(min_length=1, max_length=50)
    change_note: str = Field(default="", max_length=500)


class MilestoneListUpdate(BaseModel):
    milestones: list[MilestoneCreate]


class PaymentIntentCreate(BaseModel):
    milestone_id: str
    memo: str | None = Field(default=None, max_length=28)


class DisputeCreate(BaseModel):
    agreement_id: str
    milestone_id: str | None = None
    reason: str = Field(min_length=10, max_length=2000)
    evidence_url: str | None = Field(default=None, max_length=1000)

    @field_validator("evidence_url")
    @classmethod
    def validate_evidence_url(cls, value: str | None) -> str | None:
        return http_url(value) if value else value


class DisputeEvidence(BaseModel):
    evidence_url: str = Field(min_length=8, max_length=1000)
    note: str = Field(default="", max_length=1000)

    @field_validator("evidence_url")
    @classmethod
    def validate_evidence_url(cls, value: str) -> str:
        return http_url(value)


class DisputeResolution(BaseModel):
    resolution: str

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, value: str) -> str:
        if value not in {"release_freelancer", "refund_client", "cancel_agreement"}:
            raise ValueError("resolution must be release_freelancer, refund_client, or cancel_agreement")
        return value
