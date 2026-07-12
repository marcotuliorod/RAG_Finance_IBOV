from pydantic import BaseModel


class ClaimJudgement(BaseModel):
    claim: str
    supported: bool
    reasoning: str | None = None


class FaithfulnessResult(BaseModel):
    claims: list[ClaimJudgement]
    score: float


class RelevancyResult(BaseModel):
    score: float
    reasoning: str
