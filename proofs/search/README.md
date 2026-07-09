# Static search proof

COMMONWORLD-ATLAS-V1-T016 is a static browser proof for search over the generated T015 search index input sample.

It loads `examples/commonworld/search-index-input.sample.json`, filters the allowed T014 fields in the browser and shows transparent match reasons with a local proof score. It does not introduce a search endpoint, search service, vector database, crawler, ingestion worker, account system, public submissions or weltgewebe write path.

Run it from the repository root with:

```bash
python3 -m http.server 4173
```

Then open `http://localhost:4173/proofs/search/`.

T017 adds explainable local match reasons. The score is a browser-only proof aid, not a server ranking, curation decision or authority signal.

T018 adds `examples/commonworld/search-query-fixtures.sample.json`, a static query fixture set for representative searches such as repair, open data, Hamburg, mutual aid and exact venue lookup. These fixtures test quality drift without adding a search runtime.
