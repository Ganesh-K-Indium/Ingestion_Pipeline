# server.py
import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from manager import ManagerAgent
from app_logger import log_stream

app = FastAPI()
agent = ManagerAgent()


async def async_stream(gen):
    for item in gen:
        yield item + "\n"
        await asyncio.sleep(0)


def stream_with_logging(payload, generator):
    return log_stream(payload, generator)


@app.get("/ingest")
async def ingest(query: str):
    parsed = await agent.parse_ingestion_command(query)

    source = parsed.get("source")
    payload = {"query": query, **parsed}

    if source == "local_pdf" and parsed.get("file_name"):
        from ingestion_nodes import ingest_local_pdf
        stream = ingest_local_pdf(parsed["file_name"])
    elif source == "confluence" and parsed.get("space_key"):
        from ingestion_nodes import ingest_confluence
        stream = ingest_confluence(parsed["space_key"])
    elif source == "jira" and parsed.get("project_key"):
        from ingestion_nodes import ingest_jira 
        stream = ingest_jira(parsed["project_key"])
    elif source == "gdrive_folder" and parsed.get("folder_id"):
        from ingestion_nodes import ingest_gdrive_folder
        stream = ingest_gdrive_folder(parsed["folder_id"])
    elif source == "sharepoint" and parsed.get("file_url"):
        from ingestion_nodes import ingest_sharepoint
        stream = ingest_sharepoint(parsed["file_url"])
    else:
        return {"error": f"Incomplete or unknown source: {source}"}

    return StreamingResponse(
        async_stream(stream_with_logging(payload, stream)),
        media_type="text/plain",
    )
