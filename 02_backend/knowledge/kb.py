"""Multimodal knowledge base (Task 7) — Lance-backed store of ontology-validated
assets (images/pdfs/text) with precomputed embeddings for semantic search.

Two-store rule: this is a third, separate store (data/kb/assets.lance) —
distinct from common/db.py's ops SQLite and common/source.py's CSV source.

Embedding: embed(text) tries sentence-transformers MiniLM first (only useful
if the model is already cached offline — see module docstring note below on
why the fallback is what actually runs here), and falls back to a
deterministic 128-dim token-hash bag, L2-normalized (_hash_embed). The ST
attempt is wrapped in try/except so embed() never hard-fails regardless of
network state; determinism is guaranteed by the hashing fallback.
"""
import sys, os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

import hashlib
import numpy as np
import pyarrow as pa
import lance

from knowledge import ontology
from common.config import get_config, PROJECT_ROOT as CFG_PROJECT_ROOT

HASH_DIM = 128

_st_model = None
_st_unavailable = False


def _try_load_st():
    """Attempt to load sentence-transformers MiniLM from local/offline cache
    only (HF_HUB_OFFLINE=1) so this never blocks on a network call. Cached
    once per process; on any failure, remember it and never retry."""
    global _st_model, _st_unavailable
    if _st_model is not None or _st_unavailable:
        return _st_model
    try:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        _st_unavailable = True
        _st_model = None
    return _st_model


def _hash_embed(text: str, dim: int = HASH_DIM) -> np.ndarray:
    """Deterministic token-hash bag-of-words embedding, L2-normalized."""
    vec = np.zeros(dim, dtype=np.float32)
    for tok in (text or "").lower().split():
        h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def embed(text: str) -> np.ndarray:
    """Same function used at build time (asset captions) and query time (the
    search string) — this is what makes vector search apples-to-apples."""
    model = _try_load_st()
    if model is not None:
        try:
            v = np.asarray(model.encode([text], convert_to_numpy=True)[0], dtype=np.float32)
            norm = np.linalg.norm(v)
            return v / norm if norm > 0 else v
        except Exception:
            pass  # fall through to the deterministic hash embedding
    return _hash_embed(text)


def _kb_path() -> str:
    cfg = get_config()
    kb_dir = cfg.get("data", {}).get("kb_dir", "data/kb")
    if not os.path.isabs(kb_dir):
        kb_dir = os.path.join(CFG_PROJECT_ROOT, kb_dir)
    return os.path.join(kb_dir, "assets.lance")


def build_kb() -> int:
    """Validates every seeded asset against the ontology, embeds each asset's
    caption, and (re)writes the Lance dataset. Returns the row count."""
    from data_generation.generate_assets import build_assets

    assets = build_assets()
    for a in assets:
        assert ontology.validate_asset(a), f"invalid ontology_class: {a.get('ontology_class')}"

    embeddings = [embed(a["caption_text"]) for a in assets]
    dim = len(embeddings[0])
    assert all(len(e) == dim for e in embeddings), "embedding dim mismatch across assets"

    table = pa.table({
        "asset_id": pa.array([a["asset_id"] for a in assets], type=pa.string()),
        "ontology_class": pa.array([a["ontology_class"] for a in assets], type=pa.string()),
        "modality": pa.array([a["modality"] for a in assets], type=pa.string()),
        "title": pa.array([a["title"] for a in assets], type=pa.string()),
        "caption_text": pa.array([a["caption_text"] for a in assets], type=pa.string()),
        "blob": pa.array([a["blob"] for a in assets], type=pa.binary()),
        "program_ref": pa.array([a["program_ref"] for a in assets], type=pa.string()),
        "linked_entity_type": pa.array([a["linked_entity_type"] for a in assets], type=pa.string()),
        "linked_entity_id": pa.array([a["linked_entity_id"] for a in assets], type=pa.string()),
        "embedding": pa.array([e.tolist() for e in embeddings], type=pa.list_(pa.float32(), dim)),
    })

    path = _kb_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lance.write_dataset(table, path, mode="overwrite")
    return table.num_rows


def _open() -> "lance.LanceDataset":
    path = _kb_path()
    if not os.path.exists(path):
        raise RuntimeError(f"KB not found at {path}. Run build_kb() first.")
    return lance.dataset(path)


def search(query: str, ontology_filter: str | None = None, k: int = 5) -> list[dict]:
    """Brute-force cosine similarity over the (small, ~10-row) embedding
    column — simpler and more deterministic than building an ANN index at
    this scale. Sorted by score desc with a stable asset_id tiebreak.
    ponytail: brute-force cosine, add a Lance vector index only if N grows
    past a few thousand rows."""
    ds = _open()
    filt = f"ontology_class = '{ontology_filter}'" if ontology_filter else None
    rows = ds.to_table(filter=filt).to_pylist()
    if not rows:
        return []

    qvec = embed(query)
    mat = np.array([r["embedding"] for r in rows], dtype=np.float32)
    qnorm = np.linalg.norm(qvec)
    row_norms = np.linalg.norm(mat, axis=1)
    denom = row_norms * qnorm
    scores = np.where(denom > 0, mat @ qvec / np.where(denom > 0, denom, 1.0), 0.0)

    hits = []
    for r, score in zip(rows, scores):
        h = {kk: v for kk, v in r.items() if kk != "embedding"}
        h["score"] = float(score)
        hits.append(h)
    hits.sort(key=lambda h: (-h["score"], h["asset_id"]))
    return hits[:k]


def get_asset(asset_id: str) -> dict:
    ds = _open()
    rows = ds.to_table(filter=f"asset_id = '{asset_id}'").to_pylist()
    if not rows:
        raise KeyError(f"asset not found: {asset_id}")
    row = rows[0]
    row.pop("embedding", None)
    return row


if __name__ == "__main__":
    n = build_kb()
    assert n >= 8, n
    hits = search("thermal runaway containment design", k=3)
    assert hits and any("thermal" in (h.get("linked_entity_id") or "") for h in hits), hits
    top = hits[0]
    a = get_asset(top["asset_id"])
    assert a["blob"] and a["modality"] in {"image", "pdf", "text"}
    a2 = [h["asset_id"] for h in search("thermal", k=3)]
    b2 = [h["asset_id"] for h in search("thermal", k=3)]
    assert a2 == b2, (a2, b2)
    print(f"kb OK — {n} assets, top hit for 'thermal runaway containment design' = {top['asset_id']} "
          f"(score={top['score']:.3f}, linked={top['linked_entity_id']})")
