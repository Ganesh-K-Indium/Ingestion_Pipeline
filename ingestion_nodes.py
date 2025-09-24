# mcp_ingestion/ingestion_nodes.py
"""
Streaming ingestion nodes for different sources.
Each node yields log messages instead of returning a state dict.
"""

import os
from utils.pdf_processor1 import process_pdf_and_stream
from utils.confluence import download_all_pdfs
from utils.gdrive import download_pdfs_from_folder
from utils.jira import download_attachments_from_project


def ingest_local_pdf(file_name: str):
    if not file_name:
        yield "Error: No file_name provided for local PDF ingestion."
        return

    file_path = os.path.join("10k_PDFs", file_name)
    if not os.path.exists(file_path):
        yield f"Error: File not found: {file_path}"
        return

    yield f"Processing local PDF: {file_name}"
    yield from process_pdf_and_stream(file_path)
    yield f"Completed ingestion for {file_name}"


def ingest_confluence(space_key: str):
    if not space_key:
        yield "Error: No space_key provided for Confluence ingestion."
        return

    yield f"Downloading PDFs from Confluence space {space_key}..."
    pdf_files = download_all_pdfs(space_key)

    if not pdf_files:
        yield "No PDFs found in the specified Confluence space."
        return

    for pdf_path in pdf_files:
        yield f"Downloaded: {pdf_path}"
        yield from process_pdf_and_stream(pdf_path)

    yield "Completed Confluence ingestion."


def ingest_jira(project_key: str):
    if not project_key:
        yield "Error: No project_key provided for Jira ingestion."
        return

    yield f"Fetching attachments from Jira project {project_key}..."
    pdf_files = download_attachments_from_project(project_key)

    if not pdf_files:
        yield "No attachments found in the specified Jira project."
        return

    for pdf_path in pdf_files:
        yield f"Downloaded from Jira: {pdf_path}"
        yield from process_pdf_and_stream(pdf_path)

    yield "Completed Jira ingestion."


def ingest_gdrive_folder(folder_id: str):
    if not folder_id:
        yield "Error: No folder_id provided for Google Drive ingestion."
        return

    yield f"Downloading PDFs from Google Drive folder {folder_id}..."
    pdf_files = download_pdfs_from_folder(folder_id)

    if not pdf_files:
        yield "No PDFs found in the specified Google Drive folder."
        return

    for pdf_path in pdf_files:
        yield f"Downloaded: {pdf_path}"
        yield from process_pdf_and_stream(pdf_path)

    yield "Completed Google Drive ingestion."
