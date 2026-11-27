"""A 4-page employee handbook as a PDF extractor returns it, plus 10 questions.

The page text is hand-made but reproduces what real extraction produces:
a running header and a "Page N of 4" footer on every page, words hyphenated
across lines, ligature glyphs (\\ufb01 = "fi"), hard line breaks, and one
paragraph that runs over a page break. Each question lists a phrase that only
appears in the paragraph that answers it, so a hit is checked by that phrase.
"""

HEADER = "Acme Corp Employee Handbook (v3, 2026)"


def footer(n):
    return f"Confidential - Page {n} of 4"


PAGES = [
    f"""{HEADER}

Remote work. Staff may work from home up to 3 days per week
with their manager's ap-
proval. Core hours are 10:00 to 16:00 local time.

Expense reim-
bursement. Submit receipts within 30 days through the
ﬁnance portal. Meals are reimbursed up to $75 per day
when travelling for a client.

{footer(1)}""",
    f"""{HEADER}

Sick leave. Employees receive 10 paid sick days a year. Tell
your manager before 09:30 on the ﬁrst day of absence.

Equipment. New starters get a laptop on day one. Lost or
damaged equipment must be reported to IT within 24 hours.

Conﬁdential ﬁles must be stored on the shared drive,
never on personal USB sticks.

{footer(2)}""",
    f"""{HEADER}

Pass-
words. Use a pass-
word manager and turn on two-factor authentication for all
work accounts.

Annual leave. Full-time staff get 25 days of annual leave plus
public holidays. Up to 5 unused days carry into next year.

Parental leave. Primary carers receive 16 weeks of
{footer(3)}""",
    f"""{HEADER}
full pay and secondary carers receive 4 weeks of full pay.

Learning budget. Every employee has $1,000 a year for
courses, books and conferences.

Pension. Acme matches pension contributions up to 5% of salary.

{footer(4)}""",
]

# The client's own glossary: how staff talk -> words the handbook uses.
GLOSSARY = {
    "wfh": "work from home remote",
    "ill": "sick leave",
    "unwell": "sick leave",
    "computer": "laptop equipment",
    "stolen": "lost",
    "vacation": "annual leave holiday",
    "pto": "annual leave paid time off",
    "maternity": "parental leave",
    "paternity": "parental leave",
    "401k": "pension",
    "retirement": "pension",
    "2fa": "two-factor authentication",
}

# (question, phrase found only in the answering paragraph)
QUESTIONS = [
    ("Can I wfh on Fridays?", "3 days per week"),
    ("How do I get reimbursement for a client dinner?", "30 days"),
    ("How many days off do I get when I'm ill?", "10 paid sick days"),
    ("My computer was stolen, what now?", "24 hours"),
    ("Where should I save confidential files?", "shared drive"),
    ("What are the password rules?", "password manager"),
    ("How much vacation do I get?", "25 days"),
    ("How long is maternity leave?", "16 weeks"),
    ("Is there money for an online course?", "$1,000"),
    ("Does Acme match my 401k?", "5% of salary"),
]
