"""Lance asset store with pinned offline embeddings and attributable source chunks.

Build-time extraction preserves original bytes. Runtime search uses lexical and
vector scores after scope filtering. No model discovery or paid extraction occurs.
"""
import sys, os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

import hashlib
import re
import numpy as np
import pyarrow as pa
import lance

from knowledge import ontology
from common.config import get_config, PROJECT_ROOT as CFG_PROJECT_ROOT

HASH_DIM = 128
STOPWORDS = frozenset('a an the is are was were be been being of for to in on at by with and or as it this that these those has have from does do not'.split())


def _tokens(text):
    return set(re.findall(r"\w+", text.lower())) - STOPWORDS


EMBEDDING_CONTRACT = {"version": "token-hash-v2", "model": "sha256-token-bag", "dimension": HASH_DIM,
                      "tokenizer": "unicode-word-lower-v1", "normalization": "l2", "dtype": "float32"}


class IncompatibleIndex(RuntimeError):
    """The stored vectors cannot be compared with this query encoder."""


def _try_load_st():
    """Compatibility hook. Automatic model discovery is deliberately disabled."""
    return None


def embedding_contract():
    configured = get_config().get('knowledge', {}).get('embedding', {})
    if configured and configured != EMBEDDING_CONTRACT:
        raise IncompatibleIndex('Unsupported embedding contract. Use token-hash-v2 and rebuild with prepare.py.')
    return dict(EMBEDDING_CONTRACT)


def _hash_embed(text: str, dim: int = HASH_DIM) -> np.ndarray:
    """Deterministic token-hash bag-of-words embedding, L2-normalized."""
    vec = np.zeros(dim, dtype=np.float32)
    for tok in re.findall(r"\w+", (text or "").lower()):
        h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def embed(text: str) -> np.ndarray:
    """Use the explicitly versioned offline encoder; never switch models."""
    embedding_contract()
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
    from common.runtime import require_demo
    require_demo('Demo knowledge build')
    from data_generation.generate_assets import build_assets

    assets = build_assets()
    for a in assets:
        assert ontology.validate_asset(a), f"invalid ontology_class: {a.get('ontology_class')}"

    from knowledge.documents import extract_document
    import json
    for asset in assets:
        asset['extraction'] = extract_document(asset)
        asset['chunks'] = asset['extraction']['chunks']
    embeddings = [embed(' '.join([a['title'], a['caption_text']] + [c['text'] for c in a['chunks']])) for a in assets]
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
        **{key: pa.array([a[key] for a in assets], type=pa.string())
           for key in ("provenance", "source_url", "license_url")},
        **{key: pa.array([a.get(key, '') for a in assets], type=pa.string()) for key in ('evidence_kind','snapshot_id')},
        "extraction_json": pa.array([json.dumps({k:v for k,v in a['extraction'].items() if k!='chunks'}, sort_keys=True) for a in assets], type=pa.string()),
        "chunks_json": pa.array([json.dumps(a['chunks'], sort_keys=True) for a in assets], type=pa.string()),
        "embedding_contract": pa.array([json.dumps(embedding_contract(), sort_keys=True)] * len(assets), type=pa.string()),
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
    import json
    ds = lance.dataset(path)
    if 'embedding_contract' not in ds.schema.names:
        raise IncompatibleIndex('Knowledge index has no embedding contract. Run prepare.py to rebuild it.')
    contracts = ds.to_table(columns=['embedding_contract']).column(0).to_pylist()
    expected = json.dumps(embedding_contract(), sort_keys=True)
    if any(c != expected for c in contracts) or ds.schema.field('embedding').type.list_size != HASH_DIM:
        raise IncompatibleIndex('Knowledge index embedding contract differs. Run prepare.py to rebuild it.')
    return ds


def search(query: str, ontology_filter: str | None = None, k: int = 5, external_only: bool = False, program_id: str | None = None, evidence_kind: str = "all", requirement_ids: list[str] | None = None) -> list[dict]:
    """Brute-force cosine similarity over the (small, ~10-row) embedding
    column — simpler and more deterministic than building an ANN index at
    this scale. Sorted by score desc with a stable asset_id tiebreak.
    ponytail: brute-force cosine, add a Lance vector index only if N grows
    past a few thousand rows."""
    import json
    query_tokens = _tokens(query)
    if not query_tokens or k <= 0:
        return []
    if ontology_filter is not None and ontology_filter not in ontology.classes():
        # Unknown class legitimately has zero matches — safe to short-circuit
        # instead of string-interpolating an unvalidated value into the
        # Lance filter (which crashed on quotes / allowed tautology bypass).
        return []
    ds = _open()
    filt = f"ontology_class = '{ontology_filter}'" if ontology_filter else None
    rows = ds.to_table(filter=filt).to_pylist()
    if program_id:
        from knowledge.asset_registry import scoped_assets
        rows = scoped_assets(rows, program_id, evidence_kind, len(rows))
    if requirement_ids is not None:
        rows = [r for r in rows if r.get('source_url') or r.get('linked_entity_id') in requirement_ids]
    if external_only:
        # Exclude generated fixtures and collapse reused copies of one source asset.
        unique = {}
        for row in sorted(rows, key=lambda r: r['asset_id']):
            if row.get('source_url') and row.get('license_url'):
                identity = (row['source_url'], hashlib.sha256(row['blob']).hexdigest())
                unique.setdefault(identity, row)
        rows = list(unique.values())
    if not rows:
        return []

    qvec = embed(query)
    mat = np.array([r["embedding"] for r in rows], dtype=np.float32)
    qnorm = np.linalg.norm(qvec)
    row_norms = np.linalg.norm(mat, axis=1)
    denom = row_norms * qnorm
    scores = np.where(denom > 0, np.sum(mat * qvec, axis=1) / np.where(denom > 0, denom, 1.0), 0.0)

    hits = []
    for r, score in zip(rows, scores):
        chunks = json.loads(r['chunks_json'])
        searchable = ' '.join([r['title'], r['caption_text']] + [c['text'] for c in chunks])
        tokens = _tokens(searchable)
        overlap = query_tokens & tokens
        # Hash collisions alone cannot establish relevance.
        if not overlap:
            continue
        lexical = len(overlap) / len(query_tokens)
        vector_score = max(0.0, float(score))
        score = 0.7 * lexical + 0.3 * vector_score
        matching = sorted([c for c in chunks if query_tokens & _tokens(c['text'])],
                          key=lambda c: (-len(query_tokens & _tokens(c['text'])), c['chunk_id']))
        h = {kk: v for kk, v in r.items() if kk not in {"embedding", "chunks_json", "embedding_contract", "extraction_json"}}
        h['retrieval'] = {'method':'hybrid-lexical-token-hash-v1', 'lexical_score':lexical, 'vector_score':vector_score,
                          'matched_terms':sorted(overlap), 'chunks':matching[:3], 'support':'extracted source text' if matching else 'metadata only; no matching extracted source text', 'embedding_contract':embedding_contract()}
        h['extraction'] = json.loads(r['extraction_json'])
        h["score"] = float(score)
        hits.append(h)
    hits.sort(key=lambda h: (-h["score"], h["asset_id"]))
    return hits[:k]


_ASSET_ID_RE = re.compile(r"[A-Za-z0-9_-]+")


def get_asset(asset_id: str) -> dict:
    if not _ASSET_ID_RE.fullmatch(asset_id):
        # Malformed id (e.g. containing a quote) can't be a real asset_id —
        # treat as not-found instead of letting it reach the Lance
        # tokenizer, which raises an unhandled ValueError on bad syntax.
        raise KeyError(f"asset not found: {asset_id}")
    ds = _open()
    rows = ds.to_table(filter=f"asset_id = '{asset_id}'").to_pylist()
    if not rows:
        raise KeyError(f"asset not found: {asset_id}")
    row = rows[0]
    row.pop("embedding", None)
    import json
    row['extraction'] = json.loads(row.pop('extraction_json'))
    row['chunks'] = json.loads(row.pop('chunks_json'))
    row['embedding_contract'] = json.loads(row['embedding_contract'])
    if row.get('snapshot_id'):
        from common import source
        if row['snapshot_id'] != source.snapshot_identity(row['program_ref'])['snapshot_id']:
            raise ValueError('Asset snapshot is stale. Run prepare.py to rebuild the knowledge base.')
    return row


if __name__ == "__main__":
    assert embed('thermal').shape == (HASH_DIM,)
    assert np.array_equal(embed('thermal'), embed('thermal'))
    assert search('!!!') == []
