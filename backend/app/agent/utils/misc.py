from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import get_settings

_bm25: SparseTextEmbedding | None = None


def get_google_api_key() -> str:
    key = get_settings().gemini_api_key
    if not key:
        raise ValueError("Missing Google API key. Set GEMINI_API_KEY.")
    return key


def get_qdrant_client() -> QdrantClient:
    s = get_settings()
    if not s.qdrant_url:
        raise ValueError("Missing QDRANT_URL.")
    return QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key or None, timeout=30)


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    s = get_settings()
    return GoogleGenerativeAIEmbeddings(
        model=s.embedding_model,
        google_api_key=get_google_api_key(),
        output_dimensionality=s.embedding_dimension,
    )


def get_bm25_model() -> SparseTextEmbedding:
    global _bm25
    if _bm25 is None:
        _bm25 = SparseTextEmbedding(model_name="Qdrant/bm25")
    return _bm25


