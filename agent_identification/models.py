from pydantic import BaseModel, Field
from enum import Enum


class SchoolType(str, Enum):
    PRIVATE = "Privé"
    PUBLIC = "Public"
    UNKNOWN = "Inconnu"


class Prospect(BaseModel):
    nom: str = Field(description="Nom de l'établissement")
    type: SchoolType = Field(description="Privé ou Public")
    localisation: str = Field(default="", description="Ville, Pays")
    site_web: str = Field(default="", description="URL du site")
    email: str = Field(default="", description="Email de contact")
    telephone: str = Field(default="", description="Téléphone")
    source: str = Field(default="", description="Source de la donnée")
    pays: str = Field(default="", description="Pays")
