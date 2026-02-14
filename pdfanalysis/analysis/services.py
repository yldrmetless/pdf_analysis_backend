import urllib.request
import urllib.error
from io import BytesIO
from urllib.parse import quote
import os
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
