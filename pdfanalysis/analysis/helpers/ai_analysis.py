import os
import json
import time
from openai import OpenAI, RateLimitError


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

JSON_SCHEMA = {
  "name": "doc_analysis",
  "schema": {
    "type": "object",
    "additionalProperties": False,
    "properties": {
      "doc_type": {"type": "string"},
      "language": {"type": "string"},
      "summary": {"type": "string"},
      "key_points": {"type": "array", "items": {"type": "string"}},
      "entities": {
        "type": "array",
        "items": {
          "type": "object",
          "additionalProperties": False,
          "properties": {"type": {"type": "string"}, "value": {"type": "string"}},
          "required": ["type", "value"]
        }
      },
      "dates": {"type": "array", "items": {"type": "string"}},
      "numbers": {
        "type": "array",
        "items": {
          "type": "object",
          "additionalProperties": False,
          "properties": {"label": {"type": "string"}, "value": {"type": "string"}},
          "required": ["label", "value"]
        }
      },
      "action_items": {"type": "array", "items": {"type": "string"}},
      "sections": {
        "type": "array",
        "items": {
          "type": "object",
          "additionalProperties": False,
          "properties": {"title": {"type": "string"}, "content": {"type": "string"}},
          "required": ["title", "content"]
        }
      }
    },
    "required": ["doc_type","language","summary","key_points","entities","dates","numbers","action_items","sections"]
  }
}


def analyze_document_with_openai(full_text: str) -> tuple[str, dict]:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Return ONLY valid JSON object."},
            {"role": "user", "content": full_text[:120000]},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=2000,
    )

    raw = (resp.choices[0].message.content or "").strip()
    parsed = json.loads(raw)  # JSON değilse burada FAIL olacak
    return raw, parsed