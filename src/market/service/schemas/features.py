from pydantic import BaseModel, ConfigDict, Field


class Features(BaseModel):
    model_config = ConfigDict(extra="forbid") 

    age: int = Field(ge=0, le=140)
    work_experience: float = Field(ge=0, le=140)
    family_size: int = Field(ge=1, le=50)
    gender: bool
    ever_married: bool
    graduated: bool
    spending_score: int = Field(ge=0, le=2)
