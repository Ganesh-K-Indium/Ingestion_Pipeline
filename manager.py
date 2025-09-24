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

    def _clean_filename(self, filename: str) -> str:
        """Clean and normalize filenames while preserving important information."""
        if not filename:
            return filename
            
        # Remove common filler words
        filler_words = ['the', 'a', 'an', 'from', 'in', 'of', 'for']
        cleaned = ' '.join(word for word in filename.split() 
                         if word.lower() not in filler_words)
        
        # Remove any duplicate spaces
        cleaned = ' '.join(cleaned.split())
        
        # Remove special characters except dots and dashes
        allowed_chars = set('.-_ abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
        cleaned = ''.join(c for c in cleaned if c in allowed_chars)
        
        return cleaned.strip()

    async def parse_ingestion_command(self, query: str) -> dict:
        # Normalize query
        query = query.strip()
        
        system_prompt = """
        You are an intelligent assistant that extracts structured ingestion commands from user queries, 
        with strong pattern recognition for file names and sources.

        CANONICAL SOURCES AND PATTERNS:
        1. local_pdf
           - Keywords: pdf, document, file, report, local, upload, read, analyze
           - File patterns: 
             * Company names (e.g., "amazon", "meta", "google")
             * Report types (e.g., "q2 report", "annual report", "10k")
             * Any mention of PDF files or documents
           - Smart matching: Look for company names or document types anywhere in the query
           - Examples:
             * "process amazon document" → file_name: "amazon"
             * "read q2 report" → file_name: "q2 report"
             * "analyze META financial pdf" → file_name: "META"
             * "upload the NVIDIA file" → file_name: "NVIDIA"

        2. confluence
           - Keywords: wiki, confluence, knowledge base, team docs
           - Space key patterns: Look for space identifiers or project areas
           - Examples: "team wiki ENG", "confluence SALES", "kb HR"

        3. jira
           - Keywords: ticket, issue, jira, project, task
           - Project patterns: Look for project identifiers or team codes
           - Examples: "jira ENG", "tickets from MOBILE", "issues in BACKEND"

        4. sharepoint
           - Keywords: sharepoint, sp, microsoft docs, ms sharepoint
           - URL patterns: Look for sharepoint links or document identifiers

        5. gdrive_folder
           - Keywords: google drive, gdrive, drive folder, google docs
           - ID patterns: Look for folder identifiers or paths

        EXTRACTION RULES:
        1. File Name Detection (for local_pdf):
           - Remove common words like "the", "a", "an", "from", "in"
           - Identify company names, report types, or document descriptions
           - Accept file names with or without .pdf extension
           - Look for phrases between quotes if present
           - Default to entire remaining text if no clear file name pattern

        2. Priority Order:
           - Exact matches first (e.g., exact file names)
           - Company names or clear identifiers second
           - Descriptive phrases last

        3. Smart Cleanup:
           - Remove special characters except dots and dashes
           - Preserve case as provided by user
           - Handle multi-word file names properly

        Required fields per source:
        - local_pdf → file_name (auto-append .pdf if missing)
        - confluence → space_key (convert to uppercase)
        - jira → project_key (convert to uppercase)
        - sharepoint → file_url (preserve as is)
        - gdrive_folder → folder_id (preserve as is)

        IMPORTANT:
        - Process the ENTIRE query to find relevant information
        - Word order doesn't matter
        - Be flexible with naming patterns
        - When in doubt for local_pdf, include more text in file_name
        - Always return a valid IngestionCommand structure
        """

        response = await self.structured_llm.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=query)]
        )

        command = response.dict()

        # Post-process the command based on source
        if command.get("source"):
            if command["source"] == "local_pdf" and command.get("file_name"):
                # Clean and normalize the filename
                cleaned_name = self._clean_filename(command["file_name"])
                
                # Ensure we have something after cleaning
                if cleaned_name:
                    # Auto-append .pdf if missing
                    if not cleaned_name.lower().endswith('.pdf'):
                        cleaned_name = f"{cleaned_name}.pdf"
                    command["file_name"] = cleaned_name
                
            elif command["source"] == "confluence" and command.get("space_key"):
                # Convert space key to uppercase
                command["space_key"] = command["space_key"].upper()
                
            elif command["source"] == "jira" and command.get("project_key"):
                # Convert project key to uppercase
                command["project_key"] = command["project_key"].upper()

        return command
