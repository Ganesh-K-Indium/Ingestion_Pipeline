import os
import json
import uuid
from datetime import datetime
import fitz  # PyMuPDF
from qdrant_client import models
from langchain.docstore.document import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from vector_store.load_dbs import load_vector_database
from data_preparation.image_data_prep import ImageDescription


def init_vector_stores():
    """Initialize and return text and image vector stores with proper collection setup."""
    db_init = load_vector_database()
    
    # Initialize text vector store
    text_retriever, text_vectorstore, _ = db_init.get_text_retriever()
    
    # Initialize image vector store
    image_vectorstore, image_retriever, _ = db_init.get_image_retriever()
    
    return text_vectorstore, image_vectorstore

def calculate_content_hash(pdf_path: str) -> str:
    """Calculate a deterministic hash of the PDF content."""
    import hashlib
    
    try:
        pdf_document = fitz.open(pdf_path)
        content_hash = hashlib.sha256()
        
        # Include text content from each page
        for page in pdf_document:
            text = page.get_text("text").encode('utf-8')
            content_hash.update(text)
            
        return content_hash.hexdigest()
    except Exception as e:
        print(f"Error calculating content hash: {e}")
        return ""

def generate_doc_id(doc_metadata: dict, index: int, doc_type: str = "text") -> str:
    """Generate a deterministic UUID for a document."""
    if doc_type == "text":
        # Include content_hash in the ID generation if available
        content_hash = doc_metadata.get('content_hash', '')
        return str(uuid.uuid5(uuid.NAMESPACE_DNS,
                           f"{content_hash}_page{doc_metadata['page_num']}_{index}"))
    else:  # image
        return str(uuid.uuid5(uuid.NAMESPACE_DNS,
                           f"{doc_metadata.get('company', 'NA')}_{doc_metadata['source_file']}_{index}"))

def check_document_exists(vectorstore, source_file_name: str, doc_type: str = "text", content_hash: str = None) -> tuple[bool, list]:
    """
    Check if a document already exists in the vector store using metadata filters.
    
    Args:
        vectorstore: The vector store to check
        source_file_name: Name of the source file
        doc_type: Type of document ("text" or "image")
        content_hash: Hash of the document content for duplicate detection
    
    Returns:
        tuple[bool, list]: (exists, existing_points)
    """
    try:
        print(f"\n=== Checking existence of {source_file_name} ({doc_type}) ===")
        print(f"Collection name: {vectorstore.collection_name}")
        
        # First, let's see what's in the collection
        print("\nDebug: Checking collection info...")
        collection_info = vectorstore.client.get_collection(vectorstore.collection_name)
        print(f"Collection size: {collection_info.points_count} points")
        print(f"Collection vectors dimension: {collection_info.config.params.vectors.size}")
        
        # Build the filter based on content hash if available, otherwise fallback to filename
        filter_conditions = [
            models.FieldCondition(
                key="metadata.content_type",
                match=models.MatchValue(value=doc_type)
            )
        ]
        
        if content_hash:
            filter_conditions.append(
                models.FieldCondition(
                    key="metadata.content_hash",
                    match=models.MatchValue(value=content_hash)
                )
            )
        else:
            filter_conditions.append(
                models.FieldCondition(
                    key="metadata.source_file",
                    match=models.MatchValue(value=source_file_name)
                )
            )
            
        search_filter = models.Filter(must=filter_conditions)
        
        print(f"\nDebug: Using search filter:")
        print(f"metadata.source_file: {source_file_name}")
        print(f"metadata.content_type: {doc_type}")
        print(f"Debug: Full filter: {search_filter.dict()}")

        # Let's first scroll through some points to see what metadata exists
        print("\nDebug: Sampling existing points metadata...")
        sample_points = vectorstore.client.scroll(
            collection_name=vectorstore.collection_name,
            limit=5,
            with_payload=True
        )[0]
        
        if sample_points:
            print("Sample point metadata:")
            for idx, point in enumerate(sample_points[:2]):  # Show first 2 points
                print(f"Point {idx} payload structure: {point.payload.keys()}")
                if 'metadata' in point.payload:
                    print(f"Point {idx} metadata: {point.payload['metadata']}")
                else:
                    print(f"Point {idx} full payload: {point.payload}")
        else:
            print("No sample points found in collection")

        # Now count points matching our filter
        count_response = vectorstore.client.count(
            collection_name=vectorstore.collection_name,
            count_filter=search_filter
        )
        print(f"\nDebug: Found {count_response.count} matching points")
        
        if count_response.count > 0:
            # If points exist, get them all
            points = vectorstore.client.scroll(
                collection_name=vectorstore.collection_name,
                scroll_filter=search_filter,
                with_payload=True,
                limit=count_response.count  # Get all matching points
            )[0]  # [0] because scroll returns (points, next_page_offset)
            
            print(f"\nDebug: Retrieved {len(points)} points")
            print("First matching point metadata:")
            if points:
                print(points[0].payload)
            
            return True, points
            
        return False, []
        
    except Exception as e:
        print(f"\nError checking document existence:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        return False, []
    except Exception as e:
        print(f"Error checking document existence: {e}")
        return False, []

def process_pdf_and_stream(uploaded_pdf_path: str):
    """
    Process a PDF file and stream progress updates.
    
    Args:
        uploaded_pdf_path: Path to the PDF file
    """
    if not os.path.exists(uploaded_pdf_path):
        yield f"Error: File does not exist: {uploaded_pdf_path}"
        return

    try:
        yield f"Processing document: {uploaded_pdf_path}"
        pdf_document = fitz.open(uploaded_pdf_path)
        source_file_name = os.path.basename(uploaded_pdf_path)
        company_name = os.path.splitext(source_file_name)[0]

        # Initialize vector stores
        text_vectorstore, image_vectorstore = init_vector_stores()
        
        # Calculate content hash for duplicate detection
        content_hash = calculate_content_hash(uploaded_pdf_path)
        print(f"\nDebug: Content hash for {source_file_name}: {content_hash}")
        
        # --- Text ingestion ---
        exists, existing_points = check_document_exists(text_vectorstore, source_file_name, "text", content_hash)
        
        if exists:
            yield f"{source_file_name} already ingested (text) with {len(existing_points)} chunks. Skipping text ingestion."
            return

        documents = []
        for page_num, page in enumerate(pdf_document):
            text = page.get_text("text")
            if text.strip():
                metadata = {
                    "source_file": source_file_name,
                    "page_num": page_num + 1,
                    "company": company_name,
                    "content_type": "text",
                    "content_hash": content_hash,
                    "ingestion_timestamp": str(datetime.now()),
                }
                documents.append(Document(page_content=text, metadata=metadata))

        if documents:
            yield f"Extracted {len(documents)} text segments from PDF."
            text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                chunk_size=1000, chunk_overlap=100
            )
            text_chunks = text_splitter.split_documents(documents)

            # Generate deterministic UUIDs using the common function
            ids = [generate_doc_id(doc.metadata, i, "text") for i, doc in enumerate(text_chunks)]
            print("\nDebug: Adding text chunks to Qdrant")
            print(f"First chunk metadata sample: {text_chunks[0].metadata}")
            print(f"First chunk ID: {ids[0]}")
            text_vectorstore.add_documents(text_chunks, ids=ids)
            print("Debug: Verifying ingestion...")
            verify_points = text_vectorstore.client.scroll(
                collection_name=text_vectorstore.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="metadata.source_file",
                            match=models.MatchValue(value=source_file_name)
                        )
                    ]
                ),
                with_payload=True,
                limit=1
            )[0]
            if verify_points:
                print(f"Verification - First point payload: {verify_points[0].payload}")
            yield f"Added {len(text_chunks)} text chunks from {source_file_name} into Qdrant text vector store."
        else:
            yield "No text extracted from PDF."

        # --- Image ingestion ---
        exists, existing_img_points = check_document_exists(image_vectorstore, company_name, "image")

        if exists:
            yield f"{source_file_name} already exists in image store. Skipping image ingestion."
            return

        yield f"Extracting images from {source_file_name}..."
        img_processor = ImageDescription(uploaded_pdf_path)
        image_info = img_processor.get_image_information()

        if image_info:
            # Save metadata with timestamp
            metadata_path = f"metadata_{source_file_name}.json"
            metadata_with_timestamp = {
                "metadata": image_info,
                "ingestion_timestamp": str(datetime.now()),
                "source_file": source_file_name,
                "company": company_name
            }
            
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata_with_timestamp, f, indent=2)
            yield f"Saved image metadata to {metadata_path}"

            image_documents = img_processor.getRetriever(
                metadata_path, company_name)

            # Add additional metadata to each image document
            for doc in image_documents:
                doc.metadata.update({
                    "source_file": source_file_name,
                    "company": company_name,
                    "content_type": "image",
                    "ingestion_timestamp": str(datetime.now())
                })

            # Generate deterministic UUIDs using the common function
            img_ids = [generate_doc_id(doc.metadata, i, "image") for i, doc in enumerate(image_documents)]
            image_vectorstore.add_documents(image_documents, ids=img_ids)
            yield f"Added {len(image_documents)} image captions from {source_file_name} into Qdrant image vector store."
        else:
            yield "No images found in PDF."

        yield f"Completed ingestion for {source_file_name}"

    except Exception as e:
        yield f"Error while processing PDF {uploaded_pdf_path}: {str(e)}"
        import traceback
        yield f"Traceback: {traceback.format_exc()}"

    except Exception as e:
        yield f"Error while processing PDF {uploaded_pdf_path}: {str(e)}"
