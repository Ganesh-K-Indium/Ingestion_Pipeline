"""
Attachment Manager - Comprehensive attachment handling and processing
"""

import os
import json
import shutil
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    from .jira_client import JiraClient
    from .issue_manager import IssueManager
except ImportError:
    from jira_client import JiraClient
    from issue_manager import IssueManager


class AttachmentManager:
    """
    Advanced attachment management for Jira issues including download, 
    organization, and processing capabilities.
    """
    
    def __init__(self, jira_client: JiraClient, base_download_path: str = "jira_attachments"):
        """
        Initialize Attachment Manager.
        
        Args:
            jira_client: Configured JiraClient instance
            base_download_path: Base directory for downloaded attachments
        """
        self.client = jira_client
        self.issue_manager = IssueManager(jira_client)
        self.base_download_path = Path(base_download_path)
        self.base_download_path.mkdir(exist_ok=True)
        
        # Supported file types for processing
        self.supported_types = {
            'documents': ['.pdf', '.doc', '.docx', '.txt', '.rtf'],
            'images': ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'],
            'spreadsheets': ['.xls', '.xlsx', '.csv'],
            'presentations': ['.ppt', '.pptx'],
            'archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
            'code': ['.py', '.js', '.java', '.cpp', '.c', '.h', '.cs', '.php'],
            'data': ['.json', '.xml', '.yaml', '.yml', '.sql']
        }
    
    def list_project_attachments(self, 
                                project_key: str,
                                file_types: Optional[List[str]] = None,
                                max_issues: int = 100) -> Dict[str, Any]:
        """
        List all attachments in a project with detailed information.
        
        Args:
            project_key: Project key to search
            file_types: List of file extensions to filter by (e.g., ['pdf', 'png'])
            max_issues: Maximum number of issues to check
            
        Returns:
            Dictionary with attachment summary and details
        """
        print(f"🔍 Scanning attachments in project {project_key}...")
        
        issues_with_attachments = self.issue_manager.get_issues_with_attachments(
            project_key, 
            file_types, 
            max_issues
        )
        
        attachment_summary = {
            'project_key': project_key,
            'total_issues_with_attachments': len(issues_with_attachments),
            'total_attachments': 0,
            'attachments_by_type': {},
            'attachments_by_size': {'small': 0, 'medium': 0, 'large': 0},
            'issues': []
        }
        
        for issue in issues_with_attachments:
            issue_key = issue.get('key')
            issue_summary = issue.get('fields', {}).get('summary', '')
            attachments = issue.get('fields', {}).get('attachment', [])
            
            issue_info = {
                'issue_key': issue_key,
                'issue_summary': issue_summary,
                'attachment_count': len(attachments),
                'attachments': []
            }
            
            for attachment in attachments:
                attachment_info = self._process_attachment_info(attachment)
                issue_info['attachments'].append(attachment_info)
                
                # Update summary statistics
                attachment_summary['total_attachments'] += 1
                
                # Count by type
                file_ext = attachment_info['file_extension']
                if file_ext in attachment_summary['attachments_by_type']:
                    attachment_summary['attachments_by_type'][file_ext] += 1
                else:
                    attachment_summary['attachments_by_type'][file_ext] = 1
                
                # Count by size
                size = attachment_info['size_bytes']
                if size < 1024 * 1024:  # < 1MB
                    attachment_summary['attachments_by_size']['small'] += 1
                elif size < 10 * 1024 * 1024:  # < 10MB
                    attachment_summary['attachments_by_size']['medium'] += 1
                else:  # >= 10MB
                    attachment_summary['attachments_by_size']['large'] += 1
            
            attachment_summary['issues'].append(issue_info)
        
        return attachment_summary
    
    def download_issue_attachments(self, 
                                  issue_key: str,
                                  file_types: Optional[List[str]] = None,
                                  create_issue_folder: bool = True) -> Dict[str, Any]:
        """
        Download all attachments from a specific issue.
        
        Args:
            issue_key: Issue key to download attachments from
            file_types: List of file extensions to download (None = all)
            create_issue_folder: Whether to create a subfolder for the issue
            
        Returns:
            Download results dictionary
        """
        print(f"📥 Downloading attachments from {issue_key}...")
        
        attachments = self.client.get_issue_attachments(issue_key)
        
        if not attachments:
            print(f"📎 No attachments found in {issue_key}")
            return {
                'issue_key': issue_key,
                'total_attachments': 0,
                'downloaded': 0,
                'failed': 0,
                'skipped': 0,
                'files': []
            }
        
        # Create download directory
        if create_issue_folder:
            download_dir = self.base_download_path / issue_key
        else:
            download_dir = self.base_download_path
        
        download_dir.mkdir(exist_ok=True)
        
        results = {
            'issue_key': issue_key,
            'total_attachments': len(attachments),
            'downloaded': 0,
            'failed': 0,
            'skipped': 0,
            'download_path': str(download_dir),
            'files': []
        }
        
        for attachment in attachments:
            filename = attachment.get('filename', 'unknown')
            file_ext = Path(filename).suffix.lower()
            
            # Check file type filter
            if file_types and not any(filename.lower().endswith(f'.{ft.lower()}') for ft in file_types):
                print(f"⏭️  Skipping {filename} (not in requested file types)")
                results['skipped'] += 1
                continue
            
            # Download the file
            download_url = attachment.get('content')
            local_path = download_dir / filename
            
            # Handle duplicate filenames
            counter = 1
            original_path = local_path
            while local_path.exists():
                stem = original_path.stem
                suffix = original_path.suffix
                local_path = download_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            
            success = self.client.download_attachment(download_url, str(local_path))
            
            file_info = {
                'filename': filename,
                'local_path': str(local_path),
                'size_bytes': attachment.get('size', 0),
                'mimetype': attachment.get('mimeType', ''),
                'download_success': success,
                'created': attachment.get('created', ''),
                'author': attachment.get('author', {}).get('displayName', '')
            }
            
            results['files'].append(file_info)
            
            if success:
                results['downloaded'] += 1
            else:
                results['failed'] += 1
        
        print(f"✅ Download complete: {results['downloaded']}/{results['total_attachments']} files")
        return results
    
    def download_project_attachments(self, 
                                   project_key: str,
                                   file_types: Optional[List[str]] = None,
                                   max_issues: int = 50,
                                   organize_by_type: bool = False) -> Dict[str, Any]:
        """
        Download attachments from multiple issues in a project.
        
        Args:
            project_key: Project key to download from
            file_types: List of file extensions to download
            max_issues: Maximum number of issues to process
            organize_by_type: Whether to organize files by type
            
        Returns:
            Comprehensive download results
        """
        print(f"📦 Starting bulk download for project {project_key}...")
        
        project_results = {
            'project_key': project_key,
            'total_issues_processed': 0,
            'total_files_downloaded': 0,
            'total_files_failed': 0,
            'total_files_skipped': 0,
            'download_path': str(self.base_download_path / project_key),
            'issues': []
        }
        
        # Get issues with attachments
        issues_with_attachments = self.issue_manager.get_issues_with_attachments(
            project_key, 
            file_types, 
            max_issues
        )
        
        # Create project directory
        project_dir = self.base_download_path / project_key
        project_dir.mkdir(exist_ok=True)
        
        for issue in issues_with_attachments:
            issue_key = issue.get('key')
            
            # Temporarily set base path to project directory
            original_base_path = self.base_download_path
            self.base_download_path = project_dir
            
            try:
                # Download issue attachments
                issue_results = self.download_issue_attachments(
                    issue_key, 
                    file_types, 
                    create_issue_folder=not organize_by_type
                )
                
                # If organizing by type, move files to type-based folders
                if organize_by_type:
                    self._organize_files_by_type(issue_results['files'], project_dir)
                
                project_results['issues'].append(issue_results)
                project_results['total_files_downloaded'] += issue_results['downloaded']
                project_results['total_files_failed'] += issue_results['failed']
                project_results['total_files_skipped'] += issue_results['skipped']
                project_results['total_issues_processed'] += 1
                
            finally:
                # Restore original base path
                self.base_download_path = original_base_path
        
        # Save download manifest
        manifest_path = project_dir / 'download_manifest.json'
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(project_results, f, indent=2, default=str)
        
        print(f"🎉 Bulk download complete: {project_results['total_files_downloaded']} files from {project_results['total_issues_processed']} issues")
        return project_results
    
    def get_attachment_statistics(self, project_key: str) -> Dict[str, Any]:
        """
        Generate comprehensive attachment statistics for a project.
        
        Args:
            project_key: Project key to analyze
            
        Returns:
            Detailed statistics dictionary
        """
        attachment_data = self.list_project_attachments(project_key, max_issues=1000)
        
        stats = {
            'project_key': project_key,
            'summary': {
                'total_issues_with_attachments': attachment_data['total_issues_with_attachments'],
                'total_attachments': attachment_data['total_attachments'],
                'average_attachments_per_issue': 0
            },
            'file_types': attachment_data['attachments_by_type'],
            'size_distribution': attachment_data['attachments_by_size'],
            'categorized_types': self._categorize_file_types(attachment_data['attachments_by_type']),
            'top_issues_by_attachment_count': []
        }
        
        # Calculate averages
        if attachment_data['total_issues_with_attachments'] > 0:
            stats['summary']['average_attachments_per_issue'] = round(
                attachment_data['total_attachments'] / attachment_data['total_issues_with_attachments'], 2
            )
        
        # Find top issues by attachment count
        issues_sorted = sorted(
            attachment_data['issues'], 
            key=lambda x: x['attachment_count'], 
            reverse=True
        )
        stats['top_issues_by_attachment_count'] = issues_sorted[:10]
        
        return stats
    
    def _process_attachment_info(self, attachment: Dict[str, Any]) -> Dict[str, Any]:
        """Process raw attachment data into structured format."""
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
    
    def _categorize_file_types(self, file_type_counts: Dict[str, int]) -> Dict[str, Dict[str, int]]:
        """Categorize file types into logical groups."""
        categorized = {category: {} for category in self.supported_types.keys()}
        categorized['other'] = {}
        
        for ext, count in file_type_counts.items():
            categorized_type = None
            
            for category, extensions in self.supported_types.items():
                if ext in extensions:
                    categorized[category][ext] = count
                    categorized_type = category
                    break
            
            if not categorized_type:
                categorized['other'][ext] = count
        
        # Remove empty categories
        return {k: v for k, v in categorized.items() if v}
    
    def _organize_files_by_type(self, files: List[Dict[str, Any]], base_dir: Path) -> None:
        """Organize downloaded files into type-based subdirectories."""
        for file_info in files:
            if not file_info['download_success']:
                continue
                
            current_path = Path(file_info['local_path'])
            if not current_path.exists():
                continue
            
            filename = current_path.name
            file_ext = current_path.suffix.lower()
            
            # Determine target directory
            target_category = 'other'
            for category, extensions in self.supported_types.items():
                if file_ext in extensions:
                    target_category = category
                    break
            
            target_dir = base_dir / target_category
            target_dir.mkdir(exist_ok=True)
            
            target_path = target_dir / filename
            
            # Handle duplicates
            counter = 1
            original_target = target_path
            while target_path.exists():
                stem = original_target.stem
                suffix = original_target.suffix
                target_path = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            
            # Move file
            shutil.move(str(current_path), str(target_path))
            file_info['local_path'] = str(target_path)
    
    def search_attachments_by_name(self, 
                                  project_key: str,
                                  filename_pattern: str,
                                  case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """
        Search for attachments by filename pattern.
        
        Args:
            project_key: Project key to search in
            filename_pattern: Pattern to search for in filenames
            case_sensitive: Whether search should be case sensitive
            
        Returns:
            List of matching attachments with issue information
        """
        attachment_data = self.list_project_attachments(project_key)
        matching_attachments = []
        
        search_pattern = filename_pattern if case_sensitive else filename_pattern.lower()
        
        for issue in attachment_data['issues']:
            for attachment in issue['attachments']:
                filename = attachment['filename']
                search_filename = filename if case_sensitive else filename.lower()
                
                if search_pattern in search_filename:
                    matching_attachment = attachment.copy()
                    matching_attachment['issue_key'] = issue['issue_key']
                    matching_attachment['issue_summary'] = issue['issue_summary']
                    matching_attachments.append(matching_attachment)
        
        print(f"🔍 Found {len(matching_attachments)} attachments matching '{filename_pattern}'")
        return matching_attachments
    
    def get_largest_attachments(self, 
                               project_key: str,
                               limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the largest attachments in a project.
        
        Args:
            project_key: Project key to search in
            limit: Number of largest attachments to return
            
        Returns:
            List of largest attachments with issue information
        """
        attachment_data = self.list_project_attachments(project_key)
        all_attachments = []
        
        for issue in attachment_data['issues']:
            for attachment in issue['attachments']:
                attachment_with_issue = attachment.copy()
                attachment_with_issue['issue_key'] = issue['issue_key']
                attachment_with_issue['issue_summary'] = issue['issue_summary']
                all_attachments.append(attachment_with_issue)
        
        # Sort by size and return top N
        largest = sorted(all_attachments, key=lambda x: x['size_bytes'], reverse=True)[:limit]
        
        print(f"📊 Found {len(largest)} largest attachments")
        return largest