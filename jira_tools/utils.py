"""
Utils - Helper functions for Jira MCP tools
"""

import os
import json
import requests
import base64
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from urllib.parse import urljoin
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class IssueFilter:
    """Simple data class for issue filtering."""
    project_key: Optional[str] = None
    issue_type: Optional[str] = None
    status: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None
    has_attachments: Optional[bool] = None
    text_search: Optional[str] = None


class JiraClient:
    """Simple Jira client for API operations."""
    
    def __init__(self):
        """Initialize with environment variables."""
        self.jira_url = os.getenv('JIRA_URL')
        self.username = os.getenv('JIRA_USERNAME')
        self.api_token = os.getenv('JIRA_API_TOKEN')
        
        if not all([self.jira_url, self.username, self.api_token]):
            raise ValueError("Missing Jira credentials in environment variables")
        
        # Ensure URL format
        if not self.jira_url.startswith(('http://', 'https://')):
            self.jira_url = f"https://{self.jira_url}"
        if not self.jira_url.endswith('/'):
            self.jira_url += '/'
        
        # Setup authentication
        auth_string = f"{self.username}:{self.api_token}"
        self.auth_header = base64.b64encode(auth_string.encode()).decode()
        
        self.headers = {
            'Authorization': f'Basic {self.auth_header}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request to Jira API."""
        url = urljoin(self.jira_url, endpoint)
        kwargs['headers'] = self.headers
        return requests.request(method, url, **kwargs)
    
    def get_projects(self, expand: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all projects."""
        params = {'expand': expand} if expand else {}
        response = self._make_request('GET', 'rest/api/3/project', params=params)
        response.raise_for_status()
        return response.json()
    
    def get_project(self, project_key: str, expand: Optional[str] = None) -> Dict[str, Any]:
        """Get specific project."""
        params = {'expand': expand} if expand else {}
        response = self._make_request('GET', f'rest/api/3/project/{project_key}', params=params)
        response.raise_for_status()
        return response.json()
    
    def search_issues(self, jql: str, max_results: int = 50, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Search issues using JQL."""
        data = {
            'jql': jql,
            'maxResults': max_results,
            'fields': fields or ['key', 'summary', 'status', 'issuetype', 'priority', 'assignee', 'reporter', 'created', 'updated', 'attachment', 'comment']
        }
        response = self._make_request('POST', 'rest/api/3/search/jql', json=data)
        response.raise_for_status()
        return response.json()
    
    def get_issue(self, issue_key: str, expand: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get specific issue."""
        params = {}
        if expand:
            params['expand'] = ','.join(expand)
        response = self._make_request('GET', f'rest/api/3/issue/{issue_key}', params=params)
        response.raise_for_status()
        return response.json()
    
    def get_issue_attachments(self, issue_key: str) -> List[Dict[str, Any]]:
        """Get attachments for an issue."""
        issue = self.get_issue(issue_key, expand=['attachment'])
        return issue.get('fields', {}).get('attachment', [])
    
    def download_attachment(self, attachment_url: str, local_path: str) -> bool:
        """Download an attachment."""
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            response = self._make_request('GET', attachment_url.replace(self.jira_url, ''))
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
            return True
        except Exception:
            return False


class JiraUtils:
    """Utility functions for Jira operations."""
    
    def __init__(self):
        """Initialize utilities."""
        self.jira_client = JiraClient()
    
    def create_issue_filter(self, **kwargs) -> IssueFilter:
        """Create an IssueFilter from keyword arguments."""
        return IssueFilter(**kwargs)
    
    def build_jql_from_filter(self, filter_obj: IssueFilter) -> str:
        """Build JQL query from filter object."""
        parts = []
        
        if filter_obj.project_key:
            parts.append(f'project = {filter_obj.project_key}')
        if filter_obj.issue_type:
            parts.append(f'issuetype = "{filter_obj.issue_type}"')
        if filter_obj.status:
            parts.append(f'status = "{filter_obj.status}"')
        if filter_obj.assignee:
            if filter_obj.assignee.lower() == 'unassigned':
                parts.append('assignee is EMPTY')
            else:
                parts.append(f'assignee = "{filter_obj.assignee}"')
        if filter_obj.priority:
            parts.append(f'priority = "{filter_obj.priority}"')
        if filter_obj.has_attachments is not None:
            if filter_obj.has_attachments:
                parts.append('attachments is not EMPTY')
            else:
                parts.append('attachments is EMPTY')
        if filter_obj.text_search:
            parts.append(f'text ~ "{filter_obj.text_search}"')
        
        jql = ' AND '.join(parts) if parts else 'project is not EMPTY'
        return jql + ' ORDER BY created DESC'
    
    def process_issue_details(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Process and enhance issue details."""
        fields = issue.get('fields', {})
        
        return {
            'key': issue.get('key'),
            'summary': fields.get('summary', ''),
            'description': fields.get('description', ''),
            'status': fields.get('status', {}).get('name'),
            'issue_type': fields.get('issuetype', {}).get('name'),
            'priority': fields.get('priority', {}).get('name') if fields.get('priority') else None,
            'assignee': fields.get('assignee', {}).get('displayName') if fields.get('assignee') else None,
            'reporter': fields.get('reporter', {}).get('displayName') if fields.get('reporter') else None,
            'created': fields.get('created'),
            'updated': fields.get('updated'),
            'attachments': self._process_attachments(fields.get('attachment', [])),
            'comments': self._process_comments(fields.get('comment', {}).get('comments', [])),
            'raw_issue': issue
        }
    
    def _process_attachments(self, attachments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process attachment data."""
        return [{
            'id': att.get('id'),
            'filename': att.get('filename'),
            'size': att.get('size'),
            'mimetype': att.get('mimeType'),
            'created': att.get('created'),
            'author': att.get('author', {}).get('displayName'),
            'download_url': att.get('content')
        } for att in attachments]
    
    def _process_comments(self, comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process comment data."""
        return [{
            'id': comment.get('id'),
            'body': comment.get('body'),
            'created': comment.get('created'),
            'author': comment.get('author', {}).get('displayName')
        } for comment in comments]
    
    def process_attachment_info(self, attachment: Dict[str, Any]) -> Dict[str, Any]:
        """Process single attachment info."""
        filename = attachment.get('filename', 'unknown')
        size = attachment.get('size', 0)
        
        return {
            'id': attachment.get('id'),
            'filename': filename,
            'file_extension': Path(filename).suffix.lower(),
            'size_bytes': size,
            'size_human': self._format_file_size(size),
            'mimetype': attachment.get('mimeType', ''),
            'created': attachment.get('created', ''),
            'author': attachment.get('author', {}).get('displayName', ''),
            'download_url': attachment.get('content', '')
        }
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def filter_attachments_by_type(self, attachments: List[Dict[str, Any]], file_types: List[str]) -> List[Dict[str, Any]]:
        """Filter attachments by file types."""
        filtered = []
        for att in attachments:
            filename = att.get('filename', '').lower()
            if any(filename.endswith(f'.{ft.lower()}') for ft in file_types):
                filtered.append(att)
        return filtered
    
    def list_project_attachments(self, project_key: str, file_types: Optional[List[str]] = None, max_issues: int = 50) -> Dict[str, Any]:
        """List all attachments in a project."""
        filter_obj = self.create_issue_filter(project_key=project_key, has_attachments=True)
        jql = self.build_jql_from_filter(filter_obj)
        result = self.jira_client.search_issues(jql=jql, max_results=max_issues)
        
        issues = result.get('issues', [])
        total_attachments = 0
        issues_data = []
        
        for issue in issues:
            issue_key = issue.get('key')
            attachments = issue.get('fields', {}).get('attachment', [])
            
            if file_types:
                attachments = self.filter_attachments_by_type(attachments, file_types)
            
            if attachments:
                issues_data.append({
                    'issue_key': issue_key,
                    'summary': issue.get('fields', {}).get('summary', ''),
                    'attachment_count': len(attachments),
                    'attachments': [self.process_attachment_info(att) for att in attachments]
                })
                total_attachments += len(attachments)
        
        return {
            'project_key': project_key,
            'total_issues_with_attachments': len(issues_data),
            'total_attachments': total_attachments,
            'issues': issues_data
        }
    
    def download_issue_attachments(self, issue_key: str, file_types: Optional[List[str]] = None, 
                                 base_path: str = "jira_attachments", organize_by_type: bool = False) -> Dict[str, Any]:
        """Download attachments from a specific issue."""
        attachments = self.jira_client.get_issue_attachments(issue_key)
        
        if file_types:
            attachments = self.filter_attachments_by_type(attachments, file_types)
        
        download_dir = Path(base_path) / issue_key
        download_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            'issue_key': issue_key,
            'total_attachments': len(attachments),
            'downloaded': 0,
            'failed': 0,
            'download_path': str(download_dir),
            'files': []
        }
        
        for attachment in attachments:
            filename = attachment.get('filename', 'unknown')
            download_url = attachment.get('content')
            local_path = download_dir / filename
            
            # Handle duplicate filenames
            counter = 1
            original_path = local_path
            while local_path.exists():
                name = original_path.stem
                ext = original_path.suffix
                local_path = download_dir / f"{name}_{counter}{ext}"
                counter += 1
            
            success = self.jira_client.download_attachment(download_url, str(local_path))
            
            file_info = {
                'filename': filename,
                'local_path': str(local_path),
                'size_bytes': attachment.get('size', 0),
                'download_success': success
            }
            
            results['files'].append(file_info)
            
            if success:
                results['downloaded'] += 1
            else:
                results['failed'] += 1
        
        return results
    
    def download_project_attachments(self, project_key: str, file_types: Optional[List[str]] = None,
                                   base_path: str = "jira_attachments", organize_by_type: bool = False) -> Dict[str, Any]:
        """Download attachments from all issues in a project."""
        project_dir = Path(base_path) / project_key
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Get issues with attachments
        filter_obj = self.create_issue_filter(project_key=project_key, has_attachments=True)
        jql = self.build_jql_from_filter(filter_obj)
        result = self.jira_client.search_issues(jql=jql, max_results=100)
        issues = result.get('issues', [])
        
        project_results = {
            'project_key': project_key,
            'total_issues_processed': len(issues),
            'total_files_downloaded': 0,
            'total_files_failed': 0,
            'download_path': str(project_dir),
            'issues': []
        }
        
        for issue in issues:
            issue_key = issue.get('key')
            issue_result = self.download_issue_attachments(
                issue_key, file_types, str(project_dir), organize_by_type
            )
            
            project_results['issues'].append(issue_result)
            project_results['total_files_downloaded'] += issue_result['downloaded']
            project_results['total_files_failed'] += issue_result['failed']
        
        return project_results
    
    def generate_issue_statistics(self, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate statistics from a list of issues."""
        if not issues:
            return {'total_issues': 0}
        
        status_counts = {}
        type_counts = {}
        priority_counts = {}
        assignee_counts = {}
        attachments_count = 0
        
        for issue in issues:
            fields = issue.get('fields', {})
            
            # Status counts
            status = fields.get('status', {}).get('name', 'Unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Type counts
            issue_type = fields.get('issuetype', {}).get('name', 'Unknown')
            type_counts[issue_type] = type_counts.get(issue_type, 0) + 1
            
            # Priority counts
            priority = fields.get('priority', {})
            priority_name = priority.get('name', 'None') if priority else 'None'
            priority_counts[priority_name] = priority_counts.get(priority_name, 0) + 1
            
            # Assignee counts
            assignee = fields.get('assignee', {})
            assignee_name = assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'
            assignee_counts[assignee_name] = assignee_counts.get(assignee_name, 0) + 1
            
            # Attachment counts
            attachments = fields.get('attachment', [])
            if attachments:
                attachments_count += 1
        
        return {
            'total_issues': len(issues),
            'by_status': status_counts,
            'by_type': type_counts,
            'by_priority': priority_counts,
            'by_assignee': assignee_counts,
            'issues_with_attachments': attachments_count
        }