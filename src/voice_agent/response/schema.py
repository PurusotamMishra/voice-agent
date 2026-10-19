"""Structured response shape (architecture §9): per-vehicle sentences bound to listing ids."""

from typing import Literal

from pydantic import BaseModel, Field


class ItemSentence(BaseModel):
    listing_id: str
    text: str


class ComposedResponse(BaseModel):
    intro: str = Field(default="", description="Opening sentence. No numbers, no vehicle names.")
    items: list[ItemSentence] = Field(default_factory=list, description="One sentence per vehicle")
    closing: str = Field(default="", description="Closing question. No numbers, no vehicle names.")

    def sentences(self) -> list[str]:
        parts = [self.intro, *(i.text for i in self.items), self.closing]
        return [p.strip() for p in parts if p.strip()]

    def text(self) -> str:
        return " ".join(self.sentences())


class Violation(BaseModel):
    where: str
    kind: Literal["order", "number", "number_word", "entity", "extra_vehicle"]
    detail: str


class Verdict(BaseModel):
    ok: bool
    violations: list[Violation] = Field(default_factory=list)
    source: Literal["llm", "template"]
