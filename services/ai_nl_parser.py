"""
SplitSmart Natural-Language Expense Parser (AI Feature 1)
Leverages Google Gemini API (gemini-2.0-flash / gemini-1.5-flash) with structured JSON output
to extract expense descriptions, amounts, payers, and participant splits from plain text.
Includes advanced fuzzy name-matching against group members using difflib to resolve IDs,
plus deterministic heuristic fallback if the API key is not configured or in offline mode.
"""

import os
import re
import json
import logging
import difflib
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

CENT = Decimal('0.01')


def _clean_member_roster(roster: List[Any]) -> List[Dict[str, Any]]:
    """Normalizes member roster into list of {'id': int, 'name': str}."""
    normalized = []
    for item in roster:
        if isinstance(item, dict):
            m_id = item.get("id") or item.get("member_id")
            name = item.get("display_name") or item.get("name") or str(m_id)
            normalized.append({"id": m_id, "name": str(name).strip()})
        elif isinstance(item, str):
            normalized.append({"id": None, "name": item.strip()})
        else:
            normalized.append({"id": None, "name": str(item)})
    return normalized


def fuzzy_match_member(candidate: str, roster: List[Dict[str, Any]], cutoff: float = 0.6) -> Optional[Dict[str, Any]]:
    """
    Advanced multi-strategy fuzzy matcher to match a candidate name against group member roster:
    1. Exact match (case-insensitive)
    2. Substring containment ('Rahul' in 'Rahul Verma', 'Ramesh' in 'Uncle Ramesh')
    3. Token-level overlap (first name / last name match)
    4. SequenceMatcher / difflib close matches for typos (e.g. 'Rahuul' -> 'Rahul')
    """
    if not candidate or not roster:
        return None

    cand_lower = candidate.strip().lower()
    cand_tokens = set(re.findall(r'\w+', cand_lower))

    # 1. Exact match
    for m in roster:
        if m["name"].lower() == cand_lower:
            return m

    # 2. Substring match
    for m in roster:
        name_lower = m["name"].lower()
        if cand_lower in name_lower or name_lower in cand_lower:
            return m

    # 3. Token-level match (e.g. 'Aman' in 'Aman Sharma')
    for m in roster:
        m_tokens = set(re.findall(r'\w+', m["name"].lower()))
        if cand_tokens and m_tokens and (cand_tokens.issubset(m_tokens) or m_tokens.issubset(cand_tokens)):
            return m

    # 4. difflib SequenceMatcher fuzzy match
    best_match = None
    best_score = 0.0

    for m in roster:
        name_lower = m["name"].lower()
        # Direct string similarity
        score = difflib.SequenceMatcher(None, cand_lower, name_lower).ratio()
        if score > best_score and score >= cutoff:
            best_score = score
            best_match = m

        # Token-to-token similarity
        for tok in re.findall(r'\w+', name_lower):
            tok_score = difflib.SequenceMatcher(None, cand_lower, tok).ratio()
            if tok_score > best_score and tok_score >= cutoff:
                best_score = tok_score
                best_match = m

    return best_match


def parse_expense_text(
    text: str,
    group_member_roster: Optional[List[Any]] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Parses a natural language expense prompt into structured expense fields.
    Resolves member names to IDs using fuzzy matching against group_member_roster.
    
    Args:
        text: Natural language string (e.g. "Rahul paid 1200 for beach dinner for everyone")
        group_member_roster: List of group member dicts or names
        api_key: Optional Gemini API key override (defaults to GEMINI_API_KEY env var)
        
    Returns:
        Dict:
        {
            "description": str,
            "amount": Decimal,
            "payer_name": str,
            "payer_id": Optional[int],
            "split_members": List[str],
            "split_member_ids": List[int],
            "split_type": str,
            "confidence": str
        }
    """
    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("Expense text prompt cannot be empty.")

    roster = _clean_member_roster(group_member_roster or [])
    roster_names = [m["name"] for m in roster]

    gemini_key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()

    parsed_result = None

    # 1. Attempt Gemini Structured Extraction if API key is present
    if gemini_key:
        try:
            parsed_result = _call_gemini_nlp(clean_text, roster_names, gemini_key)
        except Exception as e:
            logger.warning("Gemini NLP call failed, falling back to heuristic parser: %s", e)

    # 2. If Gemini unavailable or failed, use heuristic NLP fallback
    if not parsed_result:
        parsed_result = _heuristic_nlp_parse(clean_text, roster_names)

    # 3. Post-process and resolve member IDs from candidate names using fuzzy matching
    desc = parsed_result.get("description", "Expense").strip()
    raw_amount = parsed_result.get("amount", 0.0)
    try:
        amount_dec = Decimal(str(raw_amount)).quantize(CENT, rounding=ROUND_HALF_UP)
    except Exception:
        amount_dec = Decimal('0.00')

    payer_candidate = str(parsed_result.get("payer_name") or "").strip()
    split_type = parsed_result.get("split_type", "EQUAL").upper()
    if split_type not in ("EQUAL", "EXACT", "PERCENTAGE", "SHARES", "ITEMIZED"):
        split_type = "EQUAL"

    # Fuzzy match payer against roster
    matched_payer = fuzzy_match_member(payer_candidate, roster)
    payer_name = matched_payer["name"] if matched_payer else payer_candidate
    payer_id = matched_payer["id"] if matched_payer else None

    # Fuzzy match split participants
    raw_splits = parsed_result.get("split_members", [])
    resolved_split_names = []
    resolved_split_ids = []

    is_everyone = (
        not raw_splits or
        any(x.lower() in ("everyone", "all", "all members", "everybody") for x in raw_splits)
    )

    if is_everyone and roster:
        for m in roster:
            resolved_split_names.append(m["name"])
            if m["id"] is not None:
                resolved_split_ids.append(m["id"])
    else:
        for item in raw_splits:
            m = fuzzy_match_member(str(item), roster)
            if m:
                if m["name"] not in resolved_split_names:
                    resolved_split_names.append(m["name"])
                    if m["id"] is not None:
                        resolved_split_ids.append(m["id"])
            else:
                if item not in resolved_split_names:
                    resolved_split_names.append(item)

    return {
        "description": desc or "Expense",
        "amount": amount_dec,
        "payer_name": payer_name,
        "payer_id": payer_id,
        "split_members": resolved_split_names,
        "split_member_ids": resolved_split_ids,
        "split_type": split_type,
        "confidence": parsed_result.get("confidence", "high")
    }


def _call_gemini_nlp(text: str, roster_names: List[str], api_key: str) -> Optional[Dict[str, Any]]:
    """Calls Gemini API using google.genai client with structured JSON output."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        prompt = f"""
You are an expert expense parser for SplitSmart.
Extract the expense details from the following user prompt:
"{text}"

Available group members: {json.dumps(roster_names)}

Output strictly valid JSON with this exact schema:
{{
  "description": "Short title of expense (e.g. 'Beach shack dinner')",
  "amount": 1200.00,
  "payer_name": "Name of the person who paid",
  "split_members": ["List of member names who share this expense, or ['everyone'] if all"],
  "split_type": "EQUAL"
}}
"""
        model_candidates = [
            "gemini-flash-lite-latest",
            "gemini-3.5-flash",
            "gemini-3-flash-preview",
            "gemini-3.8-flash"
        ]
        for model_name in model_candidates:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                if response and response.text:
                    raw = response.text.strip()
                    if "```json" in raw:
                        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
                    elif "```" in raw:
                        raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
                    
                    data = None
                    try:
                        data = json.loads(raw)
                    except Exception:
                        s = raw.find('{')
                        e = raw.rfind('}')
                        if s != -1 and e > s:
                            data = json.loads(raw[s:e+1])
                    if data and isinstance(data, dict):
                        data["confidence"] = "gemini_ai"
                        return data
            except Exception as e:
                logger.warning("Error with model %s in ai_nl_parser: %s", model_name, e)
    except Exception as e:
        logger.warning("Error initializing genai client: %s", e)

    return None


def _heuristic_nlp_parse(text: str, roster_names: List[str]) -> Dict[str, Any]:
    """
    Deterministic rule-based NLP extraction when offline or API key is not supplied.
    Handles patterns like:
    - 'Rahul paid 1200 for beach dinner for everyone'
    - 'Pooja paid 500 for groceries split between Pooja and Aman'
    - 'Paid 450 for coffee'
    """
    clean = text.strip()

    # 1. Extract Payer first using fuzzy matching against roster
    payer = ""
    for r_name in sorted(roster_names, key=len, reverse=True):
        if re.search(r'\b' + re.escape(r_name) + r'\b', clean, re.IGNORECASE):
            payer = r_name
            break

    if not payer:
        payer_pattern = re.search(r'([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+(?:paid|spent|covered)', clean, re.IGNORECASE)
        if payer_pattern:
            cand = payer_pattern.group(1).strip()
            matched = fuzzy_match_member(cand, [{"id": idx, "name": n} for idx, n in enumerate(roster_names)])
            payer = matched["name"] if matched else cand

    # Remove payer string from text to avoid numbers in username being treated as amount
    text_without_payer = clean
    if payer:
        text_without_payer = re.sub(re.escape(payer), '', clean, flags=re.IGNORECASE)

    # 2. Extract Amount
    amount = 0.0
    amt_match = re.search(r'(?:₹|rs\.?|inr|\$)\s*(\d+(?:\.\d{1,2})?)', text_without_payer, re.IGNORECASE)
    if not amt_match:
        amt_match = re.search(r'(?:paid|spent|cost)\s*(?:₹|rs\.?|inr|\$)?\s*(\d+(?:\.\d{1,2})?)', text_without_payer, re.IGNORECASE)
    if not amt_match:
        amt_match = re.search(r'\b(\d+(?:\.\d{1,2})?)\b', text_without_payer)

    if amt_match:
        try:
            amount = float(amt_match.group(1))
        except ValueError:
            amount = 0.0

    # 3. Extract Description
    desc = "Expense"
    for_match = re.search(r'\bfor\s+([^,]+?)(?:\s+(?:for\s+everyone|for\s+all|split|between|with)|\s*$)', clean, re.IGNORECASE)
    if for_match:
        desc_cand = for_match.group(1).strip()
        desc_cand = re.sub(r'^(?:₹|rs\.?|inr|\$)?\s*\d+(?:\.\d{1,2})?\s*', '', desc_cand).strip()
        if desc_cand:
            desc = desc_cand.capitalize()
    else:
        rem = re.sub(r'(?:₹|rs\.?|inr|\$)?\s*\d+(?:\.\d{1,2})?', '', clean, flags=re.IGNORECASE)
        rem = re.sub(r'\b(?:paid|spent|covered|for|split|between|everyone|all)\b', '', rem, flags=re.IGNORECASE)
        if payer:
            rem = re.sub(re.escape(payer), '', rem, flags=re.IGNORECASE)
        rem = rem.strip()
        if rem:
            desc = rem.capitalize()

    # 4. Extract Split Members
    split_members = []
    if re.search(r'\b(?:everyone|everybody|all|all members)\b', clean, re.IGNORECASE):
        split_members = roster_names if roster_names else ["everyone"]
    else:
        between_match = re.search(r'\b(?:between|with|split between|split with)\s+(.+)$', clean, re.IGNORECASE)
        if between_match:
            cand_str = between_match.group(1)
            tokens = re.split(r'[,&]|\band\b', cand_str)
            for t in tokens:
                t_clean = t.strip()
                if t_clean:
                    m = fuzzy_match_member(t_clean, [{"id": idx, "name": n} for idx, n in enumerate(roster_names)])
                    if m:
                        split_members.append(m["name"])
                    else:
                        split_members.append(t_clean)
        else:
            split_members = roster_names if roster_names else ["everyone"]

    return {
        "description": desc,
        "amount": amount,
        "payer_name": payer,
        "split_members": split_members,
        "split_type": "EQUAL",
        "confidence": "heuristic"
    }
