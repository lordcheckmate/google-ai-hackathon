"""
Typed Pydantic schemas for the 4 block kinds.
Enforces the core rule: No model ever emits markup.
Instruction -> Gemini + Pydantic schema -> typed block JSON -> pure Python renderer.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# 1. Flow Block
class FlowNode(BaseModel):
    id: str = Field(description="Unique node identifier, e.g. n1, n2")
    label: str = Field(description="Short human-readable label for the step")
    shape: Literal["start", "step", "decision", "end"] = Field(
        default="step", description="Visual shape of the node"
    )
    note: str = Field(default="", description="Optional context or description")
    highlight: bool = Field(default=False, description="Whether node is currently highlighted")
    image_url: Optional[str] = Field(default=None, description="Optional Nano Banana illustration URL")


class FlowEdge(BaseModel):
    from_node: str = Field(alias="from", description="Source node id")
    to_node: str = Field(alias="to", description="Target node id")
    label: str = Field(default="", description="Optional transition condition or label")

    class Config:
        populate_by_name = True


class FlowBlock(BaseModel):
    kind: Literal["flow"] = "flow"
    title: str = Field(description="Process or workflow title")
    nodes: List[FlowNode] = Field(default_factory=list, description="Ordered process nodes")
    edges: List[FlowEdge] = Field(default_factory=list, description="Connections between nodes")


# 2. Compare Block
class CompareBlock(BaseModel):
    kind: Literal["compare"] = "compare"
    title: str = Field(description="Comparison title")
    options: List[str] = Field(description="Option columns being compared")
    criteria: List[str] = Field(description="Criterion rows")
    cells: List[List[str]] = Field(description="cells[criterion_index][option_index]")
    recommendation: Optional[str] = Field(default=None, description="Recommended choice, if any")


# 3. Answer Block
class AnswerSource(BaseModel):
    title: str
    url: str


class AnswerBlock(BaseModel):
    kind: Literal["answer"] = "answer"
    question: str
    answer: str
    detail: Optional[str] = None
    image_url: Optional[str] = None
    visual_caption: Optional[str] = None
    sources: List[AnswerSource] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "high"


# 4. Checklist Block
class ChecklistItem(BaseModel):
    text: str
    owner: Optional[str] = None
    done: bool = False


class ChecklistBlock(BaseModel):
    kind: Literal["checklist"] = "checklist"
    title: str
    items: List[ChecklistItem] = Field(default_factory=list)
