"""Clean text extracted from a PDF so it can be chunked and searched.

PDF text comes out page by page with the page furniture still in it:
running headers and footers, page numbers, words split across lines with a
hyphen, ligature characters (the single glyph "ﬁ" instead of "f" + "i") and
hard line breaks in the middle of sentences. Each function below removes one
of those, and `clean_pages` runs them in order and reports what it removed.
"""
import re
from collections import Counter

LIGATURES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "­": "",  # soft hyphen
}

PAGE_NUMBER = re.compile(r"^\s*(page\s+)?\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE)
HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")


def extract_pages(path):
    """Read a real PDF into one string per page (needs `pip install pypdf`)."""
    from pypdf import PdfReader

    return [page.extract_text() or "" for page in PdfReader(path).pages]


def fix_ligatures(text):
    for glyph, letters in LIGATURES.items():
        text = text.replace(glyph, letters)
    return text


def _shape(line):
    """A line with its digits masked, so 'Page 1 of 4' and 'Page 2 of 4' match."""
    return re.sub(r"\d+", "#", line.strip().lower())


def find_repeated_lines(pages, edge=2, min_share=0.5):
    """Line shapes at the top or bottom of at least `min_share` of pages (and 2+ pages)."""
    if len(pages) < 2:
        return set()
    counts = Counter()
    for page in pages:
        lines = [l for l in page.splitlines() if l.strip()]
        counts.update({_shape(l) for l in lines[:edge] + lines[-edge:]})
    # n >= 2: a line seen on a single page is never "repeated", even in a 2-page file.
    return {s for s, n in counts.items() if n >= 2 and n / len(pages) >= min_share}


def remove_furniture(pages, edge=2, min_share=0.5):
    """Drop repeated headers/footers and bare page numbers. Returns (pages, removed)."""
    repeated = find_repeated_lines(pages, edge, min_share)
    out, removed = [], 0
    for page in pages:
        kept = []
        for line in page.splitlines():
            if line.strip() and (_shape(line) in repeated or PAGE_NUMBER.match(line)):
                removed += 1
                continue
            kept.append(line)
        out.append("\n".join(kept))
    return out, removed


def dehyphenate(text):
    """Join words split across a line break: 'reim-\\nbursement' -> 'reimbursement'."""
    return HYPHEN_BREAK.sub(r"\1\2", text)


def join_lines(text):
    """Turn single line breaks into spaces; a blank line still ends a paragraph."""
    paragraphs = re.split(r"\n\s*\n", text)
    return "\n\n".join(" ".join(p.split()) for p in paragraphs if p.strip())


def glue_pages(pages):
    """Join pages back into one text.

    If a page ends mid-sentence the next page continues the same paragraph
    (single newline); otherwise the page break is a paragraph break.
    """
    text = ""
    for page in pages:
        page = page.strip("\n")
        if not page.strip():
            continue
        if not text:
            text = page
        elif text.rstrip()[-1] in ".!?:":
            text += "\n\n" + page
        else:
            text += "\n" + page
    return text


def clean_pages(pages):
    """Full pipeline. Returns (clean_text, report)."""
    ligatures = sum(p.count(glyph) for p in pages for glyph in LIGATURES)
    pages = [fix_ligatures(p) for p in pages]
    pages, furniture = remove_furniture(pages)
    text = glue_pages(pages)
    hyphen_breaks = len(HYPHEN_BREAK.findall(text))
    text = join_lines(dehyphenate(text))
    report = {
        "ligatures_fixed": ligatures,
        "furniture_lines_removed": furniture,
        "hyphen_breaks_joined": hyphen_breaks,
    }
    return text, report


def chunk_paragraphs(text):
    """One chunk per paragraph (blank-line separated)."""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
