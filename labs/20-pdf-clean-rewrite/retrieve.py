"""A tiny keyword retriever (stand-in for BM25 or a vector search).

Score of a chunk = sum of IDF weights of the query words it contains, so rare
words count more than common ones. With several queries, a chunk keeps its
best score across them.
"""
import math
import re

STOPWORDS = set(
    "a an and are at be can do does for from get how i if in is it me my of off on or "
    "our should the to what when where which who will with you your much many there "
    "this that was were am".split()
)


def tokens(text):
    out = []
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in STOPWORDS:
            continue
        if len(word) > 4 and word.endswith("s"):
            word = word[:-1]  # crude plural fold: "files" -> "file"
        out.append(word)
    return out


class Index:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.sets = [set(tokens(c)) for c in self.chunks]
        n = len(self.chunks)
        df = {}
        for s in self.sets:
            for w in s:
                df[w] = df.get(w, 0) + 1
        self.idf = {w: math.log(1 + n / d) for w, d in df.items()}

    def score(self, query, i):
        return sum(self.idf.get(w, 0.0) for w in set(tokens(query)) if w in self.sets[i])

    def search(self, queries):
        """Index of the best chunk for any of `queries`, or None if nothing matches."""
        if isinstance(queries, str):
            queries = [queries]
        best, best_score = None, 0.0
        for i in range(len(self.chunks)):
            s = max(self.score(q, i) for q in queries)
            if s > best_score:
                best, best_score = i, s
        return best
