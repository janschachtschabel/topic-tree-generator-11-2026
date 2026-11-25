"""What a use-case strategy hands back to the orchestrator."""

from dataclasses import dataclass, field

from app.domain.tree import Node
from app.schemas.response_v2 import ChangeRecord, Question, StructureInfo, Unassigned


@dataclass
class StrategyResult:
    roots: list[Node]
    title: str
    description: str = ""
    structure: StructureInfo | None = None
    unassigned: list[Unassigned] = field(default_factory=list)
    changes: list[ChangeRecord] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    shape_checked: bool = True
