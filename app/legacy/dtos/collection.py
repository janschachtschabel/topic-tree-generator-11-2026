from pydantic import BaseModel, Field

from app.legacy.dtos.properties import Properties


class Collection(BaseModel):
    """
    Repräsentiert einen Knoten im Themenbaum mit Titel, Kurztitel,
    Properties und möglichen Unterknoten (subcollections).
    """

    title: str
    shorttitle: str
    properties: Properties
    subcollections: list["Collection"] | None = Field(default_factory=list)

    def to_dict(self) -> dict:
        """
        Konvertiert das Collection-Objekt rekursiv in ein Dictionary,
        das alle Subcollections enthält.
        """
        result = {"title": self.title, "shorttitle": self.shorttitle, "properties": self.properties.model_dump()}
        if self.subcollections:
            result["subcollections"] = [sub.to_dict() for sub in self.subcollections]
        return result
