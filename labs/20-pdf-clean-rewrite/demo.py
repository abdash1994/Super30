from pipeline import run

r = run()
print("Cleaning report:", r["report"])
print(f"Chunks: raw {r['raw_chunks']}, clean {r['clean_chunks']}\n")
names = {"raw": "Raw text, question as asked",
         "clean": "Cleaned text, question as asked",
         "clean_rewrite": "Cleaned text, rewritten question"}
for key, label in names.items():
    n = sum(hit for _, hit, _ in r[key])
    print(f"{label}: {n}/{len(r[key])} right")
print()
print(f"{'Question':50} raw   clean  clean+rewrite")
for (q, a, ca), (_, b, _), (_, c, _) in zip(r["raw"], r["clean"], r["clean_rewrite"]):
    mark = lambda x: "yes" if x else "-"
    print(f"{q:50} {mark(a):5} {mark(b):6} {mark(c)}")
print("\nWhat the raw text retrieved for the 'confidential files' question:")
print(" ", r["raw"][4][2])
