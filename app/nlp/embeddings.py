import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN

_model=None
def get_model():
    global _model
    if _model is None:
        _model=SentenceTransformer("intfloat/multilingual-e5-small")
    return _model

def embed_texts(texts):
    m=get_model()
    return np.asarray(m.encode([t[:512] for t in texts], normalize_embeddings=True))

def cluster_texts(embeds, eps=0.25, min_samples=2):
    db=DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
    labels=db.fit_predict(embeds)
    return labels
