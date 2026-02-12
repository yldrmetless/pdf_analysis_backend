import urllib.request
import urllib.error
from io import BytesIO
from urllib.parse import quote
import re
from documents.models import DocumentChunk
import os, json
from openai import OpenAI, RateLimitError

import pdfplumber

def download_pdf_bytes_from_supabase(file_path: str) -> bytes:
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    bucket = os.getenv("SUPABASE_BUCKET", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not bucket or not key:
        raise ValueError("SUPABASE_URL / SUPABASE_BUCKET / SUPABASE_SERVICE_ROLE_KEY eksik.")

    safe_path = quote(file_path.lstrip("/"), safe="/")

    url = f"{supabase_url}/storage/v1/object/authenticated/{bucket}/{safe_path}"

    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {key}"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise ValueError(f"SUPABASE DOWNLOAD error {e.code}: {body}")


def extract_first_pages_text(pdf_bytes: bytes, max_pages: int = 2) -> tuple[int, str]:
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        page_count = len(pdf.pages)
        n = min(max_pages, page_count)
        texts = []
        for i in range(n):
            page = pdf.pages[i]

            t = (page.extract_text(layout=False, x_tolerance=2, y_tolerance=2) or "").strip()

            if t:
                texts.append(t)

        return page_count, "\n\n".join(texts).strip()
    
    

def extract_full_text_pages(pdf_bytes: bytes, max_pages: int = 50):
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        page_count = len(pdf.pages)
        n = min(page_count, max_pages)
        pages = []
        for i in range(n):
            page = pdf.pages[i]

            t = (page.extract_text(layout=False, x_tolerance=2, y_tolerance=2) or "").strip()
            pages.append(t)

        return page_count, pages



STOPWORDS = {
    "ve", "ile", "bir", "bu", "şu", "o", "da", "de", "mi", "mı", "mu", "mü",
    "the", "a", "an", "and", "or", "to", "of", "in", "for", "on", "is", "are"
}

def _tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    tokens = re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]+", text)
    return [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]

def retrieve_top_chunks(document_id: int, question: str, top_k: int = 4):
    q_tokens = set(_tokenize(question))
    if not q_tokens:
        return []

    chunks = (DocumentChunk.objects
              .filter(document_id=document_id)
              .only("chunk_index", "page_start", "page_end", "text")
              .order_by("chunk_index"))

    scored = []
    for c in chunks:
        c_tokens = set(_tokenize(c.text))
        score = len(q_tokens.intersection(c_tokens))
        if score > 0:
            scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]

def build_context(chunks, max_chars: int = 8000) -> str:
    parts = []
    total = 0
    for c in chunks:
        block = f"[chunk {c.chunk_index} | pages {c.page_start}-{c.page_end}]\n{(c.text or '').strip()}\n"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts).strip()

def answer_mock(question: str, chunks) -> str:
    if not chunks:
        return "Bu soruyu yanıtlayacak yeterli içerik bulunamadı. (Mock mode)"
    return f"(Mock) Soru: {question}\n\nBulunan içerik parça sayısı: {len(chunks)}"

def answer_with_openai(question: str, context: str) -> str:

    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not api_key:
        raise ValueError("OPENAI_API_KEY eksik.")

    client = OpenAI(api_key=api_key)

    system = (
        "You are a helpful document analyst. Answer ONLY using the provided context. "
        "If the answer is not in the context, say you can't find it."
    )

    user = f"QUESTION:\n{question}\n\nCONTEXT:\n{context}"

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()






def analyze_document_with_openai(full_text: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not api_key:
        raise ValueError("OPENAI_API_KEY eksik.")

    client = OpenAI(api_key=api_key)

    system = (
        "You are a document analyst. "
        "You will analyze ANY type of document (resume, contract, invoice, report, etc.). "
        "Return ONLY valid JSON. No markdown."
    )

    user_payload = {
        "task": "Analyze the document and return a structured JSON.",
        "output_schema": {
            "doc_type": "string",               # resume|contract|invoice|report|academic|unknown...
            "language": "string",               # tr|en|mixed|unknown
            "summary": "string",
            "key_points": ["string"],
            "entities": [{"type": "string", "value": "string"}],  # person|org|location|product|...
            "dates": ["string"],
            "numbers": [{"label": "string", "value": "string"}],  # amount, % etc.
            "action_items": ["string"],
            "sections": [{"title": "string", "content": "string"}]
        },
        "text": full_text[:60000]  # güvenlik: çok uzunsa kırp
    }

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        temperature=0.2,
    )

    content = (resp.choices[0].message.content or "").strip()
    return json.loads(content)