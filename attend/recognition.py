from typing import List, Tuple
import numpy as np
from .utils import cosine_sim


def best_match(query: np.ndarray, enrolled: List[Tuple[str, str, np.ndarray]]):
    """
    Find best match for query embedding from enrolled students.

    Args:
        query: Query embedding vector (512D)
        enrolled: List of (student_id, name, embedding_vec) tuples

    Returns:
        Tuple of (student_id, similarity_score) or (None, 0.0) if no match
    """
    if not enrolled:
        return None, 0.0

    best_id, best_sim = None, -1.0

    for sid, name, ref in enrolled:
        sim = cosine_sim(query, ref)
        if sim > best_sim:
            best_sim, best_id = sim, sid

    return best_id, best_sim
