from pydantic import BaseModel


class Subvention(BaseModel):
    nom: str = ""
    type: str = ""
    sous_type: str = ""
    organisme: str = ""
    region: str = ""
    public_cible: str = ""
    deadline: str = ""
    date_publication: str = ""
    montant: str = ""
    eligibilite: str = ""
    mots_cles: str = ""
    type_aide: str = ""
    statut: str = ""
    priorite: str = ""
    score_strategique: int = 0
    pertinence: str = ""
    raison: str = ""
    url: str = ""
    lien_officiel: str = ""
    date_derniere_verification: str = ""
    description: str = ""
    thematiques: list[str] = []
    source: str = ""

    model_config = {"extra": "ignore"}
