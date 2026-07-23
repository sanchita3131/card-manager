"""
Image handling — minimal touch.

PaddleOCR works best on the raw, unmodified image.
Any preprocessing risks destroying text the model was trained to recognize.
"""

from pathlib import Path


def prepare(image_path: str) -> str:
    """
    Return the original image path unchanged.
    PaddleOCR handles its own preprocessing internally.
    No OpenCV transformations — they HURT more than they help.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    return image_path
