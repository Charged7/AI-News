from functools import lru_cache

from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim


@lru_cache(maxsize=1)
def get_model():
    return SentenceTransformer(
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    )


def similarity(text1: str, text2: str) -> float:
    model = get_model()

    emb1 = model.encode(text1, convert_to_tensor=True)
    emb2 = model.encode(text2, convert_to_tensor=True)

    return float(cos_sim(emb1, emb2))