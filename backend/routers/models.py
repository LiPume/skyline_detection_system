"""
Skyline — Models API Router
REST API endpoints for model discovery and capabilities.
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.registry import (
    MODEL_REGISTRY,
    get_model_capabilities,
    list_all_models,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/models", tags=["models"])


# ── Response Schemas ────────────────────────────────────────────────────────────

class ModelCapabilitiesResponse(BaseModel):
    """Full capabilities response for a single model."""
    model_id: str
    display_name: str
    model_type: str  # 'open_vocab' | 'closed_set'
    supports_prompt: bool
    prompt_editable: bool
    supported_classes: list[str]
    class_filter_enabled: bool
    description: str


class ModelListItem(BaseModel):
    """Simplified model info for list endpoint."""
    model_id: str
    display_name: str
    model_type: str
    description: str


class ModelListResponse(BaseModel):
    """Response for GET /api/models."""
    models: list[ModelListItem]


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.get("", response_model=ModelListResponse)
async def list_models():
    """
    List all available models with basic info.
    Use this to populate the model selector dropdown.
    """
    models = list_all_models()
    return ModelListResponse(
        models=[
            ModelListItem(
                model_id=m.model_id,
                display_name=m.display_name,
                model_type=m.model_type,
                description=m.description,
            )
            for m in models
        ]
    )


@router.get("/{model_id}/capabilities", response_model=ModelCapabilitiesResponse)
async def get_model_capabilities_endpoint(model_id: str):
    """
    Get full capabilities for a specific model.
    Frontend uses this to dynamically render the configuration panel.
    
    Returns:
        - For open_vocab models: supported_classes will be empty, prompt_editable=True
        - For closed_set models: supported_classes contains all detectable classes
    """
    caps = get_model_capabilities(model_id)
    if not caps:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_id}' not found. Available: {list(MODEL_REGISTRY.keys())}"
        )
    return ModelCapabilitiesResponse(**caps.to_dict())
