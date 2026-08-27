from pydantic import BaseModel


class ClaimJudgement(BaseModel):
    claim: str
    supported: bool
    reasoning: str | None = None


class FaithfulnessResult(BaseModel):
    claims: list[ClaimJudgement]
    score: float
    input_tokens: int = 0
    output_tokens: int = 0


class RelevancyResult(BaseModel):
    score: float
    reasoning: str
    input_tokens: int = 0
    output_tokens: int = 0
