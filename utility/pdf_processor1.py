import os
import json
import uuid
import re
import hashlib
import traceback
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

def calculate_image_content_hash(image_data: bytes) -> str:
    """Calculate a deterministic hash of individual image content."""
    try:
        return hashlib.sha256(image_data).hexdigest()
    except Exception as e:
        print(f"Error calculating image content hash: {e}")
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

def check_document_exists(vectorstore, source_file_name: str, doc_type: str = "text", content_hash: str = None, image_hashes: dict = None) -> tuple[bool, list]:
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
        
        # For images, check individual image hashes first if available
        if doc_type == "image" and image_hashes:
            # Check if any individual image hash already exists
            for img_id, img_info in image_hashes.items():
                individual_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="metadata.content_type",
                            match=models.MatchValue(value="image")
                        ),
                        models.FieldCondition(
                            key="metadata.image_content_hash",
                            match=models.MatchValue(value=img_info["hash"])
                        )
                    ]
                )
                
                count_response = vectorstore.client.count(
                    collection_name=vectorstore.collection_name,
                    count_filter=individual_filter
                )
                
                if count_response.count > 0:
                    print(f"Found existing image with hash {img_info['hash'][:16]}...")
                    points = vectorstore.client.scroll(
                        collection_name=vectorstore.collection_name,
                        scroll_filter=individual_filter,
                        with_payload=True,
                        limit=count_response.count
                    )[0]
                    return True, points
            
            print("No individual image hashes found, checking by PDF content hash...")
        
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

def process_pdf_and_get_result(uploaded_pdf_path: str) -> dict:
    """
    Process a PDF file and return a structured result.
    
    Args:
        uploaded_pdf_path: Path to the PDF file
        
    Returns:
        dict: Processing result with status and details
    """
    result = {
        "success": False,
        "file_name": os.path.basename(uploaded_pdf_path),
        "text_processed": False,
        "text_already_existed": False,
        "text_chunks": 0,
        "images_processed": False,
        "images_already_existed": False,
        "image_count": 0,
        "messages": [],
        "error": None
    }
    
    try:
        # Collect all progress messages
        for message in process_pdf_and_stream(uploaded_pdf_path):
            result["messages"].append(message)
            
            # Parse key information from messages
            if "already ingested (text)" in message:
                result["text_already_existed"] = True
            elif "Added" in message and "text chunks" in message:
                result["text_processed"] = True
                # Extract chunk count from message like "Added 170 text chunks"
                match = re.search(r'Added (\d+) text chunks', message)
                if match:
                    result["text_chunks"] = int(match.group(1))
            elif "already exists in image store" in message:
                result["images_already_existed"] = True
            elif "Added" in message and "image captions" in message:
                result["images_processed"] = True
                # Extract image count from message like "Added 5 image captions"
                match = re.search(r'Added (\d+) image captions', message)
                if match:
                    result["image_count"] = int(match.group(1))
            elif "Error" in message:
                result["error"] = message
                
        # Determine overall success
        result["success"] = not result["error"] and (
            result["text_processed"] or result["text_already_existed"] or
            result["images_processed"] or result["images_already_existed"]
        )
        
    except Exception as e:
        result["error"] = f"Processing failed: {str(e)}"
        result["messages"].append(result["error"])
        
    return result

def process_pdf_and_stream(uploaded_pdf_path: str):
    """
    Process a PDF file and stream progress updates.
    
    Args:
        uploaded_pdf_path: Path to the PDF file
    """
    if not os.path.exists(uploaded_pdf_path):
        yield f"Error: File does not exist: {uploaded_pdf_path}"
        yield f"Failed to process {os.path.basename(uploaded_pdf_path)} - file not found"
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
        text_already_exists = False
        exists, existing_points = check_document_exists(text_vectorstore, source_file_name, "text", content_hash)
        
        if exists:
            text_already_exists = True
            yield f"{source_file_name} already ingested (text) with {len(existing_points)} chunks. Skipping text ingestion."

        if not text_already_exists:
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
        image_already_exists = False
        
        # Use enhanced ImageDescription class that extracts and hashes images in one pass
        yield f"Extracting and hashing images from {source_file_name}..."
        img_processor = ImageDescription(uploaded_pdf_path)
        
        # Get both image information and hashes in a single extraction
        image_info, image_hashes = img_processor.get_image_information()
        
        if image_hashes:
            yield f"Found {len(image_hashes)} images to check for duplicates."
            
            # First try to find by individual image hashes (most precise)
            exists, existing_img_points = check_document_exists(image_vectorstore, source_file_name, "image", content_hash, image_hashes)
            
            # If not found by individual hashes, try by PDF content hash (for newer ingestions)
            if not exists:
                exists, existing_img_points = check_document_exists(image_vectorstore, source_file_name, "image", content_hash)
            
            # If still not found, try by source file only (for backward compatibility)
            if not exists:
                exists, existing_img_points = check_document_exists(image_vectorstore, source_file_name, "image")

            if exists:
                image_already_exists = True
                yield f"{source_file_name} already exists in image store (duplicate images detected). Skipping image ingestion."

        if not image_already_exists:
            if image_info:  # image_info already extracted above
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

                # Get image documents with enhanced metadata including hashes
                image_documents = img_processor.getRetriever(
                    metadata_path, company_name, image_hashes)

                # Add additional metadata to each image document
                for i, doc in enumerate(image_documents):
                    # The getRetriever already adds image_content_hash, just add the standard metadata
                    doc.metadata.update({
                        "source_file": source_file_name,
                        "company": company_name,
                        "content_type": "image",
                        "content_hash": content_hash,  # PDF content hash
                        "ingestion_timestamp": str(datetime.now())
                    })

                # Generate deterministic UUIDs using the common function
                img_ids = [generate_doc_id(doc.metadata, i, "image") for i, doc in enumerate(image_documents)]
                image_vectorstore.add_documents(image_documents, ids=img_ids)
                yield f"Added {len(image_documents)} image captions from {source_file_name} into Qdrant image vector store."
            else:
                yield "No images found in PDF."

        # Final completion status
        if text_already_exists and image_already_exists:
            yield f"Completed processing for {source_file_name} - file already existed, no new ingestion needed"
        elif text_already_exists:
            yield f"Completed processing for {source_file_name} - text already existed, images processed"
        elif image_already_exists:
            yield f"Completed processing for {source_file_name} - images already existed, text processed"
        else:
            yield f"Completed ingestion for {source_file_name}"

    except Exception as e:
        yield f"Error while processing PDF {uploaded_pdf_path}: {str(e)}"
        import traceback
        yield f"Traceback: {traceback.format_exc()}"

    except Exception as e:
        yield f"Error while processing PDF {uploaded_pdf_path}: {str(e)}"
