"""
Issue Manager - Advanced issue operations and data processing
"""

import json
import os
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

try:
    from .jira_client import JiraClient
except ImportError:
    from jira_client import JiraClient


@dataclass
class IssueFilter:
    """Data class for issue filtering options."""
    project_key: Optional[str] = None
    issue_type: Optional[str] = None
    status: Optional[str] = None
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    priority: Optional[str] = None
    component: Optional[str] = None
    version: Optional[str] = None
    label: Optional[str] = None
    created_after: Optional[str] = None
    created_before: Optional[str] = None
    updated_after: Optional[str] = None
    updated_before: Optional[str] = None
    has_attachments: Optional[bool] = None
    text_search: Optional[str] = None


@dataclass
class IssueStats:
    """Data class for issue statistics."""
    total_issues: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    by_priority: Dict[str, int]
    by_assignee: Dict[str, int]
    issues_with_attachments: int
    avg_comments_per_issue: float
    date_range: Dict[str, str]


class IssueManager:
    """
    Advanced issue management with filtering, statistics, and data processing.
    """
    
    def __init__(self, jira_client: JiraClient):
        """
        Initialize Issue Manager.
        
        Args:
            jira_client: Configured JiraClient instance
        """
        self.client = jira_client
        
    def build_jql_from_filter(self, filter_obj: IssueFilter) -> str:
        """
        Build JQL query from filter object.
        
        Args:
            filter_obj: IssueFilter instance
            
        Returns:
            JQL query string
        """
        jql_parts = []
        
        if filter_obj.project_key:
            jql_parts.append(f'project = {filter_obj.project_key}')
            
        if filter_obj.issue_type:
            jql_parts.append(f'issuetype = "{filter_obj.issue_type}"')
            
        if filter_obj.status:
            jql_parts.append(f'status = "{filter_obj.status}"')
            
        if filter_obj.assignee:
            if filter_obj.assignee.lower() == 'unassigned':
                jql_parts.append('assignee is EMPTY')
            else:
                jql_parts.append(f'assignee = "{filter_obj.assignee}"')
                
        if filter_obj.reporter:
            jql_parts.append(f'reporter = "{filter_obj.reporter}"')
            
        if filter_obj.priority:
            jql_parts.append(f'priority = "{filter_obj.priority}"')
            
        if filter_obj.component:
            jql_parts.append(f'component = "{filter_obj.component}"')
            
        if filter_obj.version:
            jql_parts.append(f'fixVersion = "{filter_obj.version}"')
            
        if filter_obj.label:
            jql_parts.append(f'labels = "{filter_obj.label}"')
            
        if filter_obj.created_after:
            jql_parts.append(f'created >= "{filter_obj.created_after}"')
            
        if filter_obj.created_before:
            jql_parts.append(f'created <= "{filter_obj.created_before}"')
            
        if filter_obj.updated_after:
            jql_parts.append(f'updated >= "{filter_obj.updated_after}"')
            
        if filter_obj.updated_before:
            jql_parts.append(f'updated <= "{filter_obj.updated_before}"')
            
        if filter_obj.has_attachments is not None:
            if filter_obj.has_attachments:
                jql_parts.append('attachments is not EMPTY')
            else:
                jql_parts.append('attachments is EMPTY')
                
        if filter_obj.text_search:
            jql_parts.append(f'text ~ "{filter_obj.text_search}"')
        
        jql = ' AND '.join(jql_parts) if jql_parts else 'project is not EMPTY'
        return jql + ' ORDER BY created DESC'
    
    def get_filtered_issues(self, 
                           filter_obj: IssueFilter,
                           max_results: int = 100,
                           include_fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get issues based on filter criteria.
        
        Args:
            filter_obj: IssueFilter instance
            max_results: Maximum number of issues to return
            include_fields: Specific fields to include in response
            
        Returns:
            List of filtered issues
        """
        jql = self.build_jql_from_filter(filter_obj)
        
        # Default fields to include
        fields = include_fields or [
            'key', 'summary', 'status', 'issuetype', 'priority', 
            'assignee', 'reporter', 'created', 'updated', 'attachment',
            'comment', 'description', 'components', 'fixVersions', 'labels'
        ]
        
        print(f"🔍 Executing JQL: {jql}")
        
        # Handle pagination for large result sets
        all_issues = []
        start_at = 0
        batch_size = min(100, max_results)
        
        while len(all_issues) < max_results:
            remaining = max_results - len(all_issues)
            current_batch_size = min(batch_size, remaining)
            
            result = self.client.search_issues(
                jql=jql,
                start_at=start_at,
                max_results=current_batch_size,
                fields=fields
            )
            
            issues = result.get('issues', [])
            if not issues:
                break
                
            all_issues.extend(issues)
            
            # Check if we've reached the end
            if len(issues) < current_batch_size:
                break
                
            start_at += current_batch_size
        
        print(f"📊 Found {len(all_issues)} issues matching criteria")
        return all_issues
    
    def get_issues_with_attachments(self, 
                                   project_key: str,
                                   attachment_types: Optional[List[str]] = None,
                                   max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Get issues that have attachments, optionally filtered by attachment type.
        
        Args:
            project_key: Project key to search in
            attachment_types: List of file extensions to filter by (e.g., ['pdf', 'png'])
            max_results: Maximum number of issues to return
            
        Returns:
            List of issues with their attachments
        """
        filter_obj = IssueFilter(
            project_key=project_key,
            has_attachments=True
        )
        
        issues = self.get_filtered_issues(filter_obj, max_results)
        
        # Filter by attachment types if specified
        if attachment_types:
            filtered_issues = []
            for issue in issues:
                attachments = issue.get('fields', {}).get('attachment', [])
                matching_attachments = []
                
                for attachment in attachments:
                    filename = attachment.get('filename', '').lower()
                    if any(filename.endswith(f'.{ext.lower()}') for ext in attachment_types):
                        matching_attachments.append(attachment)
                
                if matching_attachments:
                    # Update the issue to only include matching attachments
                    issue['fields']['attachment'] = matching_attachments
                    filtered_issues.append(issue)
            
            issues = filtered_issues
            print(f"📎 Found {len(issues)} issues with {attachment_types} attachments")
        
        return issues
    
    def get_issue_statistics(self, 
                           filter_obj: IssueFilter,
                           max_issues: int = 1000) -> IssueStats:
        """
        Generate comprehensive statistics for filtered issues.
        
        Args:
            filter_obj: IssueFilter instance
            max_issues: Maximum number of issues to analyze
            
        Returns:
            IssueStats object with comprehensive statistics
        """
        issues = self.get_filtered_issues(filter_obj, max_issues)
        
        # Initialize counters
        status_counts = {}
        type_counts = {}
        priority_counts = {}
        assignee_counts = {}
        attachments_count = 0
        total_comments = 0
        created_dates = []
        
        for issue in issues:
            fields = issue.get('fields', {})
            
            # Status counts
            status = fields.get('status', {}).get('name', 'Unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Issue type counts
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
            
            # Comment counts
            comments = fields.get('comment', {}).get('comments', [])
            total_comments += len(comments)
            
            # Created dates
            created = fields.get('created', '')
            if created:
                created_dates.append(created)
        
        # Calculate date range
        date_range = {}
        if created_dates:
            created_dates.sort()
            date_range = {
                'earliest': created_dates[0],
                'latest': created_dates[-1]
            }
        
        # Calculate average comments
        avg_comments = total_comments / len(issues) if issues else 0
        
        return IssueStats(
            total_issues=len(issues),
            by_status=status_counts,
            by_type=type_counts,
            by_priority=priority_counts,
            by_assignee=assignee_counts,
            issues_with_attachments=attachments_count,
            avg_comments_per_issue=round(avg_comments, 2),
            date_range=date_range
        )
    
    def export_issues_to_json(self, 
                             issues: List[Dict[str, Any]], 
                             output_path: str,
                             include_metadata: bool = True) -> bool:
        """
        Export issues to JSON file with optional metadata.
        
        Args:
            issues: List of issues to export
            output_path: Path to save the JSON file
            include_metadata: Whether to include export metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            export_data = {
                'issues': issues,
                'total_count': len(issues)
            }
            
            if include_metadata:
                export_data['metadata'] = {
                    'export_timestamp': str(datetime.now()),
                    'exported_by': 'Jira MCP Tools',
                    'jira_instance': self.client.jira_url
                }
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"📁 Exported {len(issues)} issues to {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to export issues: {str(e)}")
            return False
    
    def get_recent_issues(self, 
                         project_key: str,
                         days_back: int = 7,
                         max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Get recently created or updated issues.
        
        Args:
            project_key: Project key to search in
            days_back: Number of days to look back
            max_results: Maximum number of issues to return
            
        Returns:
            List of recent issues
        """
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        filter_obj = IssueFilter(
            project_key=project_key,
            updated_after=cutoff_date
        )
        
        return self.get_filtered_issues(filter_obj, max_results)
    
    def search_issues_by_text(self, 
                             text: str,
                             project_key: Optional[str] = None,
                             max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Search issues by text content in summary, description, or comments.
        
        Args:
            text: Text to search for
            project_key: Optional project key to limit search
            max_results: Maximum number of results
            
        Returns:
            List of matching issues
        """
        filter_obj = IssueFilter(
            project_key=project_key,
            text_search=text
        )
        
        return self.get_filtered_issues(filter_obj, max_results)
    
    def get_issue_details_enhanced(self, issue_key: str) -> Dict[str, Any]:
        """
        Get enhanced issue details with processed data.
        
        Args:
            issue_key: Issue key to retrieve
            
        Returns:
            Enhanced issue dictionary with processed fields
        """
        issue = self.client.get_issue(
            issue_key, 
            expand=['comments', 'changelog', 'attachments']
        )
        
        # Process and enhance the issue data
        fields = issue.get('fields', {})
        
        # Extract key information
        enhanced_issue = {
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
            'resolved': fields.get('resolutiondate'),
            'components': [comp.get('name') for comp in fields.get('components', [])],
            'labels': fields.get('labels', []),
            'fix_versions': [v.get('name') for v in fields.get('fixVersions', [])],
            'attachments': self._process_attachments(fields.get('attachment', [])),
            'comments': self._process_comments(fields.get('comment', {}).get('comments', [])),
            'raw_issue': issue  # Include full raw data for reference
        }
        
        return enhanced_issue
    
    def _process_attachments(self, attachments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process attachment data for enhanced readability."""
        processed = []
        for att in attachments:
            processed.append({
                'id': att.get('id'),
                'filename': att.get('filename'),
                'size': att.get('size'),
                'mimetype': att.get('mimeType'),
                'created': att.get('created'),
                'author': att.get('author', {}).get('displayName'),
                'download_url': att.get('content')
            })
        return processed
    
    def _process_comments(self, comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process comment data for enhanced readability."""
        processed = []
        for comment in comments:
            processed.append({
                'id': comment.get('id'),
                'body': comment.get('body'),
                'created': comment.get('created'),
                'updated': comment.get('updated'),
                'author': comment.get('author', {}).get('displayName')
            })
        return processed