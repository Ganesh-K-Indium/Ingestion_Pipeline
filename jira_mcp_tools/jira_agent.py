"""
Jira Agent - Intelligent LLM agent for Jira operations with tool selection and execution
"""

import json
import os
import sys
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import openai
from dataclasses import asdict
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables from multiple possible locations
def load_env_files():
    """Load .env from current directory and parent directories"""
    current_dir = Path(__file__).parent
    
    # Try current directory first
    env_file = current_dir / '.env'
    if env_file.exists():
        load_dotenv(env_file)
        return
    
    # Try parent directory (main project directory)
    parent_env = current_dir.parent / '.env'
    if parent_env.exists():
        load_dotenv(parent_env)
        return
    
    # Try grandparent directory
    grandparent_env = current_dir.parent.parent / '.env'
    if grandparent_env.exists():
        load_dotenv(grandparent_env)
        return
    
    # Fallback to default load_dotenv (searches up the directory tree)
    load_dotenv()

load_env_files()

from .jira_client import JiraClient
from .issue_manager import IssueManager, IssueFilter
from .attachment_manager import AttachmentManager


class JiraAgent:
    """
    Intelligent LLM-powered agent for Jira operations.
    Automatically selects and executes appropriate tools based on user requests.
    """
    
    def __init__(self, 
                 jira_url: Optional[str] = None,
                 username: Optional[str] = None,
                 api_token: Optional[str] = None,
                 openai_api_key: Optional[str] = None,
                 base_download_path: str = "jira_attachments"):
        """
        Initialize Jira Agent with LLM capabilities.
        
        Args:
            jira_url: Jira instance URL
            username: Jira username/email
            api_token: Jira API token
            openai_api_key: OpenAI API key for LLM capabilities
            base_download_path: Base path for downloaded attachments
        """
        # Initialize Jira components
        self.jira_client = JiraClient(jira_url, username, api_token)
        self.issue_manager = IssueManager(self.jira_client)
        self.attachment_manager = AttachmentManager(self.jira_client, base_download_path)
        
        # Initialize OpenAI client
        openai_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        if not openai_key:
            raise ValueError("OpenAI API key is required for LLM agent functionality")
        
        self.openai_client = openai.OpenAI(api_key=openai_key)
        
        # Available tools and their descriptions
        self.available_tools = {
            'list_projects': {
                'description': 'List all accessible Jira projects',
                'parameters': ['expand'],
                'use_cases': ['show projects', 'list projects', 'what projects are available']
            },
            'get_project_info': {
                'description': 'Get detailed information about a specific project',
                'parameters': ['project_key', 'expand'],
                'use_cases': ['project details', 'project information', 'tell me about project']
            },
            'search_issues': {
                'description': 'Search for issues using flexible filters',
                'parameters': ['project_key', 'issue_type', 'status', 'assignee', 'text_search', 'has_attachments', 'max_results'],
                'use_cases': ['find issues', 'search issues', 'get issues', 'issues with attachments']
            },
            'get_issue_details': {
                'description': 'Get comprehensive details for a specific issue',
                'parameters': ['issue_key'],
                'use_cases': ['issue details', 'show issue', 'get issue information']
            },
            'list_attachments': {
                'description': 'List attachments in a project or issue',
                'parameters': ['project_key', 'issue_key', 'file_types'],
                'use_cases': ['list attachments', 'show attachments', 'what attachments', 'files attached']
            },
            'download_attachments': {
                'description': 'Download attachments from issues or projects',
                'parameters': ['project_key', 'issue_key', 'file_types', 'organize_by_type'],
                'use_cases': ['download attachments', 'get files', 'download files', 'save attachments']
            },
            'download_and_ingest': {
                'description': 'Download attachments and ingest them into vector database',
                'parameters': ['project_key', 'issue_key', 'file_types', 'company_name', 'cleanup_after_ingest'],
                'use_cases': ['download and ingest', 'ingest attachments', 'add to vector db', 'process attachments']
            }
        }
    
    def process_request(self, user_request: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Process a natural language request and execute appropriate Jira operations.
        
        Args:
            user_request: Natural language request from user
            context: Optional context from previous interactions
            
        Returns:
            Dictionary with results and execution details
        """
        print(f"🤖 Processing request: {user_request}")
        
        # Analyze the request using LLM
        analysis = self._analyze_request(user_request, context)
        
        if analysis.get('error'):
            return {
                'success': False,
                'error': analysis['error'],
                'request': user_request
            }
        
        # Execute the determined action
        try:
            result = self._execute_action(analysis)
            result['request_analysis'] = analysis
            result['original_request'] = user_request
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Execution error: {str(e)}",
                'request': user_request,
                'analysis': analysis
            }
    
    def _analyze_request(self, user_request: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Use LLM to analyze user request and determine appropriate action.
        """
        # Prepare context information
        context_info = ""
        if context:
            context_info = f"Previous context: {json.dumps(context, indent=2)}\n\n"
        
        # Create tool descriptions for the prompt
        tools_description = ""
        for tool_name, tool_info in self.available_tools.items():
            tools_description += f"- {tool_name}: {tool_info['description']}\n"
            tools_description += f"  Parameters: {', '.join(tool_info['parameters'])}\n"
            tools_description += f"  Use cases: {', '.join(tool_info['use_cases'])}\n\n"
        
        prompt = f"""
        You are an expert Jira analyst. Analyze the user's request and determine the best action to take.
        
        {context_info}User Request: "{user_request}"
        
        Available Tools:
        {tools_description}
        
        Please respond with a JSON object containing:
        {{
            "action": "tool_name_to_use",
            "parameters": {{
                "param1": "value1",
                "param2": "value2"
            }},
            "reasoning": "explanation of why this tool was chosen",
            "confidence": 0.95  // confidence level 0-1
        }}
        
        Guidelines:
        1. If a project key is mentioned (like PROJ-123), extract it
        2. If file types are mentioned (PDF, image, etc.), include them
        3. If numbers are mentioned, use them for limits/results
        4. For vague requests, choose the most appropriate broad action
        5. If the request is unclear, set confidence < 0.7
        
        Respond ONLY with the JSON object, no other text.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a Jira analysis expert. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            analysis_text = response.choices[0].message.content.strip()
            analysis = json.loads(analysis_text)
            
            return analysis
            
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse LLM response: {str(e)}"}
        except Exception as e:
            return {"error": f"LLM analysis failed: {str(e)}"}
    
    def _execute_action(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the action determined by the LLM analysis.
        """
        action = analysis.get('action')
        parameters = analysis.get('parameters', {})
        
        print(f"🔧 Executing action: {action} with parameters: {parameters}")
        
        if action == 'list_projects':
            projects = self.jira_client.get_projects(expand=parameters.get('expand'))
            return {
                'success': True,
                'action': action,
                'data': projects,
                'summary': f"Found {len(projects)} accessible projects"
            }
        
        elif action == 'get_project_info':
            project_key = parameters.get('project_key')
            if not project_key:
                return {'success': False, 'error': 'Project key is required'}
            
            # Convert to uppercase for API consistency
            project_key = project_key.upper()
            project_info = self.jira_client.get_project(project_key, parameters.get('expand'))
            return {
                'success': True,
                'action': action,
                'data': project_info,
                'summary': f"Retrieved information for project {project_key}"
            }
        
        elif action == 'search_issues':
            # Convert project_key to uppercase if provided
            project_key = parameters.get('project_key')
            if project_key:
                project_key = project_key.upper()
            
            filter_obj = IssueFilter(
                project_key=project_key,
                issue_type=parameters.get('issue_type'),
                status=parameters.get('status'),
                assignee=parameters.get('assignee'),
                has_attachments=parameters.get('has_attachments'),
                text_search=parameters.get('text_search')
            )
            
            max_results = parameters.get('max_results', 50)
            issues = self.issue_manager.get_filtered_issues(filter_obj, max_results)
            
            return {
                'success': True,
                'action': action,
                'data': issues,
                'summary': f"Found {len(issues)} issues matching criteria",
                'filter_used': asdict(filter_obj)
            }
        
        elif action == 'get_issue_details':
            issue_key = parameters.get('issue_key')
            if not issue_key:
                return {'success': False, 'error': 'Issue key is required'}
            
            issue_details = self.issue_manager.get_issue_details_enhanced(issue_key)
            return {
                'success': True,
                'action': action,
                'data': issue_details,
                'summary': f"Retrieved detailed information for {issue_key}"
            }
        
        elif action == 'list_attachments':
            project_key = parameters.get('project_key')
            issue_key = parameters.get('issue_key')
            file_types = parameters.get('file_types')
            
            # Convert project_key to uppercase if provided
            if project_key:
                project_key = project_key.upper()
            
            if issue_key:
                # List attachments for specific issue
                attachments = self.jira_client.get_issue_attachments(issue_key)
                if file_types:
                    attachments = [att for att in attachments 
                                 if any(att.get('filename', '').lower().endswith(f'.{ft.lower()}') 
                                       for ft in file_types)]
                return {
                    'success': True,
                    'action': action,
                    'data': attachments,
                    'summary': f"Found {len(attachments)} attachments in {issue_key}"
                }
            elif project_key:
                # List attachments for project
                attachment_summary = self.attachment_manager.list_project_attachments(
                    project_key, file_types
                )
                return {
                    'success': True,
                    'action': action,
                    'data': attachment_summary,
                    'summary': f"Found {attachment_summary['total_attachments']} attachments in {project_key}"
                }
            else:
                return {'success': False, 'error': 'Either project_key or issue_key is required'}
        
        elif action == 'download_attachments':
            project_key = parameters.get('project_key')
            issue_key = parameters.get('issue_key')
            file_types = parameters.get('file_types')
            organize_by_type = parameters.get('organize_by_type', False)
            
            # Normalize file_types parameter to handle both string and list inputs
            if file_types:
                if isinstance(file_types, str):
                    # Convert string to list and normalize case
                    file_types = [file_types.lower()]
                elif isinstance(file_types, list):
                    # Ensure all are lowercase
                    file_types = [ft.lower() for ft in file_types]
            
            # Convert project_key to uppercase if provided
            if project_key:
                project_key = project_key.upper()
            
            if issue_key:
                # Download from specific issue
                result = self.attachment_manager.download_issue_attachments(
                    issue_key, file_types
                )
                return {
                    'success': True,
                    'action': action,
                    'data': result,
                    'summary': f"Downloaded {result['downloaded']} files from {issue_key}"
                }
            elif project_key:
                # Download from project
                result = self.attachment_manager.download_project_attachments(
                    project_key, file_types, organize_by_type=organize_by_type
                )
                return {
                    'success': True,
                    'action': action,
                    'data': result,
                    'summary': f"Downloaded {result['total_files_downloaded']} files from {project_key}"
                }
            else:
                return {'success': False, 'error': 'Either project_key or issue_key is required'}
        
        elif action == 'download_and_ingest':
            project_key = parameters.get('project_key')
            issue_key = parameters.get('issue_key')
            file_types = parameters.get('file_types')
            company_name = parameters.get('company_name')
            cleanup_after_ingest = parameters.get('cleanup_after_ingest', True)
            
            # Normalize file_types parameter to handle both string and list inputs
            if file_types:
                if isinstance(file_types, str):
                    # Convert string to list and normalize case
                    file_types = [file_types.lower()]
                elif isinstance(file_types, list):
                    # Ensure all are lowercase
                    file_types = [ft.lower() for ft in file_types]
            
            # Convert project_key to uppercase if provided
            if project_key:
                project_key = project_key.upper()
            
            if issue_key:
                # Download and ingest from specific issue
                return self._download_and_ingest_issue_attachments(
                    issue_key, file_types, company_name, cleanup_after_ingest
                )
            elif project_key:
                # Download and ingest from project
                return self._download_and_ingest_project_attachments(
                    project_key, file_types, company_name, cleanup_after_ingest
                )
            else:
                return {'success': False, 'error': 'Either project_key or issue_key is required'}
        
        else:
            return {
                'success': False, 
                'error': f"Unknown action: {action}"
            }
    
    def get_conversation_summary(self, conversation_history: List[Dict]) -> str:
        """
        Generate a summary of the conversation history for context.
        
        Args:
            conversation_history: List of previous interactions
            
        Returns:
            Summary string for context
        """
        if not conversation_history:
            return ""
        
        # Create a concise summary of recent interactions
        summary_parts = []
        for interaction in conversation_history[-3:]:  # Last 3 interactions
            if interaction.get('success'):
                action = interaction.get('action', 'unknown')
                summary = interaction.get('summary', '')
                summary_parts.append(f"- {action}: {summary}")
        
        return "Recent context:\n" + "\n".join(summary_parts)
    
    def suggest_next_actions(self, current_result: Dict[str, Any]) -> List[str]:
        """
        Suggest logical next actions based on current result.
        
        Args:
            current_result: Result from current action
            
        Returns:
            List of suggested next actions
        """
        action = current_result.get('action')
        data = current_result.get('data', {})
        
        suggestions = []
        
        if action == 'list_projects':
            suggestions = [
                "Get detailed information about a specific project",
                "Search for issues in a project",
                "List attachments in a project"
            ]
        
        elif action == 'get_project_info':
            project_key = data.get('key')
            suggestions = [
                f"Search for issues in {project_key}",
                f"List attachments in {project_key}"
            ]
        
        elif action == 'search_issues':
            if isinstance(data, list) and data:
                suggestions = [
                    "Get detailed information about a specific issue",
                    "Download attachments from these issues"
                ]
        
        elif action == 'list_attachments':
            if isinstance(data, dict) and data.get('total_attachments', 0) > 0:
                suggestions = [
                    "Download the listed attachments",
                    "Filter attachments by file type"
                ]
        
        return suggestions
    
    def interactive_session(self):
        """
        Start an interactive session for continuous Jira operations.
        """
        print("🚀 Jira Agent Interactive Session Started")
        print("Type 'exit', 'quit', or 'bye' to end the session")
        print("Type 'help' for available commands\n")
        
        conversation_history = []
        
        while True:
            try:
                user_input = input("🎯 How can I help you with Jira? ").strip()
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("👋 Goodbye!")
                    break
                
                if user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                if not user_input:
                    continue
                
                # Get conversation context
                context = self.get_conversation_summary(conversation_history)
                
                # Process the request
                result = self.process_request(user_input, context if context else None)
                
                # Display results
                self._display_result(result)
                
                # Add to history
                conversation_history.append(result)
                
                # Suggest next actions
                if result.get('success'):
                    suggestions = self.suggest_next_actions(result)
                    if suggestions:
                        print(f"\n💡 Suggested next actions:")
                        for i, suggestion in enumerate(suggestions, 1):
                            print(f"   {i}. {suggestion}")
                        print()
                
            except KeyboardInterrupt:
                print("\n👋 Session interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {str(e)}")
    
    def _show_help(self):
        """Display help information."""
        print("\n📚 Jira Agent Help")
        print("=" * 50)
        print("You can ask me to help with various Jira operations using natural language:")
        print()
        
        for tool_name, tool_info in self.available_tools.items():
            print(f"🔧 {tool_name}:")
            print(f"   {tool_info['description']}")
            print(f"   Examples: {', '.join(tool_info['use_cases'][:2])}")
            print()
        
        print("Example requests:")
        print("- 'List all projects'")
        print("- 'Show me issues in project ABC with attachments'")
        print("- 'Download PDF files from issue ABC-123'")
        print()
    
    def _display_result(self, result: Dict[str, Any]):
        """Display formatted results to the user."""
        if result.get('success'):
            print(f"✅ {result.get('summary', 'Operation completed successfully')}")
            
            # Display key data points based on action type
            action = result.get('action')
            data = result.get('data')
            
            if action == 'list_projects' and isinstance(data, list):
                print(f"\n📋 Projects ({len(data)}):")
                for project in data[:5]:  # Show first 5
                    print(f"   • {project.get('key')} - {project.get('name')}")
                if len(data) > 5:
                    print(f"   ... and {len(data) - 5} more")
            
            elif action == 'search_issues' and isinstance(data, list):
                print(f"\n📄 Issues ({len(data)}):")
                for issue in data[:5]:  # Show first 5
                    key = issue.get('key')
                    summary = issue.get('fields', {}).get('summary', '')[:60]
                    print(f"   • {key}: {summary}...")
                if len(data) > 5:
                    print(f"   ... and {len(data) - 5} more")
            
            elif action == 'list_attachments':
                if isinstance(data, dict):
                    total = data.get('total_attachments', 0)
                    print(f"\n📎 Found {total} attachments")
                    if total > 0:
                        by_type = data.get('attachments_by_type', {})
                        print("   Types:", ", ".join([f"{k}({v})" for k, v in list(by_type.items())[:5]]))
                        
                        # Show attachment details
                        issues = data.get('issues', [])
                        print(f"\n📋 Issues with attachments:")
                        for issue in issues[:3]:  # Show first 3 issues
                            issue_key = issue.get('issue_key')
                            issue_summary = issue.get('issue_summary', '')[:50]
                            attachment_count = issue.get('attachment_count', 0)
                            print(f"   🔹 {issue_key}: {issue_summary}... ({attachment_count} attachments)")
                            
                            attachments = issue.get('attachments', [])
                            for att in attachments[:2]:  # Show first 2 attachments per issue
                                filename = att.get('filename', 'Unknown')
                                size = att.get('size_mb', 0)
                                print(f"      📎 {filename} ({size:.1f} MB)")
                        
                        if len(issues) > 3:
                            print(f"   ... and {len(issues) - 3} more issues")
                elif isinstance(data, list):
                    print(f"\n📎 Found {len(data)} attachments:")
                    for att in data[:5]:  # Show first 5 attachments
                        filename = att.get('filename', 'Unknown')
                        size = att.get('size', 0)
                        print(f"   📎 {filename} ({size} bytes)")
                    if len(data) > 5:
                        print(f"   ... and {len(data) - 5} more")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error occurred')}")
        
        print("-" * 60)
    
    def _download_and_ingest_issue_attachments(self, 
                                             issue_key: str,
                                             file_types: Optional[List[str]] = None,
                                             company_name: Optional[str] = None,
                                             cleanup_after_ingest: bool = True) -> Dict[str, Any]:
        """
        Download attachments from a specific issue and ingest them into vector database.
        
        Args:
            issue_key: Jira issue key
            file_types: List of file extensions to process
            company_name: Company name for document metadata
            cleanup_after_ingest: Whether to delete files after successful ingestion
            
        Returns:
            Dict with success status and processing results
        """
        try:
            # Step 1: Download attachments
            download_result = self.attachment_manager.download_issue_attachments(
                issue_key, file_types, create_issue_folder=True
            )
            
            if not download_result['downloaded']:
                return {
                    'success': True,
                    'action': 'download_and_ingest',
                    'message': f"No files downloaded from issue {issue_key}",
                    'download_result': download_result,
                    'ingestion_result': None
                }
            
            # Step 2: Process downloaded files
            ingestion_result = self._process_issue_files(
                issue_key, download_result, company_name, cleanup_after_ingest
            )
            
            # Handle case where ingestion fails
            if ingestion_result is None:
                ingestion_result = {'processed': 0, 'failed': 1, 'error': 'Ingestion process failed'}
            
            return {
                'success': True,
                'action': 'download_and_ingest',
                'download_result': download_result,
                'ingestion_result': ingestion_result,
                'summary': f"Downloaded {download_result['downloaded']} files and processed {ingestion_result.get('processed', 0) if ingestion_result else 0} files from {issue_key}"
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to download and ingest from issue {issue_key}: {str(e)}"
            }
    
    def _download_and_ingest_project_attachments(self, 
                                               project_key: str,
                                               file_types: Optional[List[str]] = None,
                                               company_name: Optional[str] = None,
                                               cleanup_after_ingest: bool = True) -> Dict[str, Any]:
        """
        Download attachments from all issues in a project and ingest them into vector database.
        
        Args:
            project_key: Jira project key
            file_types: List of file extensions to process
            company_name: Company name for document metadata
            cleanup_after_ingest: Whether to delete files after successful ingestion
            
        Returns:
            Dict with success status and processing results
        """
        try:
            # Step 1: Download attachments from project
            download_result = self.attachment_manager.download_project_attachments(
                project_key, file_types, organize_by_type=False
            )
            
            if not download_result.get('total_files_downloaded', 0):
                return {
                    'success': True,
                    'action': 'download_and_ingest',
                    'message': f"No files downloaded from project {project_key}",
                    'download_result': download_result,
                    'ingestion_result': None
                }
            
            # Step 2: Process downloaded files for each issue
            all_ingestion_results = []
            total_processed = 0
            
            for issue_data in download_result.get('issues', []):
                if issue_data.get('downloaded', 0) > 0:
                    issue_key = issue_data['issue_key']
                    ingestion_result = self._process_issue_files(
                        issue_key, issue_data, company_name, cleanup_after_ingest
                    )
                    all_ingestion_results.append({
                        'issue_key': issue_key,
                        'result': ingestion_result
                    })
                    total_processed += ingestion_result.get('processed', 0)
            
            return {
                'success': True,
                'action': 'download_and_ingest',
                'download_result': download_result,
                'ingestion_results': all_ingestion_results,
                'summary': f"Downloaded {download_result.get('total_files_downloaded', 0)} files and processed {total_processed} files from project {project_key}"
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to download and ingest from project {project_key}: {str(e)}"
            }
    
    def _process_issue_files(self, issue_key: str, download_data: Dict, 
                           company_name: Optional[str], cleanup_after_ingest: bool) -> Dict[str, Any]:
        """
        Process downloaded files for a specific issue using image data preparation.
        
        Args:
            issue_key: Jira issue key
            download_data: Download result data containing file information
            company_name: Company name for document metadata
            cleanup_after_ingest: Whether to delete files after ingestion
            
        Returns:
            Dict with processing results
        """
        try:
            # Import here to avoid circular imports
            import sys
            sys.path.append(str(Path(__file__).parent.parent))
            from utils.pdf_processor1 import process_pdf_and_stream
            
            print(f"🔍 Starting ingestion process for issue {issue_key}")
            
            # Get the download directory
            download_path = Path(download_data.get('download_path', ''))
            print(f"🔍 Download path: {download_path}")
            
            if not download_path.exists():
                print(f"❌ Download path does not exist")
                return {'processed': 0, 'error': 'Download path not found'}
            
            # Process each downloaded file
            processed_files = []
            failed_files = []
            
            files_to_process = download_data.get('files', [])
            print(f"🔍 Found {len(files_to_process)} files to process")
            
            for file_info in files_to_process:
                # Use 'local_path' key from attachment manager
                file_path = Path(file_info['local_path'])
                
                try:
                    print(f"📄 Processing {file_path.name} using PDF processor...")
                    
                    # Check if it's a PDF file
                    if not file_path.suffix.lower() == '.pdf':
                        failed_files.append({
                            'file': file_path.name,
                            'error': 'Not a PDF file - only PDFs are supported for ingestion'
                        })
                        continue
                    
                    # Use the robust PDF processor
                    processing_successful = False
                    processing_messages = []
                    
                    for message in process_pdf_and_stream(str(file_path)):
                        processing_messages.append(message)
                        print(f"   {message}")
                        
                        # Check for success indicators
                        if "Added" in message and "chunks" in message:
                            processing_successful = True
                        elif "already ingested" in message:
                            processing_successful = True
                        elif "Error" in message:
                            processing_successful = False
                            break
                    
                    if processing_successful:
                        processed_files.append({
                            'file': file_path.name,
                            'size_mb': file_info.get('size_mb', 0),
                            'status': 'processed',
                            'messages': processing_messages[-3:]  # Keep last 3 messages
                        })
                        
                        print(f"✅ Successfully ingested {file_path.name}")
                        
                        # Cleanup if requested
                        if cleanup_after_ingest:
                            file_path.unlink()
                            print(f"🗑️  Deleted {file_path.name}")
                    else:
                        failed_files.append({
                            'file': file_path.name,
                            'error': 'PDF processing failed',
                            'messages': processing_messages[-3:]  # Keep last 3 messages for debugging
                        })
                        
                except Exception as e:
                    failed_files.append({
                        'file': file_path.name,
                        'error': str(e)
                    })
                    print(f"❌ Failed to process {file_path.name}: {str(e)}")
            
            # Cleanup empty directory if all files were processed and cleaned up
            if cleanup_after_ingest and processed_files and not failed_files:
                try:
                    download_path.rmdir()
                    print(f"🗑️  Removed empty directory {download_path}")
                except OSError:
                    pass  # Directory not empty or other issue
            
            return {
                'processed': len(processed_files),
                'failed': len(failed_files),
                'processed_files': processed_files,
                'failed_files': failed_files
            }
            
        except Exception as e:
            print(f"❌ Exception in _process_issue_files: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return {
                'processed': 0,
                'error': f"Processing failed: {str(e)}"
            }