"""
RAG — recherche dans la base de connaissances (normes ISO, guide des défauts,
interprétation des indicateurs).

Quand on pose une question au copilot, on retrouve les passages les plus
pertinents de la documentation et on les injecte dans le contexte. Le copilot
répond alors en s'appuyant sur les normes et les signatures de défaut réelles,
pas seulement sur ses connaissances générales.

Recherche par similarité TF-IDF (aucune dépendance lourde — utilise scikit-learn
déjà présent).
"""

import re
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KNOWLEDGE_DIR = Path("backend/knowledge")


class KnowledgeBase:

    def __init__(self):
        self._chunks = []
        self._vectorizer = None
        self._matrix = None
        self._built = False

    def _load_chunks(self) -> list:
        chunks = []
        if not KNOWLEDGE_DIR.exists():
            return chunks
        for f in sorted(KNOWLEDGE_DIR.glob("*.md")):
            try:
                text = f.read_text(encoding="utf-8")
            except Exception:
                continue
            # découpe par section "## titre"
            for part in re.split(r"\n(?=## )", text):
                part = part.strip()
                if len(part) < 25:
                    continue
                title = part.splitlines()[0].lstrip("# ").strip()
                chunks.append({"source": f.stem, "title": title, "text": part})
        return chunks

    def build(self):
        self._chunks = self._load_chunks()
        if not self._chunks:
            self._built = False
            return
        corpus = [c["text"] for c in self._chunks]
        self._vectorizer = TfidfVectorizer(strip_accents="unicode", lowercase=True)
        self._matrix = self._vectorizer.fit_transform(corpus)
        self._built = True

    def retrieve(self, query: str, k: int = 3, min_score: float = 0.04) -> list:
        if not self._built:
            self.build()
        if not self._built or not query:
            return []
        qv = self._vectorizer.transform([query])
        sims = cosine_similarity(qv, self._matrix)[0]
        order = np.argsort(sims)[::-1][:k]
        out = []
        for i in order:
            if sims[i] < min_score:
                continue
            out.append({**self._chunks[i], "score": round(float(sims[i]), 3)})
        return out


knowledge_base = KnowledgeBase()
