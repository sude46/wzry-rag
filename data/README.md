# Data

`data/processed/docs.jsonl` is a **2016 snapshot** of Honor of Kings hero, skill, item and inscription data, cleaned into a uniform schema:

```json
{"doc_id": "hero_105_skill_0", "subject": "廉颇", "type": "技能", "text": "...", "source_url": "..."}
```

`data/chunks/` contains three deterministic chunking strategies used by the retrieval ablation:

- `chunks_semantic.jsonl` — one knowledge item per chunk (production).
- `chunks_heading.jsonl` — grouped by subject + type.
- `chunks_fixed.jsonl` — fixed-length sliding window.

Raw crawl output (`data/raw/`) is intentionally **not committed**. Rebuild it with the scripts in `scripts/` if you have the right to access the source.

## Rebuild

```bash
uv run python ingest/chunkers.py
uv run python ingest/build_index.py
```

The Chroma index is generated locally and is not committed.

## Copyright

Honor of Kings (王者荣耀) and its game data belong to Tencent. The data here is a non-commercial technical snapshot. It is **not** covered by the repository's MIT license. See the data disclaimer in `LICENSE`.
