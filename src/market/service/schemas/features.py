from pydantic import BaseModel, ConfigDict, Field


class Features(BaseModel):
    model_config = ConfigDict(extra="forbid") 

    age: int = Field(ge=0)
    work_experience: float = Field(ge=0)
    family_size: int = Field(ge=1)
    gender: bool
    ever_married: bool
    graduated: bool
    spending_score: int = Field(ge=0)
