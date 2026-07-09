"""Minimal retrieval quality eval harness (Epic 13 / PDR §3.6 Benchmarking).

Not part of the installed package — a standalone script for measuring
precision@k / recall@k against a labeled eval set, so hybrid retrieval and
reranking changes (FR-6.6-6.8) can be judged against a baseline instead of
by feel. Requires a live vector store already populated by an ingestion run.

Usage:
    python scripts/eval_retrieval.py config/eval_set.example.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ragchatbot.config.settings import Settings  # noqa: E402
from ragchatbot.db.vector_store import build_vector_engine, ensure_schema  # noqa: E402
from ragchatbot.providers.factory import build_embedding_provider  # noqa: E402
from ragchatbot.retrieval.pipeline import retrieve  # noqa: E402


def load_eval_cases(path: str) -> list[dict[str, object]]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cases = raw.get("cases", [])
    if not cases:
        raise ValueError(f"No cases defined under 'cases:' in {path}")
    return cases


async def run_eval(eval_set_path: str, top_k: int | None = None) -> None:
    settings = Settings()
    cases = load_eval_cases(eval_set_path)

    vector_engine = build_vector_engine(settings.vector_db())
    embedding_provider = build_embedding_provider(settings)
    await embedding_provider.embed(["dimension probe"])
    vector_table = ensure_schema(vector_engine, settings.vector_table_name, embedding_provider.dimension)

    k = top_k or settings.retrieval_top_k
    precisions, recalls = [], []

    for case in cases:
        query = case["query"]
        expected = set(case.get("expected_record_ids", []))

        context = await retrieve(
            query=query,
            embedding_provider=embedding_provider,
            vector_engine=vector_engine,
            vector_table=vector_table,
            top_k=k,
            similarity_threshold=settings.retrieval_similarity_threshold,
            keyword_weight=settings.retrieval_keyword_weight,
        )
        retrieved_ids = {r.chunk.record_id for r in context.results}

        hits = retrieved_ids & expected
        precision = len(hits) / len(retrieved_ids) if retrieved_ids else 0.0
        recall = len(hits) / len(expected) if expected else 0.0
        precisions.append(precision)
        recalls.append(recall)

        print(f"[{'OK' if hits else 'MISS'}] {query!r} precision={precision:.2f} recall={recall:.2f}")

    avg_precision = sum(precisions) / len(precisions)
    avg_recall = sum(recalls) / len(recalls)
    print(f"\nAverage precision@{k}: {avg_precision:.3f}")
    print(f"Average recall@{k}:    {avg_recall:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality against a labeled eval set.")
    parser.add_argument("eval_set", help="Path to an eval set YAML file")
    parser.add_argument("--top-k", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(run_eval(args.eval_set, args.top_k))


if __name__ == "__main__":
    main()
