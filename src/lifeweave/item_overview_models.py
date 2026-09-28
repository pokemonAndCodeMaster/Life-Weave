from __future__ import annotations

from pydantic import Field

from .models import WireModel


class ItemOverviewInput(WireModel):
    version: int = Field(ge=1)
    background: str = Field(max_length=5000)
    intent: str = Field(max_length=5000)
    expected_result: str = Field(alias='expectedResult', max_length=5000)
