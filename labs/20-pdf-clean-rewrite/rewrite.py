"""Query rewriting: turn the way people ask into the words the document uses.

Two rewriters with the same output shape (a list of queries to search):
- `rule_rewrite`: a glossary the client owns (abbreviations, everyday words
  to policy words). Free, instant, predictable, but only knows what is listed.
- `llm_rewrite`: asks a model for up to 3 search queries as JSON. Handles
  phrasings nobody listed, but costs a call, adds latency and can drift, so
  its output is validated and the original query is always kept.
"""
import json
import re

FILLER = re.compile(
    r"\b(hey|hi|please|can you tell me|could you tell me|i want to know|quick question)\b[,:]?",
    re.IGNORECASE,
)


def rule_rewrite(query, glossary):
    """Return [cleaned original, expanded version]; just one if nothing matched."""
    base = " ".join(FILLER.sub(" ", query).split())
    words = re.findall(r"[a-z0-9]+", base.lower())
    additions = []
    for term, expansion in glossary.items():
        term_words = term.split()
        n = len(term_words)
        if any(words[i : i + n] == term_words for i in range(len(words) - n + 1)):
            additions.append(expansion)
    if not additions:
        return [base]
    return [base, base + " " + " ".join(additions)]


PROMPT = """Rewrite the user's question into at most 3 short search queries that use
the words a company HR policy document would use. Reply with JSON only:
{{"queries": ["...", "..."]}}

Question: {query}"""


def llm_rewrite(query, llm, max_queries=3):
    """`llm` is any callable prompt -> text. Bad output falls back to [query]."""
    try:
        data = json.loads(llm(PROMPT.format(query=query)))
        queries = data["queries"]
    except (ValueError, TypeError, KeyError):
        return [query]
    if not isinstance(queries, list):
        return [query]
    good = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
    good = [q for q in good if q.lower() != query.lower()]
    return [query] + good[:max_queries]
