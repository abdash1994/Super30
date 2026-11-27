from clean import (
    chunk_paragraphs,
    clean_pages,
    dehyphenate,
    find_repeated_lines,
    fix_ligatures,
    glue_pages,
    join_lines,
    remove_furniture,
)
from handbook import PAGES


def test_ligatures_become_plain_letters():
    assert fix_ligatures("conﬁdential ﬂow eﬀort") == "confidential flow effort"


def test_soft_hyphen_removed():
    assert fix_ligatures("reim­bursement") == "reimbursement"


def test_hyphen_at_line_end_is_joined():
    assert dehyphenate("reim-\nbursement") == "reimbursement"


def test_hyphen_inside_a_line_is_kept():
    assert dehyphenate("two-factor and full-time") == "two-factor and full-time"


def test_join_lines_keeps_paragraphs():
    assert join_lines("one\ntwo\n\nthree\nfour") == "one two\n\nthree four"


def test_repeated_header_and_footer_found_despite_page_numbers():
    shapes = find_repeated_lines(PAGES)
    assert "acme corp employee handbook (v#, #)" in shapes
    assert "confidential - page # of #" in shapes


def test_single_page_has_no_furniture_to_detect():
    assert find_repeated_lines(["Title\nBody\nFooter"]) == set()


def test_bare_page_numbers_removed_even_if_not_repeated():
    pages, removed = remove_furniture(["Body text\n7", "Other text\nPage 8"])
    assert pages == ["Body text", "Other text"]
    assert removed == 2


def test_a_line_that_repeats_only_once_is_kept():
    pages = ["Head\nA\nFoot", "Head\nB\nFoot", "Head\nC\nFoot", "Unique\nD\nEnd"]
    out, _ = remove_furniture(pages, min_share=0.75)
    assert out[0] == "A" and out[3] == "Unique\nD\nEnd"


def test_paragraph_over_a_page_break_is_rejoined():
    text = glue_pages(["Leave. Carers receive 16 weeks of", "full pay."])
    assert join_lines(text) == "Leave. Carers receive 16 weeks of full pay."


def test_page_ending_a_sentence_starts_a_new_paragraph():
    assert glue_pages(["First.", "Second."]) == "First.\n\nSecond."


def test_full_pipeline_on_handbook():
    text, report = clean_pages(PAGES)
    assert report == {
        "ligatures_fixed": 4,
        "furniture_lines_removed": 8,
        "hyphen_breaks_joined": 4,
    }
    assert "Confidential - Page" not in text
    assert "Acme Corp Employee Handbook" not in text
    assert "Expense reimbursement." in text
    assert "ﬁ" not in text
    chunks = chunk_paragraphs(text)
    assert len(chunks) == 10
    assert "16 weeks of full pay and secondary carers" in chunks[7]
