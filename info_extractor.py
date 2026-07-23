"""
Card Info Extractor — scoring-based field matching.

Every text line gets scored for how likely it is to be each entity type.
The highest score wins. This handles ANY card layout.

Components:
  1. Email + Phone (regex — near-perfect)
  2. Position (keyword matching)
  3. Name (capitalization + structure rules)
  4. Company (suffix detection + position + font size)
  5. Everything else (fallback)

No LLM, no layout assumptions, just smart scoring.
"""

import re
import logging
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger(__name__)

# ─── Regex ────────────────────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+", re.IGNORECASE)

PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,9}(?:\s*(?:ext|xt|x)\s*\d{1,5})?",
    re.IGNORECASE,
)

WEB_RE = re.compile(
    r"(?:https?://)?(?:www\.)?[\w\-]+\.(?:com|org|net|io|co|app|dev|edu|gov|in|uk|au|ca)[\w\-./]*",
    re.IGNORECASE,
)

# ─── Position Keywords (comprehensive list) ───────────────────────────────────

POSITION_ABBREVIATIONS = [
    "ceo", "cfo", "cto", "coo", "cmo", "cio", "cao", "chro",
    "vp", "svp", "avp", "evp", "dvp", "md", "gm",
    "hr", "hrbp", "sdet", "sdor", "qa",
]

POSITION_FULL = [
    # C-level
    "chief", "principal",
    "executive", "vice president", "vice-president",
    # Director / Manager
    "director", "associate director", "executive director",
    "manager", "senior manager", "general manager",
    "product manager", "project manager", "program manager",
    "account manager", "operations manager",
    # Engineer / Tech
    "engineer", "software engineer", "senior engineer",
    "staff engineer", "lead engineer", "principal engineer",
    "devops engineer", "data engineer", "ml engineer", "ai engineer",
    "developer", "software developer", "web developer",
    "architect", "solution architect", "enterprise architect",
    "tech lead", "team lead", "technical lead",
    # Analyst / Consultant
    "analyst", "data analyst", "business analyst",
    "consultant", "senior consultant", "managing consultant",
    "specialist", "subject matter expert",
    "coordinator", "project coordinator",
    # Sales / Business
    "representative", "account executive", "sales executive",
    "business development", "bd manager",
    # Creative
    "designer", "graphic designer", "ux designer", "ui designer",
    "art director", "creative director",
    # Executive / Owner
    "president", "founder", "co-founder", "cofounder",
    "owner", "partner", "managing partner", "senior partner",
    "chairman", "chairperson", "board member", "trustee",
    # Other
    "head of", "lead", "supervisor", "associate",
    "trainee", "intern", "apprentice",
    "sales", "marketing", "operations",
    "scientist", "data scientist", "research scientist",
    "professor", "fellow", "advisor", "adviser",
    "officer", "staff",
]

POSITION_KEYWORDS = POSITION_ABBREVIATIONS + POSITION_FULL

# ─── Company Indicators ───────────────────────────────────────────────────────

COMPANY_SUFFIXES = [
    "inc", "llc", "ltd", "corp", "corporation", "gmbh",
    "co.", "company", "limited", "plc", "ag", "sa", "pty",
    "bv", "holding", "holdings", "group", "technologies", "technology",
    "systems", "solutions", "consulting", "consultancy",
    "ventures", "partners", "partnership",
    "enterprises", "enterprise", "industries", "industry",
    "international", "global", "labs", "lab", "studios", "studio",
    "inc.", "llc.", "ltd.", "corp.", "co.", "gmbh.",
    "association", "foundation", "institute", "corporation",
]

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip("·•-–—|,.;:\"'")


def _is_phone_line(text: str) -> bool:
    """Check if text is primarily a phone number."""
    digits = sum(1 for c in text if c.isdigit())
    return digits >= 7 and digits <= 15


def _get_position_keywords_matched(text: str) -> List[str]:
    """Return which position keywords match this text."""
    lower = text.lower().strip()
    matched = []
    for kw in POSITION_KEYWORDS:
        if len(kw.split()) > 1:
            if kw in lower:
                matched.append(kw)
        else:
            if (lower == kw or lower.startswith(kw + " ") or
                lower.endswith(" " + kw) or " " + kw + " " in lower):
                matched.append(kw)
    return matched


def score_line(cleaned: str, line_idx: int, total_lines: int,
               bbox_height: float, max_bbox_height: float,
               classified_as: Optional[str] = None) -> Dict[str, float]:
    """
    Score how likely a text line is to be each entity type.

    Returns dict of {entity_type: score}.
    Higher score = more likely. Only includes scores > 0.

    Features used:
      - Content-based: emails, phones, position keywords, company suffixes
      - Format-based: uppercase, capitalization, word count, digits
      - Layout-based: position on card (top vs bottom), relative font size
    """
    scores = {}
    if classified_as:
        return {classified_as: 100}  # Already classified

    lower = cleaned.lower()
    words = cleaned.split()
    word_count = len(words)
    rel_pos = line_idx / max(total_lines - 1, 1)  # 0.0 = top, 1.0 = bottom
    rel_font = bbox_height / max(max_bbox_height, 1)
    digits = sum(1 for c in cleaned if c.isdigit())

    # ─── EMAIL score ───────────────────────────────────────────────────────
    if EMAIL_RE.search(cleaned):
        scores["email"] = 100  # Almost certain

    # ─── PHONE score ───────────────────────────────────────────────────────
    m = PHONE_RE.search(cleaned)
    if m:
        candidate = m.group(0).strip()
        d = sum(1 for c in candidate if c.isdigit())
        if 7 <= d <= 15 and not re.match(r"^\d{4}$", candidate):
            score = 80
            # Higher if dense with digits
            score += min(15, d)
            scores["phone"] = score

    if _is_phone_line(cleaned):
        scores["phone"] = max(scores.get("phone", 0), 70)

    # ─── WEB/URL score (don't assign to any entity, just mark) ─────────────
    if WEB_RE.fullmatch(cleaned):
        scores["web"] = 100

    # ─── POSITION score ────────────────────────────────────────────────────
    matched_kws = _get_position_keywords_matched(cleaned)
    if matched_kws:
        score = 50
        score += min(20, len(matched_kws) * 5)
        # Pure position titles with just 1-3 words score higher
        if word_count <= 4:
            score += 10
        # Position is typically in the upper-middle to middle of card
        if 0.15 <= rel_pos <= 0.65:
            score += 5
        scores["position"] = score

    # ─── COMPANY score ─────────────────────────────────────────────────────
    company_score = 0
    # Has company suffix
    if any(cleaned.lower().endswith(s) or cleaned.lower() == s
           for s in COMPANY_SUFFIXES):
        company_score += 60
    # Contains company suffix in text
    for s in COMPANY_SUFFIXES:
        if s in lower:
            company_score += 15
            break
    # ALL-CAPS (brand name)
    if cleaned.isupper() and len(cleaned) > 3:
        company_score += 30
    # Large font (often company logo/name)
    if rel_font > 0.6:
        company_score += 20
    # Top of card (typical company position)
    if rel_pos < 0.25:
        company_score += 15
    # Penalty: if it looks like a position or has digits
    if matched_kws:
        company_score -= 15
    if digits > 0:
        company_score -= 10

    if company_score > 10:
        scores["company"] = company_score

    # ─── NAME score ─────────────────────────────────────────────────────────
    name_score = 0

    if word_count >= 2 and word_count <= 5:
        name_score += 15
    if not digits:
        name_score += 10
    if not cleaned.isupper():
        name_score += 5
    # Each significant word capitalized
    all_capped = True
    for w in words:
        if len(w) > 2 and not w[0].isupper() and w.lower() not in [
            "and", "the", "of", "de", "la", "van", "der", "den"
        ]:
            all_capped = False
            break
    if all_capped:
        name_score += 15
    # Medium font size (name is often prominently sized)
    if 0.3 <= rel_font <= 0.9:
        name_score += 10
    # Names are typically in upper-middle area
    if 0.1 <= rel_pos <= 0.50:
        name_score += 10
    # Doesn't look like position
    if not matched_kws:
        name_score += 15
    # Not a company
    if not any(cleaned.lower().endswith(s) for s in COMPANY_SUFFIXES):
        name_score += 10

    # Strong penalty for company indicators
    if any(cleaned.lower() == s for s in ["inc", "llc", "corp"]):
        name_score -= 50
    if cleaned.isupper() and len(cleaned) > 6:
        name_score -= 20

    # 🛑 NEW: Penalize corporate/division words that aren't names
    CORPORATE_WORDS = [
        "division", "department", "group", "solutions", "services",
        "consulting", "worldwide", "global", "international", "enterprise",
        "industries", "partners", "ventures", "holdings", "world",
        "nationwide", "incorporated", "limited", "company",
    ]
    for w in words:
        if w.lower() in CORPORATE_WORDS:
            name_score -= 25

    if name_score > 20:
        scores["name"] = name_score

    return scores


def extract_info_from_boxes(
    items: List[Tuple[str, float, List[List[float]]]],
    use_llm: bool = False,
    llm_api_key: str = "",
    llm_model: str = "openai/gpt-4o-mini",
    llm_base_url: str = "https://openrouter.ai/api/v1",
) -> Dict[str, Optional[str]]:
    """
    Extract card fields using scoring-based matching (with optional LLM).

    How it works:
      1. Extract email + phone from ALL text (regex — near-certain)
      2. If use_llm=True: try LLM for name/position/company
      3. Fallback: score every remaining line for company/name/position
      4. Assign each field to the line that scores highest for it

    Args:
        items: OCR output — list of (text, conf, bbox) tuples
        use_llm: Try LLM extraction (OpenRouter) for name/position/company
        llm_api_key: OpenRouter API key
        llm_model: Model name (e.g. "openai/gpt-4o-mini")
        llm_base_url: OpenRouter API base URL

    Returns dict with: company, name, position, phone, email
    """
    result = {"company": None, "name": None, "position": None,
              "phone": None, "email": None}
    if not items:
        return {k: "null" for k in result}

    # ─── ROUND 0: LLM extraction (if enabled) ────────────────────────────
    if use_llm and llm_api_key:
        logger.info("  Trying LLM extraction (OpenRouter)...")
        llm_result = extract_with_llm(items, llm_api_key, llm_model, llm_base_url)
        if llm_result:
            logger.info("  ✅ LLM extraction succeeded.")
            for key in ("name", "position", "company"):
                if llm_result.get(key):
                    result[key] = llm_result[key]
        else:
            logger.warning("  LLM extraction failed, falling back to scoring.")

    # Sort top-to-bottom
    items.sort(key=lambda x: x[2][0][1])

    classified = {}  # {item_idx: entity_type}
    total = len(items)
    max_h = max((x[2][2][1] - x[2][0][1]) for x in items)  # max bbox height

    # ─── ROUND 1: Extract email + phone (regex is reliable) ───────────────
    for i, (text, conf, bbox) in enumerate(items):
        cleaned = _clean(text)
        if not cleaned or conf < 0.1:
            classified[i] = "ignore"
            continue
        if EMAIL_RE.search(cleaned) and not result["email"]:
            m = EMAIL_RE.search(cleaned)
            result["email"] = m.group(0)
            classified[i] = "email"
        elif PHONE_RE.search(cleaned) and not result["phone"]:
            m = PHONE_RE.search(cleaned)
            cand = m.group(0).strip()
            d = sum(1 for c in cand if c.isdigit())
            if 7 <= d <= 15 and not re.match(r"^\d{4}$", cand):
                result["phone"] = cand
                classified[i] = "phone"
        elif _is_phone_line(cleaned) and not result["phone"]:
            result["phone"] = cleaned
            classified[i] = "phone"

    # ─── ROUND 2: Score remaining lines for name/position/company ─────────
    scores = {}  # {item_idx: {entity: score}}
    for i, (text, conf, bbox) in enumerate(items):
        if i in classified:
            continue
        cleaned = _clean(text)
        if not cleaned or conf < 0.1:
            classified[i] = "ignore"
            continue
        if WEB_RE.fullmatch(cleaned):
            classified[i] = "web"
            continue

        bbox_h = bbox[2][1] - bbox[0][1]
        s = score_line(cleaned, i, total, bbox_h, max_h)
        if s:
            scores[i] = s

    # ─── ROUND 3: Assign name, position, company ──────────────────────────
    # For each entity, find the line that scores highest
    entities = ["position", "company", "name"]
    taken = set(classified.keys())

    for entity in entities:
        if result[entity]:  # Already set (shouldn't happen for name/pos/co)
            continue

        best_idx = None
        best_score = 0
        for idx, entity_scores in scores.items():
            if idx in taken:
                continue
            sc = entity_scores.get(entity, 0)
            if sc > best_score:
                best_score = sc
                best_idx = idx

        if best_idx is not None:
            cleaned = _clean(items[best_idx][0])
            result[entity] = cleaned
            taken.add(best_idx)

    # ─── ROUND 4: Assign any remaining high-scoring competitors ───────────
    # If a field is still null but a line scored well for it,
    # assign it even if taken by another (resolve conflicts)
    if not result["company"]:
        for idx, entity_scores in sorted(scores.items(),
                                          key=lambda x: x[1].get("company", 0),
                                          reverse=True):
            if entity_scores.get("company", 0) > 15:
                result["company"] = _clean(items[idx][0])
                break

    if not result["name"]:
        for idx, entity_scores in sorted(scores.items(),
                                          key=lambda x: x[1].get("name", 0),
                                          reverse=True):
            if entity_scores.get("name", 0) > 20:
                result["name"] = _clean(items[idx][0])
                break

    if not result["position"]:
        for idx, entity_scores in sorted(scores.items(),
                                          key=lambda x: x[1].get("position", 0),
                                          reverse=True):
            if entity_scores.get("position", 0) > 20:
                result["position"] = _clean(items[idx][0])
                break

    # ─── ROUND 5: Final fallback — any remaining text → company ───────────
    if not result["company"]:
        for i, (text, conf, bbox) in enumerate(items):
            if i in classified or i in taken:
                continue
            cleaned = _clean(text)
            if len(cleaned) >= 3:
                result["company"] = cleaned
                break

    # ─── Fill nulls ────────────────────────────────────────────────────────
    return {k: (v if v else "null") for k, v in result.items()}


# ─── LLM Extraction (OpenRouter via OpenAI-compatible API) ────────────────


def extract_with_llm(
    items: List[Tuple[str, float, List[List[float]]]],
    api_key: str,
    model: str = "openai/gpt-4o-mini",
    base_url: str = "https://openrouter.ai/api/v1",
) -> Optional[Dict[str, Optional[str]]]:
    """
    Extract name, position, company using an LLM via OpenRouter.

    Email and phone extraction is NOT done here — regex handles those
    better than any LLM for this task.

    Returns dict with name/position/company, or None on failure.
    """
    if not items:
        return None

    # Sort top-to-bottom for reading order
    sorted_items = sorted(items, key=lambda x: (x[2][0][1], x[2][0][0]))

    # Build a clean text representation
    lines = []
    for i, (text, conf, bbox) in enumerate(sorted_items):
        cleaned = _clean(text)
        if cleaned and conf >= 0.1:
            # Include Y-position hint for spatial context
            y_pos = int(bbox[0][1])
            lines.append(f"  [{i+1}] (y={y_pos}) {cleaned}")

    if not lines:
        return None

    lines_str = "\n".join(lines)

    prompt = f"""You are extracting structured data from a business card.

Below are OCR text lines detected on a business card, shown in reading order
with their approximate vertical position (y=lower means higher on the card).

Extract these three fields:
- name: the person's full name
- position: their job title or role
- company: the organization or company name

Rules:
- Use null for any field you cannot determine.
- If a line could be either a name or a company, prefer company when it
  includes indicators like Inc, LLC, Corp, Ltd, GmbH, Technologies, etc.
- "name" should be a person's name, not a department or division name.
- Return ONLY valid JSON, no markdown, no explanation.

OCR text lines:
{lines_str}"""

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You extract business card fields. Return only JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
            extra_headers={
                "HTTP-Referer": "https://github.com/your-username/card-manager",
                "X-Title": "Card Manager",
            },
        )

        content = response.choices[0].message.content
        if not content:
            return None

        import json

        parsed = json.loads(content)
        return {
            "name": parsed.get("name") or None,
            "position": parsed.get("position") or None,
            "company": parsed.get("company") or None,
        }

    except Exception as e:
        logger.warning(f"LLM extraction failed: {e}")
        return None
