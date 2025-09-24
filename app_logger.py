# logger.py
import os
import datetime

def log_stream(payload: dict, stream, folder: str = "responses"):
    """
    Save streaming ingestion logs into a Markdown file.
    Yields each message while writing it to disk.
    """
    os.makedirs(folder, exist_ok=True)
    now = datetime.datetime.now()
    filename = now.strftime("%Y-%m-%d_%H-%M-%S") + ".md"
    filepath = os.path.join(folder, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Ingestion Log\n")
        f.write("=" * 50 + "\n")
        f.write(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Query: {payload.get('query','')}\n")
        f.write("=" * 50 + "\n\n")

        for message in stream:
            f.write(f"- {message}\n")
            f.flush()
            yield message

