from pydantic import BaseModel, Field


class Hackathon(BaseModel):
    nom: str = ""
    date_debut: str = ""
    date_fin: str = ""
    lieu: str = ""
    description: str = ""
    url: str = ""
    type: str = ""
    thematiques: list[str] = []
    conditions: str = ""
    strategique: str = ""
    source: str = ""
    source_engine: str = "tavily"
    score_strategique: int = 0
    raison: str = ""
    pertinence_tuttop: str = ""

    model_config = {"extra": "ignore"}


class Evenement(BaseModel):
    nom: str = ""
    type: str = ""
    date: str = ""
    lieu: str = ""
    description: str = ""
    url: str = ""
    thematiques: list[str] = []
    strategique: str = ""
    source: str = ""
    source_engine: str = "tavily"
    score_strategique: int = 0
    raison: str = ""
    pertinence_tuttop: str = ""

    model_config = {"extra": "ignore"}
