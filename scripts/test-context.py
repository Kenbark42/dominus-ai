#!/usr/bin/env python3
"""
Test script for context-aware chat system
Demonstrates conversation memory across multiple requests
"""

import requests
import json
import time
import sys


def test_context_system(base_url="http://localhost:8091"):
    """Test the context-aware chat system"""
    
    print("=" * 60)
    print("DOMINUS AI - Context System Test")
    print("=" * 60)
    
    # 1. Create a new session
    print("\n1. Creating new session...")
    response = requests.post(f"{base_url}/session/create", json={
        "metadata": {
            "user": "test_user",
            "purpose": "context_demo"
        }
    })
    
    if response.status_code != 200:
        print(f"Failed to create session: {response.text}")
        return
    
    session_data = response.json()
    session_id = session_data['session_id']
    print(f"   Session created: {session_id}")
    
    # 2. First message - introduce a topic
    print("\n2. First message - introducing myself...")
    response = requests.post(f"{base_url}/chat", json={
        "session_id": session_id,
        "message": "My name is Alice and I'm interested in learning about quantum computing.",
        "parameters": {
            "max_new_tokens": 200,
            "temperature": 0.7
        }
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"   AI: {data['response']}")
        print(f"   Tokens used: {data['usage']['total_tokens']}")
    else:
        print(f"   Error: {response.text}")
        return
    
    time.sleep(2)  # Brief pause
    
    # 3. Second message - reference previous context
    print("\n3. Second message - testing context memory...")
    response = requests.post(f"{base_url}/chat", json={
        "session_id": session_id,
        "message": "What was my name again? And what topic did I mention?",
        "parameters": {
            "max_new_tokens": 150,
            "temperature": 0.5
        }
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"   AI: {data['response']}")
        
        # Check if AI remembered the context
        response_lower = data['response'].lower()
        if 'alice' in response_lower:
            print("   ✓ AI remembered the name!")
        else:
            print("   ✗ AI did not remember the name")
            
        if 'quantum' in response_lower:
            print("   ✓ AI remembered the topic!")
        else:
            print("   ✗ AI did not remember the topic")
    else:
        print(f"   Error: {response.text}")
        return
    
    time.sleep(2)
    
    # 4. Third message - continue conversation
    print("\n4. Third message - continuing the conversation...")
    response = requests.post(f"{base_url}/chat", json={
        "session_id": session_id,
        "message": "Can you give me a simple example of superposition?",
        "parameters": {
            "max_new_tokens": 300,
            "temperature": 0.7
        }
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"   AI: {data['response']}")
    else:
        print(f"   Error: {response.text}")
        return
    
    # 5. Get session info
    print("\n5. Getting session information...")
    response = requests.post(f"{base_url}/session/info", json={
        "session_id": session_id
    })
    
    if response.status_code == 200:
        info = response.json()
        print(f"   Messages in conversation: {info['message_count']}")
        print(f"   Total tokens used: {info['total_tokens']}")
        print(f"   Session created: {info['created_at']}")
        print(f"   Last updated: {info['updated_at']}")
    else:
        print(f"   Error: {response.text}")
    
    # 6. Test without session (stateless)
    print("\n6. Testing stateless request (no context)...")
    response = requests.post(f"{base_url}/chat", json={
        "message": "What was the name I told you?",
        "parameters": {
            "max_new_tokens": 100
        }
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"   AI: {data['response']}")
        print("   (This is a new session, so AI shouldn't remember Alice)")
    
    print("\n" + "=" * 60)
    print("Context System Test Complete!")
    print("=" * 60)
    
    return session_id


def test_context_persistence(session_id, base_url="http://localhost:8091"):
    """Test that context persists across time"""
    
    print("\n" + "=" * 60)
    print("Testing Context Persistence")
    print("=" * 60)
    
    print(f"\nResuming session: {session_id}")
    
    response = requests.post(f"{base_url}/chat", json={
        "session_id": session_id,
        "message": "Do you remember what we were discussing? Remind me of my name and interest.",
        "parameters": {
            "max_new_tokens": 200
        }
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"AI: {data['response']}")
        
        response_lower = data['response'].lower()
        if 'alice' in response_lower and 'quantum' in response_lower:
            print("\n✓ SUCCESS: Context persisted! AI remembers the conversation.")
        else:
            print("\n✗ Context was not fully preserved")
    else:
        print(f"Error: {response.text}")


if __name__ == "__main__":
    # Check if context bridge is running
    try:
        response = requests.get("http://localhost:8091/health", timeout=2)
        if response.status_code != 200:
            print("Context bridge is not responding correctly")
            print("Please start it with: python3 ~/ai/dominus-ai/services/context_bridge.py")
            sys.exit(1)
    except requests.exceptions.RequestException:
        print("Context bridge is not running!")
        print("Please start it with: python3 ~/ai/dominus-ai/services/context_bridge.py")
        sys.exit(1)
    
    # Run tests
    session_id = test_context_system()
    
    if session_id:
        print("\nWaiting 5 seconds before testing persistence...")
        time.sleep(5)
        test_context_persistence(session_id)
    
    print("\nTest complete!")