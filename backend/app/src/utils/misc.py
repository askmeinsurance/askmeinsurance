from qdrant_client import QdrantClient
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import get_settings


def get_google_api_key() -> str:
    key = get_settings().gemini_api_key
    if not key:
        raise ValueError("Missing Google API key. Set GEMINI_API_KEY.")
    return key


def get_qdrant_client() -> QdrantClient:
    s = get_settings()
    if not s.qdrant_url:
        raise ValueError("Missing QDRANT_URL.")
    return QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key or None)


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    s = get_settings()
    return GoogleGenerativeAIEmbeddings(
        model=s.embedding_model,
        google_api_key=get_google_api_key(),
        output_dimensionality=s.embedding_dimension,
    )


def get_textbook_top_k() -> int:
    v = get_settings().textbook_top_k
    if not 1 <= v <= 15:
        raise ValueError("textbook_top_k must be between 1 and 15.")
    return v


def get_product_summary_top_k() -> int:
    v = get_settings().product_summary_top_k
    if not 1 <= v <= 15:
        raise ValueError("product_summary_top_k must be between 1 and 15.")
    return v
