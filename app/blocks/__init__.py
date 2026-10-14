"""
Canvas Block Registry.
Maps block kind string to (pydantic_schema, render_fn).
Extensible design: Adding a new block kind requires only a schema and a render function.
"""

from typing import Dict, Tuple, Type, Callable, Any
from pydantic import BaseModel

from app.blocks.schema import FlowBlock, CompareBlock, AnswerBlock, ChecklistBlock
from app.blocks.flow import render_flow
from app.blocks.compare import render_compare
from app.blocks.answer import render_answer
from app.blocks.checklist import render_checklist

BLOCK_REGISTRY: Dict[str, Tuple[Type[BaseModel], Callable[[Any], str]]] = {
    "flow": (FlowBlock, render_flow),
    "compare": (CompareBlock, render_compare),
    "answer": (AnswerBlock, render_answer),
    "checklist": (ChecklistBlock, render_checklist),
}


def render_block(kind: str, data: Any) -> str:
    """Render a block using the registry."""
    if kind not in BLOCK_REGISTRY:
        raise ValueError(f"Unknown block kind: {kind}. Registered kinds: {list(BLOCK_REGISTRY.keys())}")
    schema, render_fn = BLOCK_REGISTRY[kind]
    validated = schema.model_validate(data) if isinstance(data, dict) else data
    return render_fn(validated)
