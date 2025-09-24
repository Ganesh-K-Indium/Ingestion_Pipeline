from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from dotenv import load_dotenv

load_dotenv()

def create_qdrant_collection(collection_name: str, qdrant_url: str = "http://localhost:6333"):
    # Initialize embeddings
    embeddings = OpenAIEmbeddings()
    
    # Detect embedding dimension dynamically
    dummy_vector = embeddings.embed_query("Hello world")
    embedding_dim = len(dummy_vector)
    print(f"Detected embedding dimension: {embedding_dim}")
    
    # Connect to Qdrant
    client = QdrantClient(url=qdrant_url)
    
    # Drop + recreate collection
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE)
    )
    
    print(f" Collection '{collection_name}' recreated with vector size {embedding_dim}.")

if __name__ == "__main__":
    # Recreate both collections fresh
    create_qdrant_collection("multimodel_vector_db")
    create_qdrant_collection("10K_vector_db")
