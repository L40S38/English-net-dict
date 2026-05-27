from __future__ import annotations

import asyncio
from dataclasses import dataclass

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage

from core.services.embedding_service import embed_texts_sync


@dataclass
class ClusteredDefinition:
    part_of_speech: str
    meaning_en: str
    examples_en: list[str]
    sort_order: int


def _dedup_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _connected_components_by_threshold(sim_matrix: np.ndarray, threshold: float) -> list[list[int]]:
    n = sim_matrix.shape[0]
    visited = [False] * n
    components: list[list[int]] = []
    for start in range(n):
        if visited[start]:
            continue
        stack = [start]
        visited[start] = True
        comp: list[int] = []
        while stack:
            i = stack.pop()
            comp.append(i)
            neighbors = np.where(sim_matrix[i] >= threshold)[0]
            for j in neighbors:
                jj = int(j)
                if not visited[jj]:
                    visited[jj] = True
                    stack.append(jj)
        components.append(sorted(comp))
    return components


def _cosine_similarity_matrix(vectors: list[list[float]]) -> np.ndarray:
    mat = np.array(vectors, dtype=np.float64)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = mat / norms
    sim = np.clip(normed @ normed.T, -1.0, 1.0)
    np.fill_diagonal(sim, 1.0)
    return sim


def _compress_components_to_max_k(
    components: list[list[int]],
    sim_matrix: np.ndarray,
    max_clusters: int,
) -> list[list[int]]:
    if len(components) < max_clusters:
        return components
    # Component centroid vectors on similarity-derived space.
    # Use average similarity profile as a compact proxy vector.
    profiles = []
    for comp in components:
        rows = sim_matrix[np.array(comp)]
        profile = np.mean(rows, axis=0)
        profiles.append(profile)
    points = np.array(profiles, dtype=np.float64)
    if len(points) <= 1:
        return components
    z = linkage(points, method="ward")
    labels = fcluster(z, t=max_clusters, criterion="maxclust")
    merged: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        merged.setdefault(int(label), []).extend(components[idx])
    return [sorted(v) for _, v in sorted(merged.items(), key=lambda item: min(item[1]))]


def cluster_definitions_sync(
    raw_defs: list[dict],
    *,
    sim_threshold: float = 0.8,
    max_per_pos: int = 8,
) -> list[ClusteredDefinition]:
    by_pos: dict[str, list[dict]] = {}
    pos_order: list[str] = []
    for idx, item in enumerate(raw_defs):
        if not isinstance(item, dict):
            continue
        meaning = str(item.get("meaning_en", "")).strip()
        if not meaning:
            continue
        pos = str(item.get("part_of_speech", "noun")).strip() or "noun"
        entry = dict(item)
        entry["_original_index"] = idx
        by_pos.setdefault(pos, []).append(entry)
        if pos not in pos_order:
            pos_order.append(pos)

    output: list[ClusteredDefinition] = []
    sort_order = 0
    for pos in pos_order:
        entries = by_pos.get(pos, [])
        texts = [str(x.get("meaning_en", "")).strip() for x in entries]
        try:
            vectors = embed_texts_sync(texts)
            valid = [i for i, v in enumerate(vectors) if v]
            if len(valid) < len(entries):
                components = [[i] for i in range(len(entries))]
            else:
                sim = _cosine_similarity_matrix(vectors)
                components = _connected_components_by_threshold(sim, sim_threshold)
                k1 = len(components)
                if k1 >= 9:
                    components = _compress_components_to_max_k(components, sim, max_per_pos)
        except Exception:  # noqa: BLE001
            components = [[i] for i in range(len(entries))]
        if len(components) > max_per_pos:
            components = components[:max_per_pos]
        for comp in components:
            members = [entries[i] for i in comp]
            members.sort(key=lambda x: int(x.get("_original_index", 0)))
            representative = members[0]
            examples = _dedup_keep_order([str(x.get("example_en", "")).strip() for x in members])
            output.append(
                ClusteredDefinition(
                    part_of_speech=pos,
                    meaning_en=str(representative.get("meaning_en", "")).strip(),
                    examples_en=examples,
                    sort_order=sort_order,
                )
            )
            sort_order += 1
    return output


async def cluster_definitions(
    raw_defs: list[dict],
    *,
    sim_threshold: float = 0.8,
    max_per_pos: int = 8,
) -> list[ClusteredDefinition]:
    return await asyncio.to_thread(
        cluster_definitions_sync,
        raw_defs,
        sim_threshold=sim_threshold,
        max_per_pos=max_per_pos,
    )

