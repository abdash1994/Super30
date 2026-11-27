"""Score retrieval on the 10 handbook questions under three setups."""
from clean import chunk_paragraphs, clean_pages
from handbook import GLOSSARY, PAGES, QUESTIONS
from retrieve import Index
from rewrite import rule_rewrite


def raw_chunks(pages):
    """What you get if you skip cleaning: raw page text split on blank lines."""
    return chunk_paragraphs("\n\n".join(pages))


def hits(chunks, rewrite=None, questions=QUESTIONS):
    """Return a list of (question, hit?, retrieved chunk or None)."""
    index = Index(chunks)
    results = []
    for question, expect in questions:
        queries = rewrite(question) if rewrite else [question]
        i = index.search(queries)
        chunk = None if i is None else chunks[i]
        results.append((question, chunk is not None and expect in chunk, chunk))
    return results


def run(pages=PAGES, glossary=GLOSSARY):
    clean_text, report = clean_pages(pages)
    clean = chunk_paragraphs(clean_text)
    rewrite = lambda q: rule_rewrite(q, glossary)
    return {
        "report": report,
        "raw_chunks": len(raw_chunks(pages)),
        "clean_chunks": len(clean),
        "raw": hits(raw_chunks(pages)),
        "clean": hits(clean),
        "clean_rewrite": hits(clean, rewrite),
    }
