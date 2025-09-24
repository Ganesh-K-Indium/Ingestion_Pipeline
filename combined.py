# file: app.py
import streamlit as st
import requests
import os
import uuid
from md_logger import log_response  # only used in RAG tab
from app_logger import log_stream  # only used in Ingestion tab

# Server URLs
RAG_URL = os.getenv("RAG_URL", "http://localhost:8001/ask")
INGESTION_SERVER_URL = os.getenv("INGESTION_SERVER_URL", "http://localhost:8000")

# Streamlit page config
st.set_page_config(page_title="Agentic AI Hub", layout="wide")

# Tabs
tab1, tab2 = st.tabs(["📓 Secondary Research Agent", "📥 Ingestion Agent"])


# ==============================
# TAB 1: RAG UI
# ==============================
with tab1:
    # Tailwind CSS (for RAG UI styling)
    tailwind_cdn = """
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    """
    st.markdown(tailwind_cdn, unsafe_allow_html=True)

    # Dark theme styles
    st.markdown(
        """
        <style>
        body, .stApp {
            background-color: #0f172a; /* slate-900 */
            color: #f1f5f9;           /* slate-100 */
        }
        div[data-baseweb="textarea"] {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }
        div[data-baseweb="textarea"] textarea {
            border-radius: 12px;
            padding: 12px;
            font-size: 16px;
            box-shadow: none !important;
            outline: none !important;
        }
        @keyframes blink {
            0% { opacity: .2; }
            20% { opacity: 1; }
            100% { opacity: .2; }
        }
        .dot {
            height: 8px;
            width: 8px;
            background-color: #f3f4f6;
            border-radius: 50%;
            display: inline-block;
            animation: blink 1.4s infinite both;
        }
        .dot:nth-child(2) { animation-delay: 0.2s; }
        .dot:nth-child(3) { animation-delay: 0.4s; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # App header
    st.markdown(
        """
        <div class="container mx-auto px-6 py-6 text-center">
            <h1 class="text-4xl font-bold text-gray-100 mb-2">
                📓 Secondary Research Agent
            </h1>
            <p class="text-gray-400 text-lg">
                Your AI-powered knowledge manager
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    if "rag_messages" not in st.session_state:
        st.session_state.rag_messages = []

    # User input
    rag_query = st.chat_input("Ask me anything...")

    if rag_query:
        placeholder_id = str(uuid.uuid4())
        assistant_placeholder = {
            "id": placeholder_id,
            "role": "assistant",
            "content": None,
            "loading": True,
            "processing_started": False,
            "user_query": rag_query,
        }
        st.session_state.rag_messages.insert(0, assistant_placeholder)
        st.session_state.rag_messages.insert(0, {"id": str(uuid.uuid4()), "role": "user", "content": rag_query})

    # Render messages
    for msg in st.session_state.rag_messages:
        if msg["role"] == "user":
            st.markdown(
                f"""
                <div style='display:flex; justify-content:flex-end; margin-bottom:1rem;'>
                    <div style='max-width:70%; background:linear-gradient(135deg,#f87171,#ef4444); 
                    color:white; padding:12px 16px; border-radius:18px 18px 4px 18px; 
                    font-size:15px; line-height:1.5;'>
                        {msg['content']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            if msg.get("loading"):
                st.markdown(
                    f"""
                    <div style='display:flex; justify-content:flex-start; margin-bottom:1rem;'>
                        <div style='max-width:70%; background:#1f2937; color:#f3f4f6; padding:12px 16px; 
                        border-radius:18px 18px 18px 4px; font-size:15px; line-height:1.5; 
                        display:flex; align-items:center; gap:8px;'>
                            <span class="dot"></span>
                            <span class="dot"></span>
                            <span class="dot"></span>
                            <span style="opacity:0.7; margin-left:6px; font-size:13px;">Thinking…</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div style='display:flex; justify-content:flex-start; margin-bottom:1rem;'>
                        <div style='max-width:70%; background:#1f2937; color:#f3f4f6; 
                        padding:12px 16px; border-radius:18px 18px 18px 4px; 
                        font-size:15px; line-height:1.5;'>
                            {msg.get("content","")}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # Process assistant placeholder
    for msg in st.session_state.rag_messages:
        if msg["role"] == "assistant" and msg.get("loading") and not msg.get("processing_started"):
            msg["processing_started"] = True
            try:
                payload = {"query": msg.get("user_query", "")}
                response = requests.post(RAG_URL, json=payload)
                response.raise_for_status()
                data = response.json()
                try:
                    log_response(payload, data)
                except Exception:
                    pass

                answer = data.get("answer", {})
                if isinstance(answer, dict) and "logs" in answer:
                    source = answer.get("source", "unknown source")
                    details = []
                    if answer.get("space_key"):
                        details.append(f"space key {answer['space_key']}")
                    if answer.get("file_name"):
                        details.append(f"file {answer['file_name']}")
                    detail_text = ", ".join(details) if details else ""
                    final_text = f"Ingestion completed for {source} {detail_text}".strip()
                elif isinstance(answer, dict) and "Intermediate_message" in answer:
                    final_text = answer["Intermediate_message"]
                elif isinstance(answer, str):
                    final_text = answer
                else:
                    final_text = str(answer)
            except Exception as e:
                final_text = f"❌ Error: {e}"

            msg["content"] = final_text
            msg["loading"] = False
            st.rerun()
            break


from app_logger import log_stream  # make sure this is imported

# ==============================
# TAB 2: Ingestion UI
# ==============================
with tab2:
    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="font-size: 2.2rem; font-weight: 700; color: #3f3937; margin-bottom: 0.5rem;">
                📥 Ingestion Agent
            </h1>
            <p style="font-size: 1.1rem; color: #4b5563; max-width: 600px; margin: auto;">
                Ask me to ingest your files, reports, or documents. I’ll process them step by step and provide live updates.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Bubble styles ---
    st.markdown("""
    <style>
    .chat-container { margin: auto; padding: 1rem; display: flex; flex-direction: column; gap: 1rem; }
    .msg-row { display: flex; width: 100%; }
    .msg-row.user { justify-content: flex-end; }
    .msg-row.assistant { justify-content: flex-start; }
    .bubble {
        max-width: 70%; padding: 10px 14px; border-radius: 18px;
        font-size: 15px; line-height: 1.4; word-wrap: break-word;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .user-bubble {
        background: #25D366; color: white; border-radius: 18px 18px 4px 18px;
    }
    .assistant-bubble {
        background: #e5e7eb; color: #111827; border-radius: 18px 18px 18px 4px;
    }
    </style>
    """, unsafe_allow_html=True)

    if "ingestion_messages" not in st.session_state:
        st.session_state.ingestion_messages = []

    ingestion_query = st.chat_input("Ask me to ingest data (e.g. 'Ingest Q2 report PDF')...")

    chat_container = st.container()
    for msg in st.session_state.ingestion_messages:
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

    if ingestion_query:
        # Add user message
        user_msg = {"id": str(uuid.uuid4()), "role": "user", "content": ingestion_query}
        st.session_state.ingestion_messages.append(user_msg)

        chat_container.markdown(
            f"""
            <div class="chat-container">
                <div class="msg-row user">
                    <div class="bubble user-bubble">{ingestion_query}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Placeholder for assistant streaming
        placeholder = chat_container.empty()

        try:
            # Get server response (streaming)
            response = requests.get(
                f"{INGESTION_SERVER_URL}/ingest",
                params={"query": ingestion_query},
                stream=True
            )

            logs_accum = []

            # Use log_stream here ✅
            for msg in log_stream({"query": ingestion_query}, (line.decode("utf-8") for line in response.iter_lines() if line)):
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

            # Save assistant message in session
            st.session_state.ingestion_messages.append(
                {"id": str(uuid.uuid4()), "role": "assistant", "content": "\n".join(logs_accum)}
            )

        except Exception as e:
            st.session_state.ingestion_messages.append(
                {"id": str(uuid.uuid4()), "role": "assistant", "content": f"❌ Error: {e}"}
            )
