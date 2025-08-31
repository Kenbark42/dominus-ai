#!/usr/bin/env python3
"""
Document Ingestion Script for Dominus AI RAG System
Ingests various document types into the vector database
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path
from typing import List, Dict, Optional
import mimetypes

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_URL = "http://localhost:8090"

def read_file_content(file_path: Path) -> Optional[str]:
    """Read content from a file"""
    try:
        # Determine file type
        mime_type, _ = mimetypes.guess_type(file_path)
        
        # For now, handle text-based files
        text_extensions = ['.txt', '.md', '.py', '.js', '.ts', '.jsx', '.tsx', 
                          '.json', '.yaml', '.yml', '.toml', '.ini', '.conf',
                          '.sh', '.bash', '.zsh', '.fish', '.c', '.cpp', '.h',
                          '.java', '.go', '.rs', '.rb', '.php', '.html', '.css',
                          '.xml', '.sql', '.r', '.m', '.swift', '.kt', '.scala']
        
        if file_path.suffix.lower() in text_extensions:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        else:
            print(f"Skipping unsupported file type: {file_path.suffix}")
            return None
            
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def ingest_file(file_path: Path, collection: str = "default") -> bool:
    """Ingest a single file into the RAG system"""
    content = read_file_content(file_path)
    if not content:
        return False
    
    # Prepare metadata
    metadata = {
        "source": str(file_path),
        "filename": file_path.name,
        "extension": file_path.suffix,
        "size": file_path.stat().st_size,
        "type": "code" if file_path.suffix in ['.py', '.js', '.ts', '.go', '.rs'] else "document"
    }
    
    # Prepare request
    data = {
        "collection": collection,
        "content": content,
        "metadata": metadata
    }
    
    try:
        response = requests.post(
            f"{API_URL}/ingest",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Ingested {file_path.name} ({result['document_chunks']} chunks)")
            return True
        else:
            print(f"✗ Failed to ingest {file_path.name}: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Error ingesting {file_path.name}: {e}")
        return False

def ingest_directory(dir_path: Path, collection: str = "default", 
                    pattern: str = "*", recursive: bool = True) -> Dict:
    """Ingest all matching files from a directory"""
    stats = {"success": 0, "failed": 0, "skipped": 0}
    
    # Get all matching files
    if recursive:
        files = list(dir_path.rglob(pattern))
    else:
        files = list(dir_path.glob(pattern))
    
    print(f"Found {len(files)} files matching pattern '{pattern}'")
    
    for file_path in files:
        if file_path.is_file():
            if ingest_file(file_path, collection):
                stats["success"] += 1
            else:
                stats["failed"] += 1
        else:
            stats["skipped"] += 1
    
    return stats

def main():
    parser = argparse.ArgumentParser(description="Ingest documents into Dominus AI RAG system")
    parser.add_argument("path", help="File or directory path to ingest")
    parser.add_argument("-c", "--collection", default="default", 
                       help="Collection name (default: 'default')")
    parser.add_argument("-p", "--pattern", default="*",
                       help="File pattern for directory ingestion (default: '*')")
    parser.add_argument("-r", "--recursive", action="store_true",
                       help="Recursively search directories")
    parser.add_argument("--list-collections", action="store_true",
                       help="List existing collections and exit")
    
    args = parser.parse_args()
    
    # List collections if requested
    if args.list_collections:
        try:
            response = requests.get(f"{API_URL}/collections")
            if response.status_code == 200:
                data = response.json()
                print(f"Collections ({data['count']} total):")
                for col in data['collections']:
                    print(f"  - {col['name']} ({col['count']} documents)")
            else:
                print("Failed to get collections")
        except Exception as e:
            print(f"Error: {e}")
        return
    
    # Process path
    path = Path(args.path)
    
    if not path.exists():
        print(f"Error: Path does not exist: {path}")
        sys.exit(1)
    
    print(f"Ingesting into collection: {args.collection}")
    
    if path.is_file():
        # Single file
        success = ingest_file(path, args.collection)
        if success:
            print("\n✓ Ingestion complete")
        else:
            print("\n✗ Ingestion failed")
            sys.exit(1)
    else:
        # Directory
        stats = ingest_directory(path, args.collection, args.pattern, args.recursive)
        print(f"\nIngestion complete:")
        print(f"  ✓ Success: {stats['success']}")
        print(f"  ✗ Failed: {stats['failed']}")
        print(f"  - Skipped: {stats['skipped']}")
        
        if stats['failed'] > 0:
            sys.exit(1)

if __name__ == "__main__":
    main()