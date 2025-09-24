# manager.py
from pydantic import BaseModel
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
load_dotenv()

class IngestionCommand(BaseModel):
    source: str  # local_pdf | confluence | jira | sharepoint | gdrive_folder
    file_name: Optional[str] = None
    space_key: Optional[str] = None
    project_key: Optional[str] = None
    file_url: Optional[str] = None
    folder_id: Optional[str] = None


class ManagerAgent:
    def __init__(self):
        base_llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.structured_llm = base_llm.with_structured_output(IngestionCommand)

    async def parse_ingestion_command(self, query: str) -> dict:
        system_prompt = """
        You are an assistant that extracts structured ingestion commands from user queries.

        Normalize user language to the following canonical sources:
        - local_pdf (accept synonyms like: pdf, document, file, amazon pdf, local file)
        - confluence (accept synonyms like: wiki, team wiki, knowledge base)
        - jira (accept synonyms like: tickets, issues, jira project)
        - sharepoint (accept synonyms like: microsoft sharepoint, ms sharepoint)
        - gdrive_folder (accept synonyms like: google drive, gdrive, drive folder)

        Rules:
        - Always map user phrasing to one of the canonical sources if possible.
        - If the source is "local_pdf" and the user provides an extra word that looks like a file name 
        (e.g., 'amazon','company', 'Amazon.pdf', 'report.pdf'), assign that to file_name.
        - Only treat input as a different source if it clearly matches one of the canonical sources.
        - If required info is missing, leave the field empty.
        - Required fields:
        * local_pdf → file_name
        * confluence → space_key
        * jira → project_key
        * sharepoint → file_url
        * gdrive_folder → folder_id
        - Output must strictly follow the IngestionCommand schema.
        """

        response = await self.structured_llm.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=query)]
        )

        command = response.dict()

        # --- Auto append .pdf for local_pdf ---
        if command.get("source") == "local_pdf" and command.get("file_name"):
            fn = command["file_name"]
            if not fn.lower().endswith(".pdf"):
                command["file_name"] = f"{fn}.pdf"

        return command
