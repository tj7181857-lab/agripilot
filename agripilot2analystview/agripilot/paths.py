"""Shared filesystem locations for AgriPilot (project root, data, outputs)."""
from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
# this file lives in <project>/agripilot/paths.py
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")
KB_PATH = os.path.join(DATA_DIR, "agri_knowledge_multilingual.json")
CROP_CSV = os.path.join(DATA_DIR, "crop_recommendation.csv")
DISEASE_DATA_DIR = os.path.join(DATA_DIR, "disease_dataset")
CROP_MODELS_DIR = os.path.join(OUTPUT_DIR, "crop_models")
CROP_BUNDLE = os.path.join(CROP_MODELS_DIR, "crop_recommender_bundle.joblib")
DISEASE_MODEL = os.path.join(OUTPUT_DIR, "disease_model.keras")
DISEASE_MAPPING = os.path.join(OUTPUT_DIR, "disease_class_mapping.json")
DISEASE_METRICS = os.path.join(OUTPUT_DIR, "disease_model_metrics.json")
CROP_COMPARISON = os.path.join(OUTPUT_DIR, "crop_model_comparison.json")
DEFAULT_DB = os.path.join(OUTPUT_DIR, "agripilot.db")


def db_path() -> str:
    return os.environ.get("AGRIPILOT_DB", DEFAULT_DB)
