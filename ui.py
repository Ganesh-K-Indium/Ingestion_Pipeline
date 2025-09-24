import streamlit as st
import os
import uuid
import requests

INGESTION_SERVER_URL = os.getenv("INGESTION_SERVER_URL", "http://localhost:8000")

st.set_page_config(page_title="Ingestion Agent", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []
# --- App Heading ---
st.markdown(
    """
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="font-size: 2.2rem; font-weight: 700; color: #1f2937; margin-bottom: 0.5rem;">
            📥 Ingestion Agent
        </h1>
        <p style="font-size: 1.1rem; color: #4b5563; max-width: 600px; margin: auto;">
            Ask me to ingest your files, reports, or documents. I’ll process them step by step and provide live updates.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Bubble Styles ---
st.markdown("""
<style>
.chat-container {
    
    margin: auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}
.msg-row {
    display: flex;
    width: 100%;
}
.msg-row.user { justify-content: flex-end; }
.msg-row.assistant { justify-content: flex-start; }
.bubble {
    max-width: 70%;
    padding: 10px 14px;
    border-radius: 18px;
    font-size: 15px;
    line-height: 1.4;
    word-wrap: break-word;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.user-bubble {
    background: #25D366; /* WhatsApp green */
    color: white;
    border-radius: 18px 18px 4px 18px;
}
.assistant-bubble {
    background: #e5e7eb;
    color: #111827;
    border-radius: 18px 18px 18px 4px;
}
</style>
""", unsafe_allow_html=True)

# --- Chat input ---
user_query = st.chat_input("Ask me to ingest data (e.g. 'Ingest Q2 report PDF')...")

# --- Render existing messages (persisted only once) ---
chat_container = st.container()
for msg in st.session_state.messages:
    row_class = "user" if msg["role"] == "user" else "assistant"
    bubble_class = "user-bubble" if msg["role"] == "user" else "assistant-bubble"
    chat_container.markdown(
        f"""
        <div class="chat-container">
            <div class="msg-row {row_class}">
                <div class="bubble {bubble_class}">{msg["content"].replace("\n","<br>")}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

if user_query:
    # Add user message
    user_msg = {"id": str(uuid.uuid4()), "role": "user", "content": user_query}
    st.session_state.messages.append(user_msg)

    chat_container.markdown(
        f"""
        <div class="chat-container">
            <div class="msg-row user">
                <div class="bubble user-bubble">{user_query}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Placeholder for assistant streaming
    placeholder = chat_container.empty()

    # Stream assistant response
    response = requests.get(f"{INGESTION_SERVER_URL}/ingest", params={"query": user_query}, stream=True)
    logs_accum = []
    for line in response.iter_lines():
        if line:
            msg = line.decode("utf-8")
            logs_accum.append(msg)
            placeholder.markdown(
                f"""
                <div class="chat-container">
                    <div class="msg-row assistant">
                        <div class="bubble assistant-bubble">{"<br>".join(logs_accum)}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Finalize assistant message
    st.session_state.messages.append(
        {"id": str(uuid.uuid4()), "role": "assistant", "content": "\n".join(logs_accum)}
    )
