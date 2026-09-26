from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ConversationCreate(Input):
    requestId: str = Field(min_length=1, max_length=128)
    title: str = Field(default='新的对话', min_length=1, max_length=256)
    itemId: str | None = Field(default=None, max_length=64)


class TurnCreate(Input):
    requestId: str = Field(min_length=1, max_length=128)
    body: str = Field(min_length=1, max_length=20000)
    mode: Literal['auto','record','discuss','execute'] = 'auto'
    itemId: str | None = Field(default=None, max_length=64)
    runId: str | None = Field(default=None, max_length=64)
    anchor: str | None = Field(default=None, max_length=2000)
    researchItemIds: list[str] = Field(default_factory=list, max_length=5)
    repositoryPath: str | None = Field(default=None, max_length=4096)
    acknowledgeExcludedChanges: bool = False

    @field_validator('researchItemIds')
    @classmethod
    def valid_research_ids(cls, value):
        if len(set(value)) != len(value) or any(not v or len(v)>64 for v in value):
            raise ValueError('请选择不重复的研究事项，最多5篇')
        return value

    @field_validator('body')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('请输入内容')
        return value


class PersonalModelUpdate(Input):
    version: int = Field(ge=0)
    goals: str = Field(max_length=8000)
    preferences: str = Field(max_length=8000)


class KnowledgeDraft(Input):
    path: str = Field(min_length=1, max_length=1000)
    content: str = Field(min_length=1, max_length=100000)
    reason: str = Field(min_length=1, max_length=2000)


class Decision(Input):
    # Required nullable fields keep the structured-output contract unambiguous.
    intent: Literal['answer','clarify','record','discuss','execute','feedback','context','knowledge']
    reply: str = Field(min_length=1, max_length=30000)
    title: str = Field(min_length=1, max_length=256)
    itemId: str | None
    itemType: Literal['research','learning','personal','hobby','requirement','fix','other']
    instruction: str
    feedback: str | None
    proposedGoal: str | None
    knowledge: KnowledgeDraft | None
