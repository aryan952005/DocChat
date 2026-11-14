"""RAG evaluation for DocChat (Phase 10).

Run from anywhere:  python eval/run_eval.py            (all 4 configs, a few minutes)
                    python eval/run_eval.py c500_retry_on   (one config)

Each config runs in its own Python process, so CHUNK_SIZE / MAX_RETRIES / the Qdrant
collection are read fresh by the app's config.py. The app code is not changed.
Eval data goes to separate Qdrant collections and the Mongo database "docchat_eval".
"""
import json
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AI = ROOT / "ai-service"
EVAL = ROOT / "eval"
PDF = AI / "payments-api-sample-v2.pdf"

# chunk size 500 vs 1000, retry loop ON (MAX_RETRIES=2) vs OFF (MAX_RETRIES=0)
CONFIGS = {
    "c500_retry_on": {"chunk": 500, "retries": 2},
    "c1000_retry_on": {"chunk": 1000, "retries": 2},
    "c500_retry_off": {"chunk": 500, "retries": 0},
    "c1000_retry_off": {"chunk": 1000, "retries": 0},
}


class DailyQuotaUsedUp(Exception):
    pass


def with_retry(fn, tries=4):
    """Gemini free tier can answer 429 (rate limit): wait and try again."""
    for attempt in range(1, tries + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            # The daily quota only resets at midnight Pacific time, so waiting a few seconds is pointless
            if "PerDay" in str(e):
                raise DailyQuotaUsedUp(str(e)[:150]) from e
            if attempt == tries:
                raise
            time.sleep(15 * attempt)


def with_timeout(fn, seconds):
    """A network call can hang forever; give up after `seconds` so one question cannot stall the run.
    A new thread per call, so a stuck call never blocks the next question."""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(fn).result(timeout=seconds)
    except TimeoutError:
        raise RuntimeError(f"timed out after {seconds}s")
    finally:
        pool.shutdown(wait=False)


# ---------------------------------------------------------------- worker (one config)
def worker(name):
    sys.path.insert(0, str(AI))
    from pydantic import BaseModel
    from langchain_core.messages import HumanMessage
    from app.config import llm, qdrant_client, QDRANT_COLLECTION
    from app.ingest import ingest_file
    from app.prompts import NOT_FOUND_TEXT
    from app.graph.build_graph import build_graph

    class Verdict(BaseModel):
        correct: bool

    # Ingest once per chunk size (collection name carries the chunk size)
    if not qdrant_client.collection_exists(QDRANT_COLLECTION):
        ingest_file(str(PDF), "eval-doc", PDF.name)
    chunks = qdrant_client.count(QDRANT_COLLECTION).count

    graph = build_graph()
    questions = json.loads((EVAL / "questions.json").read_text())
    rows = []
    for q in questions:
        row = {"id": q["id"], "question": q["question"], "in_docs": q["in_docs"]}
        try:
            start = time.time()
            result = with_timeout(lambda: with_retry(lambda: graph.invoke(
                {"question": q["question"], "messages": [HumanMessage(content=q["question"])]},
                config={"configurable": {"thread_id": f"eval-{uuid.uuid4()}"}},  # fresh memory per question
            )), 240)
            row["latency"] = round(time.time() - start, 1)
            row["answer"] = result["answer"]
            row["route"] = result["route"]
            row["retries"] = result["retry_count"]
            row["sources"] = result["sources"]
            not_found = (result["route"] == "docs" and not result["sources"]) or result["answer"] == NOT_FOUND_TEXT

            if q["in_docs"]:
                # Retrieval hit: the expected page is among the sources the answer cited
                row["hit"] = any(
                    s["filename"] == q["expected_filename"] and s["page"] == q["expected_page"]
                    for s in result["sources"]
                )
                # Answer correctness: simple LLM-as-judge, yes or no
                if not_found:
                    row["correct"] = False
                else:
                    prompt = (
                        "You grade answers from a documentation assistant.\n"
                        f"Question: {q['question']}\nExpected answer: {q['expected_answer']}\n"
                        f"Actual answer: {result['answer']}\n"
                        "Does the actual answer state the expected facts without contradicting them? "
                        "Extra correct detail is fine."
                    )
                    row["correct"] = with_timeout(lambda: with_retry(lambda: llm.with_structured_output(Verdict).invoke(prompt)), 120).correct
            else:
                # Out of scope: the right behaviour is an honest "not found"
                row["correct"] = not_found
        except DailyQuotaUsedUp:
            print(f"[{name}] Gemini daily quota is used up; stopping. Run again after it resets.", file=sys.stderr, flush=True)
            os._exit(2)
        except Exception as e:  # noqa: BLE001
            row["error"] = str(e)[:200]
        rows.append(row)
        print(f"[{name}] q{q['id']} {'ERROR ' + row['error'][:80] if 'error' in row else 'done'}", file=sys.stderr, flush=True)
        time.sleep(2)

    (EVAL / f"results_{name}.json").write_text(json.dumps({"name": name, "chunks": chunks, "rows": rows}, indent=2))
    os._exit(0)  # do not wait for a hung background call


# ---------------------------------------------------------------- main (all configs)
def pct(num, den):
    return f"{num}/{den} ({round(100 * num / den)}%)" if den else "n/a"


def summarise(data):
    rows = data["rows"]
    ok = [r for r in rows if "error" not in r]
    docs = [r for r in ok if r["in_docs"]]
    oos = [r for r in ok if not r["in_docs"]]
    lat = [r["latency"] for r in ok]
    return {
        "chunks": data["chunks"],
        "hit": pct(sum(r["hit"] for r in docs), len(docs)),
        "correct": pct(sum(r["correct"] for r in docs), len(docs)),
        "oos": pct(sum(r["correct"] for r in oos), len(oos)),
        "latency": f"{sum(lat) / len(lat):.1f}s" if lat else "n/a",
        "retries": f"{sum(r['retries'] for r in docs) / len(docs):.2f}" if docs else "n/a",
        "errors": len(rows) - len(ok),
    }


def main(names):
    for name in names:
        cfg = CONFIGS[name]
        env = dict(os.environ, CHUNK_SIZE=str(cfg["chunk"]), CHUNK_OVERLAP="100",
                   MAX_RETRIES=str(cfg["retries"]), QDRANT_COLLECTION=f"docchat_eval_{cfg['chunk']}",
                   MONGO_DB="docchat_eval")
        print(f"\n== {name}: chunk size {cfg['chunk']}, max retries {cfg['retries']}", flush=True)
        try:
            subprocess.run([sys.executable, __file__, "--worker", name], cwd=AI, env=env, check=True, timeout=1800)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f"[{name}] failed: {type(e).__name__}; continuing with the next config", flush=True)

    lines = ["| Config | Chunk size | Retries | Chunks stored | Retrieval hit | Answer correct | Out-of-scope correct | Avg latency | Avg retries (in-docs) | Errors |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for name in CONFIGS:
        f = EVAL / f"results_{name}.json"
        if not f.exists():
            continue
        s = summarise(json.loads(f.read_text()))
        c = CONFIGS[name]
        lines.append(f"| {name} | {c['chunk']} | {c['retries']} | {s['chunks']} | {s['hit']} | {s['correct']} | {s['oos']} | {s['latency']} | {s['retries']} | {s['errors']} |")
    table = "\n".join(lines)
    print("\n" + table)
    (EVAL / "results.md").write_text(
        "# Evaluation results\n\n"
        "Corpus: one 6-page document, 10 questions (8 answerable, 2 not in the docs). One run per config.\n"
        "The model ignores temperature, so a re-run can differ a little.\n\n" + table + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--worker":
        worker(sys.argv[2])
    else:
        main(sys.argv[1:] or list(CONFIGS))
