"""
OCR engine using PaddleOCR with ONNX Runtime backend.

PaddleOCR downloads lightweight ONNX models automatically on first run:
  - Text detection model: PP-OCRv5_server_det_onnx
  - Text recognition model: en_PP-OCRv5_mobile_rec_onnx

Using engine='onnxruntime' eliminates the PaddlePaddle framework dependency
and runs entirely through ONNX Runtime.
"""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class OCREngine:
    """Wrapper around PaddleOCR with ONNX Runtime backend."""

    def __init__(self, lang: str = "en", use_onnx: bool = True):
        """
        Initialize the OCR engine.

        Args:
            lang: Language code (default 'en' for English)
            use_onnx: Use ONNX Runtime backend (True = no PaddlePaddle needed)
        """
        self.lang = lang
        self.use_onnx = use_onnx
        self._ocr = None

    def _lazy_init(self):
        """Lazy-initialize PaddleOCR so we don't import at module load time."""
        if self._ocr is None:
            logger.info(
                "Initializing PaddleOCR with ONNX backend "
                "(models download on first run)..."
            )
            from paddleocr import PaddleOCR

            kwargs = dict(
                lang=self.lang,
                ocr_version="PP-OCRv5",
                use_textline_orientation=False,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                text_det_box_thresh=0.3,
                text_det_thresh=0.3,
            )
            if self.use_onnx:
                kwargs["engine"] = "onnxruntime"
                kwargs["device"] = "cpu"

            self._ocr = PaddleOCR(**kwargs)
            logger.info("PaddleOCR initialized successfully.")

    def extract_text(self, image_path: str) -> List[Tuple[str, float, List[List[float]]]]:
        """
        Extract text from an image.

        Args:
            image_path: Path to the image file

        Returns:
            List of (text, confidence, [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]) tuples
            sorted by position on the card (top-to-bottom, left-to-right)
        """
        self._lazy_init()

        # More lenient thresholds for card text detection
        result = list(self._ocr.predict(
            image_path,
            text_det_thresh=0.2,
            text_det_box_thresh=0.2,
            text_rec_score_thresh=0.1,
        ))

        if not result:
            logger.warning("No text detected in the image.")
            return []

        # Result is a list of OCRResult objects (typically one per page)
        parsed = []
        for page_result in result:
            data = page_result.json["res"]
            rec_texts = data.get("rec_texts", [])
            rec_scores = data.get("rec_scores", [])
            rec_polys = data.get("rec_polys", data.get("dt_polys", []))

            for i, text in enumerate(rec_texts):
                if text.strip():
                    confidence = rec_scores[i] if i < len(rec_scores) else 0.0
                    poly = rec_polys[i] if i < len(rec_polys) else [[0, 0], [0, 0], [0, 0], [0, 0]]
                    parsed.append((text.strip(), confidence, poly))

        # Sort top-to-bottom, left-to-right
        parsed.sort(key=lambda x: (x[2][0][1], x[2][0][0]))

        return parsed

    def extract_text_plain(self, image_path: str) -> List[str]:
        """
        Extract text lines from an image, returning just the text strings.

        Args:
            image_path: Path to the image file

        Returns:
            List of text lines in reading order
        """
        results = self.extract_text(image_path)
        return [text for text, conf, bbox in results if conf > 0.3]
