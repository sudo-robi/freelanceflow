from decimal import Decimal
from pydantic import BaseModel, Field, field_validator


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


class SessionResponse(BaseModel):
    token: str
    role: str


class ProjectCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10)
    required_skills: str = ""
    budget: Decimal = Field(gt=0, decimal_places=7)
    asset: str = "XLM"
    deadline: str | None = None


class InvitationCreate(BaseModel):
    freelancer_id: str


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = ""
    amount: Decimal = Field(gt=0, decimal_places=7)
    due_date: str | None = None


class AgreementCreate(BaseModel):
    freelancer_id: str
    amount: Decimal = Field(gt=0, decimal_places=7)
    asset: str = "XLM"
    description: str = Field(min_length=10)
    milestones: list[MilestoneCreate]

    @field_validator("asset")
    @classmethod
    def validate_asset(cls, value: str) -> str:
        if value != "XLM":
            raise ValueError("Only native Testnet XLM is currently supported")
        return value


class MilestoneUpdate(BaseModel):
    deliverable_url: str | None = None
    feedback: str | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    stellar_address: str | None = Field(default=None, min_length=56, max_length=56)
    title: str | None = None
    description: str | None = None
    hourly_rate: Decimal | None = Field(default=None, gt=0)
