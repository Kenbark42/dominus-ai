#!/usr/bin/env python3
"""
Ingest Darkfoo Project Files into RAG System
Focuses on core functionality and important files
"""

import os
import sys
import json
import requests
from pathlib import Path
from typing import List, Dict

API_URL = "http://localhost:8090"

def ingest_file(file_path: Path, collection: str) -> bool:
    """Ingest a single file into the RAG system"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        # Skip empty or very small files
        if len(content) < 50:
            return False
            
        metadata = {
            "source": str(file_path),
            "filename": file_path.name,
            "extension": file_path.suffix,
            "project": "darkfoo",
            "type": "frontend" if file_path.suffix in ['.js', '.css', '.html'] else "backend"
        }
        
        response = requests.post(
            f"{API_URL}/ingest",
            json={
                "collection": collection,
                "content": content,
                "metadata": metadata
            },
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ {file_path.name} ({result['document_chunks']} chunks)")
            return True
        else:
            print(f"✗ {file_path.name}: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ {file_path.name}: {e}")
        return False

def main():
    print("Ingesting Darkfoo Project Files into RAG System")
    print("=" * 50)
    
    # Define file patterns for different components
    ingestion_plan = [
        {
            "name": "Core Darkfoo Frontend",
            "collection": "darkfoo_core",
            "files": [
                "/home/ken/darkfoo/Darkfoo/index.html",
                "/home/ken/darkfoo/Darkfoo/js/main.js",
                "/home/ken/darkfoo/Darkfoo/js/terminal.js",
                "/home/ken/darkfoo/Darkfoo/js/commands-simplified.js",
                "/home/ken/darkfoo/Darkfoo/js/ui.js",
                "/home/ken/darkfoo/Darkfoo/js/three-scene.js",
                "/home/ken/darkfoo/Darkfoo/js/darkfoo-enhanced.js",
            ]
        },
        {
            "name": "Terminal System",
            "collection": "darkfoo_terminal",
            "patterns": [
                "/home/ken/darkfoo/Darkfoo/js/terminal/*.js",
            ]
        },
        {
            "name": "AI Integration",
            "collection": "darkfoo_ai",
            "patterns": [
                "/home/ken/darkfoo/Darkfoo/js/ai/*.js",
                "/home/ken/darkfoo/Darkfoo/js/ai-*.js",
            ]
        },
        {
            "name": "CSS Styles",
            "collection": "darkfoo_styles",
            "patterns": [
                "/home/ken/darkfoo/Darkfoo/css/main.css",
                "/home/ken/darkfoo/Darkfoo/css/terminal.css",
                "/home/ken/darkfoo/Darkfoo/css/darkfoo-core.css",
                "/home/ken/darkfoo/Darkfoo/css/darkfoo-theme.css",
                "/home/ken/darkfoo/Darkfoo/css/ai-enhanced.css",
                "/home/ken/darkfoo/Darkfoo/css/terminal-window.css",
            ]
        },
        {
            "name": "Backend Scripts",
            "collection": "darkfoo_backend",
            "files": [
                "/home/ken/darkfoo/scripts/deployment/deploy.sh",
                "/home/ken/darkfoo/CLAUDE.md",
                "/home/ken/darkfoo/Darkfoo/CLAUDE.md",
            ],
            "patterns": [
                "/home/ken/darkfoo/*.py",
                "/home/ken/darkfoo/scripts/*.sh",
            ]
        },
        {
            "name": "Audio System",
            "collection": "darkfoo_audio",
            "patterns": [
                "/home/ken/darkfoo/Darkfoo/js/audio*.js",
                "/home/ken/darkfoo/Darkfoo/js/ambient-audio.js",
            ]
        }
    ]
    
    total_success = 0
    total_failed = 0
    
    for component in ingestion_plan:
        print(f"\n📁 {component['name']}")
        print("-" * 40)
        
        files_to_ingest = []
        
        # Collect specific files
        if 'files' in component:
            for file_path in component['files']:
                path = Path(file_path)
                if path.exists():
                    files_to_ingest.append(path)
                    
        # Collect pattern matches
        if 'patterns' in component:
            for pattern in component['patterns']:
                # Handle glob patterns
                if '*' in pattern:
                    base_path = Path(pattern.split('*')[0].rsplit('/', 1)[0])
                    glob_pattern = pattern.split('/')[-1]
                    if base_path.exists():
                        matches = list(base_path.glob(glob_pattern))
                        files_to_ingest.extend(matches)
                else:
                    path = Path(pattern)
                    if path.exists():
                        files_to_ingest.append(path)
        
        # Ingest files
        for file_path in files_to_ingest:
            if ingest_file(file_path, component['collection']):
                total_success += 1
            else:
                total_failed += 1
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 Ingestion Complete")
    print(f"✓ Success: {total_success} files")
    print(f"✗ Failed: {total_failed} files")
    
    # Get collection stats
    try:
        response = requests.get(f"{API_URL}/collections")
        if response.status_code == 200:
            data = response.json()
            print(f"\n📚 Total Collections: {data['count']}")
            
            darkfoo_collections = [c for c in data['collections'] if 'darkfoo' in c['name']]
            if darkfoo_collections:
                print("\nDarkfoo Collections:")
                for col in darkfoo_collections:
                    print(f"  • {col['name']}: {col['count']} chunks")
    except Exception as e:
        print(f"Could not get collection stats: {e}")

if __name__ == "__main__":
    main()