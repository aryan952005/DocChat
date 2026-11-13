import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from qdrant_client import QdrantClient

load_dotenv()  # reads ai-service/.env

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")  # empty for local Docker, set for Qdrant Cloud
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "docchat_docs")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "docchat")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 100))
TOP_K = int(os.getenv("TOP_K", 5))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 2))

# Embedding model: text -> 768 numbers, used only for search.
# output_dimensionality=768 shortens Gemini's vector so the Qdrant collection stays 768.
embeddings = GoogleGenerativeAIEmbeddings(
    model=EMBED_MODEL, output_dimensionality=768, google_api_key=GEMINI_API_KEY
)

# Generative model: writes text. Temperature 0 = (nearly) deterministic output.
llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0, google_api_key=GEMINI_API_KEY)

qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
