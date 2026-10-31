"""P1 auth request/response schemas."""

import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from .security import validate_password_rules


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = None
    billing_address: str | None = None

    _pw = field_validator("password")(validate_password_rules)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    customer_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    new_password: str

    _pw = field_validator("new_password")(validate_password_rules)


class StaffCreateRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="staff", pattern="^(admin|staff)$")

    _pw = field_validator("password")(validate_password_rules)


class CustomerOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    name: str
    email: str
    phone: str | None
    billing_address: str | None

    model_config = {"from_attributes": True}


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    billing_address: str | None = None
