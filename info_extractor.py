"""
Card Info Extractor — vision LLM only.

Sends the card image directly to an LLM (OpenRouter).
No OCR, no regex, no scoring heuristics — the model sees the image.
"""

import logging
import base64
from typing import Optional

logger = logging.getLogger(__name__)


def extract_info_from_image(
    image_path: str,
    api_key: str,
    model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    base_url: str = "https://openrouter.ai/api/v1",
) -> dict:
    """
    Extract business card fields by sending the image directly to a vision LLM.

    Args:
        image_path: Path to the card image file
        api_key: OpenRouter API key
        model: Vision model name
        base_url: OpenRouter base URL

    Returns:
        Dict with keys: name, company, position, phone, email
    """
    default = {"name": "null", "company": "null", "position": "null",
               "phone": "null", "email": "null"}

    if not api_key:
        logger.error("No API key configured for vision LLM.")
        return default

    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai package not installed. Run: pip install openai")
        return default

    # Read and encode the image
    try:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        import mimetypes
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/jpeg"
    except Exception as e:
        logger.error(f"Failed to read image: {e}")
        return default

    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract business card data from images. "
                        "Return ONLY valid JSON with these keys: "
                        "name, company, position, phone, email. "
                        "Use null for any field you can't determine. "
                        "Never put addresses or website URLs in any field."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract the business card details from this image. "
                                "Return JSON: {\"name\": \"...\", \"company\": \"...\", "
                                "\"position\": \"...\", \"phone\": \"...\", \"email\": \"...\"}"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            },
                        },
                    ],
                },
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
            extra_headers={
                "HTTP-Referer": "https://github.com/sanchita3131/card-manager",
                "X-Title": "Card Manager",
            },
        )

        content = response.choices[0].message.content
        if not content:
            logger.warning("LLM returned empty response.")
            return default

        import json
        parsed = json.loads(content)
        result = {
            "name": str(parsed.get("name") or "null"),
            "company": str(parsed.get("company") or "null"),
            "position": str(parsed.get("position") or "null"),
            "phone": str(parsed.get("phone") or "null"),
            "email": str(parsed.get("email") or "null"),
        }
        logger.info(f"Vision LLM result: {result}")
        return result

    except Exception as e:
        logger.error(f"Vision LLM failed: {e}")
        return default
