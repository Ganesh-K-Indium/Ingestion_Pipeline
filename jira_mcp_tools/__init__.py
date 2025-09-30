"""
Jira MCP Tools Package

This package provides comprehensive Jira integration tools including:
- Issue retrieval and management
- Attachment listing and downloading
- Project exploration
- LLM agent integration for intelligent Jira operations
"""

from .jira_client import JiraClient
from .jira_agent import JiraAgent
from .attachment_manager import AttachmentManager
from .issue_manager import IssueManager

__all__ = [
    'JiraClient',
    'JiraAgent', 
    'AttachmentManager',
    'IssueManager'
]

__version__ = "1.0.0"