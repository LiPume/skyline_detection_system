"""Skyline — Models package."""
from models.history import DetectionRecord
from models.model_manager import ModelManager, get_model, SUPPORTED_MODELS

__all__ = ["DetectionRecord", "ModelManager", "get_model", "SUPPORTED_MODELS"]
