"""
Jira Client - Core connection and authentication handler for Jira integration
"""

import os
import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import base64
from urllib.parse import urljoin
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from multiple possible locations
def load_env_files():
    """Load .env from current directory and parent directories"""
    current_dir = Path(__file__).parent
    
    # Try current directory first
    env_file = current_dir / '.env'
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✅ Loaded .env from: {env_file}")
        return
    
    # Try parent directory (main project directory)
    parent_env = current_dir.parent / '.env'
    if parent_env.exists():
        load_dotenv(parent_env)
        print(f"✅ Loaded .env from: {parent_env}")
        return
    
    # Try grandparent directory
    grandparent_env = current_dir.parent.parent / '.env'
    if grandparent_env.exists():
        load_dotenv(grandparent_env)
        print(f"✅ Loaded .env from: {grandparent_env}")
        return
    
    # Fallback to default load_dotenv (searches up the directory tree)
    load_dotenv()
    print("ℹ️  Using default .env search")

load_env_files()




class JiraClient:
    """
    Core Jira client for handling authentication and basic API operations.
    """
    
    def __init__(self, 
                 jira_url: Optional[str] = None,
                 username: Optional[str] = None, 
                 api_token: Optional[str] = None,
                 verify_ssl: bool = True):
        """
        Initialize Jira client with authentication credentials.
        
        Args:
            jira_url: Jira instance URL (e.g., 'https://company.atlassian.net')
            username: Jira username/email
            api_token: Jira API token
            verify_ssl: Whether to verify SSL certificates
        """
        self.jira_url = jira_url or os.getenv('JIRA_URL')
        self.username = username or os.getenv('JIRA_USERNAME')
        self.api_token = api_token or os.getenv('JIRA_API_TOKEN')
        self.verify_ssl = verify_ssl
        
        if not all([self.jira_url, self.username, self.api_token]):
            raise ValueError(
                "Missing required Jira credentials. Please provide jira_url, username, and api_token "
                "either as parameters or environment variables (JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN)"
            )
        
        # Ensure URL format is correct
        if not self.jira_url.startswith(('http://', 'https://')):
            self.jira_url = f"https://{self.jira_url}"
        
        if not self.jira_url.endswith('/'):
            self.jira_url += '/'
            
        # Setup authentication
        self.auth = base64.b64encode(
            f"{self.username}:{self.api_token}".encode()
        ).decode()
        
        self.headers = {
            'Authorization': f'Basic {self.auth}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Test connection
        self._test_connection()
    
    def _test_connection(self) -> bool:
        """Test the Jira connection and authentication."""
        try:
            response = self._make_request('GET', 'rest/api/3/myself')
            if response.status_code == 200:
                user_info = response.json()
                print(f"✅ Connected to Jira as: {user_info.get('displayName', self.username)}")
                return True
            else:
                raise Exception(f"Authentication failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Failed to connect to Jira: {str(e)}")
            raise
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make HTTP request to Jira API with proper error handling.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments for requests
            
        Returns:
            requests.Response object
        """
        url = urljoin(self.jira_url, endpoint)
        
        # Merge headers
        headers = self.headers.copy()
        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))
        
        kwargs['headers'] = headers
        kwargs['verify'] = self.verify_ssl
        
        try:
            response = requests.request(method, url, **kwargs)
            
            # Log request details for debugging
            print(f"🌐 {method} {endpoint} -> {response.status_code}")
            
            if response.status_code >= 400:
                print(f"❌ Error {response.status_code}: {response.text}")
            
            return response
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {str(e)}")
            raise
    
    def get_projects(self, expand: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all accessible projects.
        
        Args:
            expand: Additional information to include (e.g., 'description,lead')
            
        Returns:
            List of project dictionaries
        """
        params = {}
        if expand:
            params['expand'] = expand
            
        response = self._make_request('GET', 'rest/api/3/project', params=params)
        response.raise_for_status()
        return response.json()
    
    def get_project(self, project_key: str, expand: Optional[str] = None) -> Dict[str, Any]:
        """
        Get specific project details.
        
        Args:
            project_key: Project key (e.g., 'PROJ')
            expand: Additional information to include
            
        Returns:
            Project dictionary
        """
        params = {}
        if expand:
            params['expand'] = expand
            
        response = self._make_request(
            'GET', 
            f'rest/api/3/project/{project_key}', 
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def search_issues(self, 
                     jql: str,
                     start_at: int = 0,
                     max_results: int = 50,
                     fields: Optional[List[str]] = None,
                     expand: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Search for issues using JQL.
        
        Args:
            jql: JQL query string
            start_at: Starting index for pagination
            max_results: Maximum number of results to return
            fields: List of fields to include in response
            expand: List of additional data to expand
            
        Returns:
            Search results dictionary
        """
        data = {
            'jql': jql,
            'maxResults': max_results
        }
        
        # Add nextPageToken for pagination (if start_at > 0)
        # For the new API, we use nextPageToken instead of startAt
        # For now, we'll use maxResults and handle pagination differently
        
        if fields:
            data['fields'] = fields
        if expand:
            data['expand'] = expand
            
        response = self._make_request(
            'POST', 
            'rest/api/3/search/jql',
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def get_issue(self, 
                  issue_key: str,
                  fields: Optional[List[str]] = None,
                  expand: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get specific issue details.
        
        Args:
            issue_key: Issue key (e.g., 'PROJ-123')
            fields: List of fields to include
            expand: List of additional data to expand
            
        Returns:
            Issue dictionary
        """
        params = {}
        if fields:
            params['fields'] = ','.join(fields)
        if expand:
            params['expand'] = ','.join(expand)
            
        response = self._make_request(
            'GET', 
            f'rest/api/3/issue/{issue_key}',
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def get_issue_attachments(self, issue_key: str) -> List[Dict[str, Any]]:
        """
        Get all attachments for a specific issue.
        
        Args:
            issue_key: Issue key (e.g., 'PROJ-123')
            
        Returns:
            List of attachment dictionaries
        """
        issue = self.get_issue(issue_key, fields=['attachment'])
        return issue.get('fields', {}).get('attachment', [])
    
    def download_attachment(self, attachment_url: str, local_path: str) -> bool:
        """
        Download an attachment from Jira.
        
        Args:
            attachment_url: URL of the attachment
            local_path: Local path to save the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            response = self._make_request('GET', attachment_url.replace(self.jira_url, ''))
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Downloaded: {os.path.basename(local_path)}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to download attachment: {str(e)}")
            return False
    
    def get_project_issues(self, 
                          project_key: str,
                          issue_type: Optional[str] = None,
                          status: Optional[str] = None,
                          assignee: Optional[str] = None,
                          max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Get issues from a specific project with optional filters.
        
        Args:
            project_key: Project key
            issue_type: Filter by issue type
            status: Filter by status
            assignee: Filter by assignee
            max_results: Maximum number of results
            
        Returns:
            List of issues
        """
        jql_parts = [f'project = {project_key}']
        
        if issue_type:
            jql_parts.append(f'issuetype = "{issue_type}"')
        if status:
            jql_parts.append(f'status = "{status}"')
        if assignee:
            jql_parts.append(f'assignee = "{assignee}"')
            
        jql = ' AND '.join(jql_parts)
        jql += ' ORDER BY created DESC'
        
        result = self.search_issues(jql, max_results=max_results)
        return result.get('issues', [])
    
    def get_issue_types(self, project_key: str) -> List[Dict[str, Any]]:
        """
        Get available issue types for a project.
        
        Args:
            project_key: Project key
            
        Returns:
            List of issue type dictionaries
        """
        response = self._make_request(
            'GET', 
            f'rest/api/3/project/{project_key}/statuses'
        )
        response.raise_for_status()
        return response.json()
    
    def get_project_components(self, project_key: str) -> List[Dict[str, Any]]:
        """
        Get project components.
        
        Args:
            project_key: Project key
            
        Returns:
            List of component dictionaries
        """
        response = self._make_request(
            'GET', 
            f'rest/api/3/project/{project_key}/components'
        )
        response.raise_for_status()
        return response.json()
    
    def get_project_versions(self, project_key: str) -> List[Dict[str, Any]]:
        """
        Get project versions.
        
        Args:
            project_key: Project key
            
        Returns:
            List of version dictionaries
        """
        response = self._make_request(
            'GET', 
            f'rest/api/3/project/{project_key}/versions'
        )
        response.raise_for_status()
        return response.json()