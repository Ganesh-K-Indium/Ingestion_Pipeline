#!/usr/bin/env python3
"""
Simple Natural Language Wrapper for Jira MCP Tools

This is the simplest way to interact with Jira using natural language.
Just run this script and start typing your requests!
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

try:
    from jira_mcp_tools import JiraAgent
except ImportError as e:
    print(f"❌ Error importing Jira MCP Tools: {e}")
    print("Make sure you're in the correct directory and dependencies are installed")
    sys.exit(1)


def main():
    """Simple natural language interface"""
    print("🤖 Jira Natural Language Interface")
    print("=" * 50)
    
    # Check if we have a request as command line argument
    if len(sys.argv) > 1:
        # Single request mode
        request = " ".join(sys.argv[1:])
        print(f"Processing: '{request}'")
        print("-" * 50)
        
        try:
            agent = JiraAgent()
            result = agent.process_request(request)
            
            if result.get('success'):
                print(f"✅ {result.get('summary', 'Operation completed')}")
                
                # Show key data if available
                data = result.get('data')
                action = result.get('action')
                
                if action == 'list_projects' and isinstance(data, list):
                    print(f"\n📋 Found {len(data)} projects:")
                    for project in data[:5]:
                        print(f"   • {project.get('key')} - {project.get('name', '')}")
                    if len(data) > 5:
                        print(f"   ... and {len(data) - 5} more")
                
                elif action == 'search_issues' and isinstance(data, list):
                    print(f"\n📄 Found {len(data)} issues:")
                    for issue in data[:5]:
                        key = issue.get('key')
                        summary = issue.get('fields', {}).get('summary', '')[:40]
                        print(f"   • {key}: {summary}...")
                    if len(data) > 5:
                        print(f"   ... and {len(data) - 5} more")
                
                elif action == 'download_attachments':
                    if 'downloaded' in data:
                        print(f"\n📥 Downloaded {data.get('downloaded', 0)} files")
                        print(f"   Location: {data.get('download_path', '')}")
                    else:
                        print(f"\n📦 Downloaded {data.get('total_files_downloaded', 0)} files")
                        print(f"   Location: {data.get('download_path', '')}")
                
                elif action == 'download_and_ingest':
                    download_result = data.get('download_result', {})
                    ingestion_result = data.get('ingestion_result') or data.get('ingestion_results')
                    
                    print(f"\n🔄 Download and Ingest Results:")
                    
                    # Show download results
                    if 'downloaded' in download_result:
                        # Single issue download
                        print(f"   📥 Downloaded: {download_result.get('downloaded', 0)} files from issue")
                        print(f"   📍 Location: {download_result.get('download_path', '')}")
                    else:
                        # Project-wide download
                        print(f"   📥 Downloaded: {download_result.get('total_files_downloaded', 0)} files from project")
                    
                    # Show ingestion results
                    if ingestion_result:
                        if isinstance(ingestion_result, list):
                            # Multiple issues processed
                            total_processed = sum(r['result'].get('processed', 0) for r in ingestion_result)
                            total_failed = sum(r['result'].get('failed', 0) for r in ingestion_result)
                            print(f"   � Processed: {total_processed} files")
                            if total_failed > 0:
                                print(f"   ❌ Failed: {total_failed} files")
                        else:
                            # Single issue processed
                            print(f"   🔄 Processed: {ingestion_result.get('processed', 0)} files")
                            if ingestion_result.get('failed', 0) > 0:
                                print(f"   ❌ Failed: {ingestion_result.get('failed', 0)} files")
                        print(f"   📊 Successfully ingested into vector database")
                        
                        # Show errors if any
                        errors = data.get('errors', [])
                        if errors:
                            print(f"   ⚠️  Errors: {len(errors)}")
                            for error in errors[:3]:  # Show first 3 errors
                                print(f"      • {error}")
                            if len(errors) > 3:
                                print(f"      ... and {len(errors) - 3} more errors")
                        
                        # Show processing details for issue-level results
                        if 'processed_files' in data:
                            processed_files = data['processed_files']
                            if processed_files:
                                print(f"   📄 File Details:")
                                for file_info in processed_files[:3]:
                                    filename = file_info.get('filename', 'Unknown')
                                    file_type = file_info.get('type', 'unknown')
                                    if file_type == 'pdf':
                                        images = file_info.get('images_extracted', 0)
                                        docs = file_info.get('documents_created', 0)
                                        print(f"      📎 {filename}: {images} images → {docs} documents")
                                    else:
                                        status = file_info.get('status', 'processed')
                                        print(f"      📎 {filename}: {status}")
                
                elif action == 'list_attachments':
                    if isinstance(data, dict):
                        total = data.get('total_attachments', 0)
                        print(f"\n📎 Found {total} attachments")
                        if total > 0:
                            by_type = data.get('attachments_by_type', {})
                            if by_type:
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
                                    size_mb = att.get('size_bytes', 0) / (1024 * 1024)
                                    print(f"      📎 {filename} ({size_mb:.1f} MB)")
                            
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
                
                # Show suggestions
                suggestions = agent.suggest_next_actions(result)
                if suggestions:
                    print(f"\n💡 Next, you could:")
                    for i, suggestion in enumerate(suggestions[:3], 1):
                        print(f"   {i}. {suggestion}")
                    print(f"\nTo continue, run: python {sys.argv[0]} \"your next request\"")
            else:
                print(f"❌ {result.get('error', 'Unknown error')}")
                print("\n💡 Try these examples:")
                print("   python jira.py \"list all projects\"")
                print("   python jira.py \"show me issues in project ABC\"")
                print("   python jira.py \"download PDFs from issue ABC-123\"")
        
        except ValueError as e:
            if "OpenAI API key" in str(e):
                print("❌ OpenAI API key required for natural language processing")
                print("Set OPENAI_API_KEY in your .env file")
            else:
                print(f"❌ Error: {e}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    else:
        # Interactive mode
        print("💬 Interactive Mode - Type your requests in natural language")
        print("Examples:")
        print("  • 'list all projects'")
        print("  • 'show me issues with attachments in project ABC'")
        print("  • 'download PDF files from issue ABC-123'")
        print("\nType 'exit', 'quit', or press Ctrl+C to end")
        print("-" * 50)
        
        try:
            agent = JiraAgent()
            
            while True:
                try:
                    request = input("\n🎯 Request: ").strip()
                    
                    if request.lower() in ['exit', 'quit', 'bye']:
                        print("👋 Goodbye!")
                        break
                    
                    if not request:
                        continue
                    
                    result = agent.process_request(request)
                    
                    if result.get('success'):
                        print(f"✅ {result.get('summary', 'Done')}")
                        
                        # Simple result display
                        data = result.get('data')
                        action = result.get('action')
                        
                        if action == 'list_projects' and data:
                            print(f"   Found {len(data)} projects")
                        elif action == 'search_issues' and data:
                            print(f"   Found {len(data)} issues")
                        elif action == 'download_attachments' and data:
                            downloaded = data.get('downloaded', data.get('total_files_downloaded', 0))
                            print(f"   Downloaded {downloaded} files")
                        elif action == 'download_and_ingest' and data:
                            # Extract results from the new structure
                            download_result = data.get('download_result', {})
                            ingestion_result = data.get('ingestion_result') or data.get('ingestion_results')
                            
                            downloaded = download_result.get('downloaded', download_result.get('total_files_downloaded', 0))
                            
                            if ingestion_result:
                                if isinstance(ingestion_result, list):
                                    processed = sum(r.get('result', {}).get('processed', 0) for r in ingestion_result if r and r.get('result'))
                                else:
                                    processed = ingestion_result.get('processed', 0) if ingestion_result else 0
                            else:
                                processed = 0
                            
                            print(f"   Downloaded {downloaded} files, processed {processed} files")
                        
                    else:
                        print(f"❌ {result.get('error', 'Failed')}")
                        print("💡 Try rephrasing your request")
                
                except KeyboardInterrupt:
                    print("\n👋 Goodbye!")
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
        
        except ValueError as e:
            if "OpenAI API key" in str(e):
                print("❌ OpenAI API key required for natural language processing")
                print("Set OPENAI_API_KEY in your .env file")
            else:
                print(f"❌ Setup error: {e}")
        except Exception as e:
            print(f"❌ Error initializing: {e}")


if __name__ == "__main__":
    main()