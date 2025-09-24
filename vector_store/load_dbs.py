"""
this module is used for loading the image related data and vector db retriever
"""

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore  # Updated LangChain Qdrant integration
from qdrant_client import QdrantClient

load_dotenv()

from qdrant_client.http.models import Filter

class load_vector_database():
    "This class is useful for loading the vector DBs"
    def __init__(self):
        self.image_vector_db_path = "multimodel_vector_db"  # collection name
        self.text_vector_db_path = "10K_vector_db"          # collection name
        self.embeddings = OpenAIEmbeddings()
        self.qdrant_client = QdrantClient(url="http://localhost:6333")
    
    def get_image_retriever(self):
        image_vectorstore_10k = QdrantVectorStore(
            client=self.qdrant_client,
            collection_name=self.image_vector_db_path,
            embedding=self.embeddings
        )
        image_retriever_10k = image_vectorstore_10k.as_retriever(search_kwargs={"k": 4})  
        return image_vectorstore_10k, image_retriever_10k, self.image_vector_db_path
    
    def get_text_retriever(self):
        vectorstore = QdrantVectorStore(
            client=self.qdrant_client,
            collection_name=self.text_vector_db_path,
            embedding=self.embeddings
        )
        retriever = vectorstore.as_retriever(
            search_kwargs={"k": 4}
        )
        return retriever, vectorstore, self.text_vector_db_path
    
    def get_vector_store_files(self, vectorstore):
        doc_list = set()

        points, _ = vectorstore.client.scroll(
            collection_name=vectorstore.collection_name,
            with_payload=True,
            limit=1000
        )

        for point in points:
            payload = point.payload  # <-- access directly
            doc_list.add(payload.get("source_file", "Unknown"))

        return ' ,'.join(doc_list)


    def get_img_vector_store_companies(self, img_vector_store):
        doc_list = set()

        points, _ = img_vector_store.client.scroll(
            collection_name=img_vector_store.collection_name,
            with_payload=True,
            limit=1000
        )

        for point in points:
            payload = point.payload  # <-- access directly
            doc_list.add(payload.get("company", "Unknown"))

        return ' ,'.join(doc_list)



