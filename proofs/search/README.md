# Static search proof

COMMONWORLD-ATLAS-V1-T016 is a static browser proof for search over the generated T015 search index input sample.

It loads `examples/commonworld/search-index-input.sample.json` and filters the allowed T014 fields in the browser. It does not introduce a search endpoint, search service, vector database, crawler, ingestion worker, account system, public submissions or weltgewebe write path.

Run it from the repository root with:

```bash
python3 -m http.server 4173
```

Then open `http://localhost:4173/proofs/search/`.
