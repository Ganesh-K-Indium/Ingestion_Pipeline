# file: logger.py
import os
import json
import datetime

def format_graph_output(data: dict) -> str:
    """Format RAG graph output into Markdown with clear headings."""
    lines = []
    answer_data = data.get("answer", {})

    if "messages" in answer_data:
        lines.append("## Messages")
        for i, msg in enumerate(answer_data["messages"], 1):
            if isinstance(msg, dict):
                content = msg.get("content", "")
                msg_type = msg.get("type", "unknown")
                lines.append(f"### Message {i} ({msg_type})")
                lines.append(content)
            else:
                lines.append(f"- {msg}")
            lines.append("")

    if "Intermediate_message" in answer_data:
        lines.append("## Intermediate Message")
        lines.append(answer_data["Intermediate_message"])
        lines.append("")

    if "documents" in answer_data:
        lines.append("## Documents")
        for i, doc in enumerate(answer_data["documents"], 1):
            lines.append(f"### Document {i}")
            if isinstance(doc, dict):
                if "metadata" in doc:
                    lines.append(f"**Metadata:** {json.dumps(doc['metadata'], indent=2)}")
                if "page_content" in doc:
                    lines.append(f"**Content:** {doc['page_content']}")
                if "type" in doc:
                    lines.append(f"**Type:** {doc['type']}")
            else:
                lines.append(str(doc))
            lines.append("")

    if "retry_count" in answer_data:
        lines.append("## Retry Count")
        lines.append(str(answer_data["retry_count"]))
        lines.append("")

    if "tool_calls" in answer_data:
        lines.append("## Tool Calls")
        for i, call in enumerate(answer_data["tool_calls"], 1):
            if isinstance(call, dict):
                lines.append(f"- Tool: {call.get('tool', 'Unknown')}")
                if "input" in call:
                    lines.append(f"- Input: {json.dumps(call.get('input'), indent=2)}")
                if "output" in call:
                    lines.append(f"- Output: {json.dumps(call.get('output'), indent=2)}")
            else:
                lines.append(str(call))
            lines.append("")

    return "\n".join(lines)


def format_ingestion_output(data: dict) -> str:
    """Format ingestion response into Markdown with clear logs."""
    lines = []
    answer_data = data.get("answer", {})

    if "request" in answer_data:
        lines.append("## Request")
        lines.append(answer_data["request"])
        lines.append("")

    if "logs" in answer_data:
        lines.append("## Ingestion Logs")
        for i, log in enumerate(answer_data["logs"], 1):
            lines.append(f"{i}. {log}")
        lines.append("")

    lines.append("## File Information")
    lines.append(f"- Source: {answer_data.get('source')}")
    lines.append(f"- File Name: {answer_data.get('file_name')}")
    lines.append(f"- Space Key: {answer_data.get('space_key')}")
    lines.append(f"- Ticket ID: {answer_data.get('ticket_id')}")
    lines.append(f"- File URL: {answer_data.get('file_url')}")
    lines.append("")

    return "\n".join(lines)


def log_response(payload: dict, data: dict, folder: str = "responses") -> None:
    """Save formatted response to markdown log."""
    os.makedirs(folder, exist_ok=True)

    now = datetime.datetime.now()
    filename = now.strftime("%Y-%m-%d_%H-%M-%S") + ".md"
    filepath = os.path.join(folder, filename)

    # Decide which formatter to use
    if "logs" in data.get("answer", {}):
        content = format_ingestion_output(data)
    else:
        content = format_graph_output(data)

    md_content = (
        "# API Response Report\n"
        + "="*50 + "\n"
        + f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        + f"Query: {payload['query']}\n"
        + "="*50 + "\n\n"
        + content
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)
