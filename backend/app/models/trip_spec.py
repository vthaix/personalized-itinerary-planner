"""Lược đồ TripSpec — đầu ra duy nhất của bước hiểu ngôn ngữ (thiết kế mục 6.2).

Quy tắc: trường người dùng không nói thì để None, không suy đoán.
"""

from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Energy = Literal["low", "medium", "high"]
Priority = Literal["high", "medium", "low"]
PartyType = Literal["family_kids", "family", "couple", "friends", "solo", "elderly", "other"]
Transport = Literal["motorbike", "car", "taxi", "walk", "mixed"]


class DayContext(BaseModel):
    day: int = Field(ge=1)
    energy: Energy
    max_radius_m: int | None = Field(default=None, gt=0)  # None = không giới hạn
    anchor: Literal["hotel", "free"] = "free"
    start_time: time | None = None
    end_time: time | None = None
    themes: list[str] = Field(default_factory=list)
    evidence: str = Field(min_length=1)  # đoạn trích từ câu yêu cầu


class PreferenceItem(BaseModel):
    group: Literal["A", "B", "C"]
    key: str = Field(min_length=1)
    priority: Priority
    evidence: str = ""
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _evidence_required_for_ab(self) -> PreferenceItem:
        if self.group in ("A", "B") and not self.evidence.strip():
            raise ValueError("nhóm A/B bắt buộc có evidence")
        return self


class LodgingRef(BaseModel):
    name: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class BudgetSpec(BaseModel):
    amount_vnd: int | None = Field(default=None, gt=0)
    scope: Literal["total", "per_person", "per_day"] = "total"


class EditTarget(BaseModel):
    days: list[int] = Field(default_factory=list)
    place_id: str | None = None
    instruction: str = Field(min_length=1)


class TripSpec(BaseModel):
    intent: Literal["create", "edit", "ask"]
    destination: str = Field(min_length=1)
    n_days: int = Field(ge=1, le=14)
    start_date: date | None = None
    party_size: int | None = Field(default=None, ge=1)
    party_type: PartyType | None = None
    lodging: LodgingRef | None = None
    transport: Transport | None = None
    budget: BudgetSpec | None = None  # None = nhóm C, không cộng điểm
    days: list[DayContext] = Field(default_factory=list)
    preferences: list[PreferenceItem] = Field(default_factory=list)
    edit_target: EditTarget | None = None
    missing: list[str] = Field(default_factory=list)  # → Clarification

    @model_validator(mode="after")
    def _check_consistency(self) -> TripSpec:
        if self.intent == "create":
            if len(self.days) != self.n_days:
                raise ValueError(f"days có {len(self.days)} phần tử, n_days = {self.n_days}")
            if [d.day for d in self.days] != list(range(1, self.n_days + 1)):
                raise ValueError("days phải đánh số liên tiếp từ 1")
        if self.intent == "edit" and self.edit_target is None:
            raise ValueError("intent = edit cần edit_target")
        return self
