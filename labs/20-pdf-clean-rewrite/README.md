# Lab 20: PDF cleaning pipeline plus query rewriting

**Result:** on a 4-page handbook PDF and 10 staff questions, search finds the right paragraph 2/10 times on the raw extracted text, 5/10 after cleaning, and 10/10 after cleaning plus query rewriting; on the raw text, "where should I save confidential files?" returns the page footer "Confidential - Page 1 of 4".

## The problem

A client wants an assistant that answers staff questions from their HR handbook, which lives as a PDF. The first demo looks bad, and it is rarely the model's fault. Two things go wrong before the model is even called:

1. **The text is dirty.** PDF extraction returns what is printed on the page, not the sentences behind it: a running header and a "Page N of 4" footer on every page, words split across lines ("reim-" / "bursement"), ligature glyphs (one character "ﬁ" instead of "f" + "i", so "conﬁdential" no longer matches "confidential"), and paragraphs cut in half by a page break.
2. **People do not ask in the document's words.** Staff say "wfh", "I'm ill", "vacation", "401k"; the handbook says "work from home", "sick leave", "annual leave", "pension".

If retrieval brings back the wrong paragraph, the model will confidently answer from it.

## What this lab does

| File | Job |
| --- | --- |
| `clean.py` | The cleaning pipeline, one function per problem: `fix_ligatures`, `remove_furniture` (headers, footers, page numbers: any line that sits at the top or bottom of at least half the pages, with digits masked so "Page 1" and "Page 2" count as the same line), `glue_pages` (a page that ends mid-sentence continues on the next one), `dehyphenate`, `join_lines`. `clean_pages` runs them in order and returns a report of what it removed. `extract_pages` reads a real PDF with `pypdf`. |
| `rewrite.py` | Two query rewriters with the same output (a list of queries, original first): `rule_rewrite` uses a glossary the client owns; `llm_rewrite` asks a model for up to 3 search queries as JSON, validates the reply and falls back to the original question if the reply is not usable. |
| `retrieve.py` | A small keyword retriever (rare words count more) standing in for BM25 or a vector search. With several queries a paragraph keeps its best score. |
| `handbook.py` | The 4 pages as an extractor returns them, the glossary, and 10 questions, each with a phrase that only appears in the answering paragraph. |
| `pipeline.py`, `demo.py` | Score the 10 questions three ways and print the table. |
| `test_clean.py`, `test_rewrite_retrieve.py` | 27 tests: each cleaning step, the rewriters (the LLM is a fake function, so no key or network), the retriever, and the headline numbers. |

`python demo.py` output:

| Question | Raw text | Cleaned | Cleaned + rewrite |
| --- | --- | --- | --- |
| Can I wfh on Fridays? | - | - | yes |
| How do I get reimbursement for a client dinner? | yes | yes | yes |
| How many days off do I get when I'm ill? | - | - | yes |
| My computer was stolen, what now? | - | - | yes |
| Where should I save confidential files? | - (got the footer) | yes | yes |
| What are the password rules? | - | yes | yes |
| How much vacation do I get? | - | - | yes |
| How long is maternity leave? | - | - | yes |
| Is there money for an online course? | yes | yes | yes |
| Does Acme match my 401k? | - | yes | yes |
| **Total** | **2/10** | **5/10** | **10/10** |

Cleaning fixed 4 ligatures, removed 8 header/footer lines and joined 4 split words; the text went from 17 chunks (6 of them nothing but a header or footer, and the parental-leave paragraph cut in two with a footer and header glued on) to 10 whole paragraphs. Cleaning fixes the questions that use the document's own words; rewriting fixes the ones that do not.

One more test shows the glossary's limit: "We are having a baby in March, how much time off can I take?" uses no glossary word, so the rule rewriter finds the remote-work paragraph (it matched "time"). A (mocked) LLM rewrite to "parental leave weeks full pay" finds the right one.

## Run it

```bash
pip install -r requirements.txt
pytest -q          # 27 tests, standard library only
python demo.py     # prints the table above
```

For a real PDF: `pip install pypdf`, then `from clean import extract_pages, clean_pages; text, report = clean_pages(extract_pages("handbook.pdf"))`.

## Why it matters to a business

"The AI gives wrong answers" is often a data-preparation problem that looks like a model problem. Cleaning the source once is cheap and helps every question afterwards; here it more than doubled the right answers before any model was involved. The glossary is something the client already knows (their own jargon) and can own and edit without an engineer. And a 10-question eval with a "right paragraph?" check turns "it feels better" into a number to show at the next review, and to re-run when the handbook changes.

## Trade-off

Cleaning rules are guesses about layout. Joining a hyphen at a line end also joins real compound words that happen to break there ("full-" / "time" becomes "fulltime"); the header rule can delete a real line that repeats on most pages (a legal notice someone needs); tables and two-column layouts need a proper layout-aware extractor, not these rules. So keep the cleaning report and look at it per document type.

Rewriting trades predictability for reach. The glossary is free, instant and explainable, but only knows what is listed, and the 10/10 here is on questions the glossary was written for, so it is the ceiling, not a forecast: real questions need a held-out set. An LLM rewrite handles wording nobody listed but adds a model call per question (cost and latency) and can drift away from what was asked, which is why the original question is always kept and bad output falls back to it.
