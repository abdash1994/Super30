import json

from clean import chunk_paragraphs, clean_pages
from handbook import GLOSSARY, PAGES
from pipeline import run
from retrieve import Index, tokens
from rewrite import llm_rewrite, rule_rewrite


def clean_index():
    text, _ = clean_pages(PAGES)
    chunks = chunk_paragraphs(text)
    return Index(chunks), chunks


# --- rule rewrite ---------------------------------------------------------

def test_rule_rewrite_expands_abbreviation():
    assert rule_rewrite("Can I wfh?", GLOSSARY) == ["Can I wfh?", "Can I wfh? work from home remote"]


def test_rule_rewrite_strips_filler():
    assert rule_rewrite("Hey, please tell me about pensions", {}) == ["tell me about pensions"]


def test_rule_rewrite_matches_whole_words_only():
    # "ill" must not fire inside "will" or "bill"
    assert rule_rewrite("Who will pay the bill?", GLOSSARY) == ["Who will pay the bill?"]


def test_rule_rewrite_keeps_original_first():
    queries = rule_rewrite("How much vacation?", GLOSSARY)
    assert queries[0] == "How much vacation?"
    assert "annual leave" in queries[1]


# --- LLM rewrite (model mocked) ------------------------------------------

def test_llm_rewrite_uses_model_queries_and_keeps_original():
    fake = lambda prompt: json.dumps({"queries": ["parental leave", "maternity weeks"]})
    assert llm_rewrite("baby due", fake) == ["baby due", "parental leave", "maternity weeks"]


def test_llm_rewrite_prompt_contains_question():
    seen = []
    llm_rewrite("my question", lambda p: seen.append(p) or '{"queries": []}')
    assert "Question: my question" in seen[0]


def test_llm_rewrite_caps_number_of_queries():
    fake = lambda p: json.dumps({"queries": ["a", "b", "c", "d", "e"]})
    assert llm_rewrite("q", fake) == ["q", "a", "b", "c"]


def test_llm_rewrite_falls_back_on_bad_output():
    assert llm_rewrite("q", lambda p: "Sure! Here are some queries:") == ["q"]
    assert llm_rewrite("q", lambda p: '{"answer": "x"}') == ["q"]
    assert llm_rewrite("q", lambda p: '{"queries": "not a list"}') == ["q"]
    assert llm_rewrite("q", lambda p: '{"queries": [1, null, "  "]}') == ["q"]


def test_llm_rewrite_rescues_a_question_the_glossary_misses():
    index, chunks = clean_index()
    question = "We are having a baby in March, how much time off can I take?"
    wrong = index.search(rule_rewrite(question, GLOSSARY))
    assert not chunks[wrong].startswith("Parental leave")
    fake = lambda p: json.dumps({"queries": ["parental leave weeks full pay"]})
    right = index.search(llm_rewrite(question, fake))
    assert chunks[right].startswith("Parental leave")


# --- retriever ------------------------------------------------------------

def test_tokens_drop_stopwords_and_fold_plurals():
    assert tokens("Where are the files?") == ["file"]


def test_search_returns_none_when_nothing_matches():
    index, _ = clean_index()
    assert index.search("zebra xylophone") is None


def test_search_takes_best_of_several_queries():
    index, chunks = clean_index()
    i = index.search(["zebra", "pension"])
    assert chunks[i].startswith("Pension")


# --- the measured result (README numbers) ---------------------------------

def score(results):
    return sum(hit for _, hit, _ in results)


def test_headline_numbers():
    r = run()
    assert (score(r["raw"]), score(r["clean"]), score(r["clean_rewrite"])) == (2, 5, 10)


def test_raw_text_returns_a_footer_for_confidential_files():
    r = run()
    question, hit, chunk = r["raw"][4]
    assert "confidential" in question.lower()
    assert not hit and chunk == "Confidential - Page 1 of 4"


def test_every_step_helps_never_hurts():
    r = run()
    for raw, clean, both in zip(r["raw"], r["clean"], r["clean_rewrite"]):
        assert clean[1] >= raw[1]
        assert both[1] >= clean[1]
