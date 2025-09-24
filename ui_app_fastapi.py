# ui_app.py
import streamlit as st
import os
import uuid
import datetime
import asyncio
from app_logger import log_response
from fastmcp.client import Client  # use fastmcp client

# --- MCP server connection ---
MCP_URL = os.getenv("MCP_URL", "http://localhost:8002")

# --- Streamlit setup ---
st.set_page_config(page_title="Agentic AI Notebook", layout="wide")

# --- Session state ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "ingest_mode" not in st.session_state:
    st.session_state.ingest_mode = None  # "choose" | "local" | "confluence" | "jira" | "gdrive"

# --- Chat input ---
user_query = st.chat_input("Ask me anything...")

if user_query:
    st.session_state.messages.insert(
        0, {"id": str(uuid.uuid4()), "role": "user", "content": user_query}
    )
    if user_query.strip().lower() == "ingest":
        st.session_state.ingest_mode = "choose"

# --- Render chat messages ---
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).markdown(msg["content"])

# --- Ingestion workflow ---
if st.session_state.ingest_mode == "choose":
    st.markdown("### Choose ingestion source:")
    col1, col2, col3, col4 = st.columns(4)
    if col1.button("📂 Local PDF"):
        st.session_state.ingest_mode = "local"
    if col2.button("📘 Confluence"):
        st.session_state.ingest_mode = "confluence"
    if col3.button("📊 Jira"):
        st.session_state.ingest_mode = "jira"
    if col4.button("🟦 Google Drive"):
        st.session_state.ingest_mode = "gdrive"

elif st.session_state.ingest_mode == "local":
    file_name = st.text_input("Enter local file name (inside ./10k_PDFs):")
    if st.button("Start Local Ingestion"):
        client = run_async(get_mcp_client())
        state = run_async(client.call_tool("ingest_local", {"file_name": file_name}))
        st.session_state.messages.insert(
            0, {"id": str(uuid.uuid4()), "role": "assistant", "content": str(state)}
        )
        log_response({"file_name": file_name}, state)
        with open("logs_local.md", "a") as f:
            f.write(f"\n## Local Ingestion {datetime.datetime.now()}\n{state}\n")
        st.session_state.ingest_mode = None
        st.rerun()

elif st.session_state.ingest_mode == "confluence":
    space_key = st.text_input("Enter Confluence space key:")
    if st.button("Start Confluence Ingestion"):
        client = run_async(get_mcp_client())
        state = run_async(client.call_tool("ingest_confluence", {"space_key": space_key}))
        st.session_state.messages.insert(
            0, {"id": str(uuid.uuid4()), "role": "assistant", "content": str(state)}
        )
        log_response({"space_key": space_key}, state)
        with open("logs_confluence.md", "a") as f:
            f.write(f"\n## Confluence Ingestion {datetime.datetime.now()}\n{state}\n")
        st.session_state.ingest_mode = None
        st.rerun()

elif st.session_state.ingest_mode == "jira":
    project_key = st.text_input("Enter Jira project key:")
    if st.button("Start Jira Ingestion"):
        client = run_async(get_mcp_client())
        state = run_async(client.call_tool("ingest_jira", {"project_key": project_key}))
        st.session_state.messages.insert(
            0, {"id": str(uuid.uuid4()), "role": "assistant", "content": str(state)}
        )
        log_response({"project_key": project_key}, state)
        with open("logs_jira.md", "a") as f:
            f.write(f"\n## Jira Ingestion {datetime.datetime.now()}\n{state}\n")
        st.session_state.ingest_mode = None
        st.rerun()

elif st.session_state.ingest_mode == "gdrive":
    folder_id = st.text_input("Enter Google Drive folder ID:")
    if st.button("Start GDrive Ingestion"):
        client = run_async(get_mcp_client())
        state = run_async(client.call_tool("ingest_gdrive", {"folder_id": folder_id}))
        st.session_state.messages.insert(
            0, {"id": str(uuid.uuid4()), "role": "assistant", "content": str(state)}
        )
        log_response({"folder_id": folder_id}, state)
        with open("logs_gdrive.md", "a") as f:
            f.write(f"\n## GDrive Ingestion {datetime.datetime.now()}\n{state}\n")
        st.session_state.ingest_mode = None
        st.rerun()
