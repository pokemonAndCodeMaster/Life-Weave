from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .models import WireModel


class OrganizationChange(WireModel):
    item_id: str = Field(alias='itemId', min_length=1)
    item_version: int = Field(alias='itemVersion', ge=1)
    topic_ids: list[str] | None = Field(default=None, alias='topicIds')
    domain_ids: list[str] | None = Field(default=None, alias='domainIds')
    parent_id: str | None = Field(default=None, alias='parentId')
    reason: str = Field(min_length=1)

    @property
    def changes_parent(self) -> bool:
        return 'parent_id' in self.model_fields_set


class OrganizationGroup(WireModel):
    key: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    goal: str = Field(min_length=1, max_length=5000)
    item_ids: list[str] = Field(alias='itemIds', min_length=1)


class OrganizationProposalInput(WireModel):
    request_id: str = Field(alias='requestId', min_length=1, max_length=128)
    item_ids: list[str] | None = Field(default=None, alias='itemIds')
    changes: list[OrganizationChange] | None = None
    groups: list[OrganizationGroup] | None = None
    reason: str = ''

    @model_validator(mode='after')
    def valid_scope(self) -> 'OrganizationProposalInput':
        if len(set(self.item_ids or [])) != len(self.item_ids or []):
            raise ValueError('事项列表存在重复 ID')
        if len({row.item_id for row in self.changes or []}) != len(self.changes or []):
            raise ValueError('一个建议批次中同一事项只能有一条变更')
        if len({row.key for row in self.groups or []}) != len(self.groups or []):
            raise ValueError('聚合组 key 不可重复')
        return self


class OrganizationActionInput(WireModel):
    request_id: str = Field(alias='requestId', min_length=1, max_length=128)


class OrganizationRule(WireModel):
    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    terms: list[str]
    topic_ids: list[str] = Field(alias='topicIds')
    domain_ids: list[str] = Field(alias='domainIds')
    enabled: bool = True


class OrganizationRulesInput(WireModel):
    version: int | None = Field(default=None, ge=1)
    rules: list[OrganizationRule]

    @model_validator(mode='after')
    def unique(self) -> 'OrganizationRulesInput':
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError('规则 ID 不可重复')
        return self
