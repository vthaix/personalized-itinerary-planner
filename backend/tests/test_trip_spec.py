import pytest
from pydantic import ValidationError

from app.models import TripSpec


def example_spec() -> dict:
    """Ví dụ ở mục 1 của thiết kế: 4 người, gia đình, Nha Trang, 3 ngày."""
    return {
        "intent": "create",
        "destination": "Nha Trang",
        "n_days": 3,
        "party_size": 4,
        "party_type": "family",
        "days": [
            {"day": 1, "energy": "low", "max_radius_m": 3000, "anchor": "hotel",
             "evidence": "mới đi xe một đêm nên mệt, chỉ muốn đi chơi gần khách sạn"},
            {"day": 2, "energy": "high", "themes": ["ẩm thực", "tham quan"],
             "evidence": "đưa gia đình đi chơi, ăn uống, tham quan cả ngày"},
            {"day": 3, "energy": "medium", "themes": ["trải nghiệm đặc biệt"],
             "evidence": "làm điều gì đó thật đáng nhớ"},
        ],
        "preferences": [
            {"group": "B", "key": "family_friendly", "priority": "high",
             "evidence": "cùng gia đình", "confidence": 0.9},
        ],
        "missing": ["lodging", "transport"],
    }


def test_valid_example():
    spec = TripSpec.model_validate(example_spec())
    assert spec.n_days == 3 and spec.budget is None and spec.lodging is None


def test_days_length_must_match():
    data = example_spec()
    data["days"].pop()
    with pytest.raises(ValidationError):
        TripSpec.model_validate(data)


def test_days_must_be_consecutive():
    data = example_spec()
    data["days"][2]["day"] = 5
    with pytest.raises(ValidationError):
        TripSpec.model_validate(data)


def test_ab_preference_requires_evidence():
    data = example_spec()
    data["preferences"][0]["evidence"] = ""
    with pytest.raises(ValidationError):
        TripSpec.model_validate(data)


def test_group_c_needs_no_evidence():
    data = example_spec()
    data["preferences"].append(
        {"group": "C", "key": "budget", "priority": "low", "confidence": 0.5}
    )
    TripSpec.model_validate(data)


def test_edit_requires_target():
    with pytest.raises(ValidationError):
        TripSpec.model_validate({"intent": "edit", "destination": "Nha Trang", "n_days": 3})


def test_edit_with_target_ok():
    spec = TripSpec.model_validate({
        "intent": "edit", "destination": "Nha Trang", "n_days": 3,
        "edit_target": {"days": [2], "instruction": "đổi ngày 2 sang đi đảo"},
    })
    assert spec.edit_target.days == [2]


def test_confidence_range():
    data = example_spec()
    data["preferences"][0]["confidence"] = 1.5
    with pytest.raises(ValidationError):
        TripSpec.model_validate(data)
