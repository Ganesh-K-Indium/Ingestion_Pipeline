import streamlit as st
import requests

st.set_page_config(page_title="Universal Ingestor", layout="wide")
st.title("📑 Universal Ingestor Demo")

FASTAPI_URL = "http://localhost:8000/ingest"  # adjust if running elsewhere

query = st.text_input("Enter your query", placeholder="e.g., List PDFs from Confluence space DOCS")

if st.button("Run Query"):
    if not query.strip():
        st.warning("Please enter a query.")
    else:
        with st.spinner("Running ingestion..."):
            response = requests.get(FASTAPI_URL, params={"query": query}, stream=True)

            if response.status_code != 200:
                st.error(f"Error: {response.status_code} - {response.text}")
            else:
                st.subheader("📦 Streaming Output")
                output_box = st.empty()
                collected = []

                for line in response.iter_lines():
                    if line:
                        text = line.decode("utf-8")
                        collected.append(text)
                        # Live update UI
                        output_box.text("\n".join(collected))

                st.success("✅ Completed")
                st.json(collected)
