import json
import os

from openai import OpenAI

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
                    "properties": {
                        "type": {"type": "string"},
                        "value": {"type": "string"},
                    },
                    "required": ["type", "value"],
                },
            },
            "dates": {"type": "array", "items": {"type": "string"}},
            "numbers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "label": {"type": "string"},
                        "value": {"type": "string"},
                    },
                    "required": ["label", "value"],
                },
            },
            "action_items": {"type": "array", "items": {"type": "string"}},
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["title", "content"],
                },
            },
        },
        "required": [
            "doc_type",
            "language",
            "summary",
            "key_points",
            "entities",
            "dates",
            "numbers",
            "action_items",
            "sections",
        ],
    },
}


def analyze_document_with_openai(full_text: str) -> tuple[str, dict]:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    system = """
      You are a document analysis assistant. Analyze the given document and return ONLY valid JSON.
      First, detect the document type (e.g. CV/resume, report, article, legal document, invoice, letter, etc.).

      Always include these top-level keys:
      - doc_type (string: detected document type)
      - summary (string: brief summary of the document)
      - key_points (list of strings: main takeaways)
      - sections (list of {title, content}: document sections you identified)

      If the document is a CV/resume, also include:
      - contact_information (email, github, linkedin, phone, etc.)
      - personal_profile (description)
      - work_experience (list)
      - education (list)
      - skills (list)
      - references (list)

      For non-CV documents, include relevant extracted fields based on document type:
      - entities (list of {type, value}: people, organizations, locations, etc.)
      - dates (list of strings)
      - numbers (list of {label, value}: monetary amounts, statistics, etc.)
      - action_items (list of strings, if applicable)

      Rules:
      - Output must be valid JSON.
      - Do NOT include a "suggestions" key. Suggestions are handled separately.
      - Adapt your extraction to the actual document type. Do not force CV fields onto non-CV documents.
      """

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system.strip()},
            {"role": "user", "content": full_text[:120000]},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=2000,
    )

    raw = (resp.choices[0].message.content or "").strip()
    parsed = json.loads(raw)

    # garanti
    if "suggestions" not in parsed or not isinstance(parsed.get("suggestions"), list):
        parsed["suggestions"] = []

    return raw, parsed


def generate_suggestions_en(full_text: str) -> tuple[str, dict]:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    system = """
    You are a professional document reviewer. Read the entire document carefully and provide an overall quality assessment.

    Return ONLY valid JSON:
    {
      "suggestions": ["suggestion 1", "suggestion 2", ...]
    }

    Rules:
    - Return 3 to 5 suggestions as plain strings (NOT objects).
    - Each suggestion should be a single, clear sentence about how to improve the OVERALL document.
    - Evaluate the document holistically: overall clarity, readability, structure, tone, completeness, and presentation quality.
    - Do NOT give section-by-section or field-by-field advice.
    - Do NOT suggest adding specific sections, links, URLs, or templates.
    - Do NOT give generic CV/resume tips. Treat this as any document.
    - Suggestions must be specific to THIS document's actual content and quality.
    - If the document is already high quality, say so and give fewer suggestions.
    - English only.

    Example output:
    {
      "suggestions": [
        "The document would benefit from more consistent formatting between sections, as font sizes and spacing vary throughout.",
        "Several claims lack supporting evidence or quantifiable results, which weakens the overall persuasiveness.",
        "The opening section could be more concise — it repeats information that appears later in the document."
      ]
    }
    """

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system.strip()},
            {"role": "user", "content": full_text[:80000]},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=1200,
    )

    raw = (resp.choices[0].message.content or "").strip()
    parsed = json.loads(raw)

    if "suggestions" not in parsed or not isinstance(parsed.get("suggestions"), list):
        parsed["suggestions"] = []

    print(">>> SUGG_RAW_HEAD:", raw[:120])
    print(">>> SUGG_COUNT:", len(parsed.get("suggestions", [])))
    return raw, parsed
