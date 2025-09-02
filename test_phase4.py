#!/usr/bin/env python3

"""
Quick test script for Phase 4 integration.
Tests the agent in isolation and then validates UI can start.
"""

import subprocess
import json
import time
from pathlib import Path

def test_agent_standalone():
    """Test the agent directly via CLI."""
    print("Testing agent standalone...")
    
    # Test SUMMARIZE
    event = {
        "ts": "2025-09-02T12:00:00.000Z",
        "decoder": {"type": "SSVEP", "version": "0.1.0"},
        "intent": {"name": "SELECT", "args": {"label": "SUMMARIZE", "index": 0}},
        "confidence": 0.85,
        "context": {"file": "workspace/in/sample_report.md"}
    }
    
    result = subprocess.run(
        ["uv", "run", "neurorelay-agent"],
        input=json.dumps(event) + "\n",
        text=True,
        capture_output=True,
        cwd=Path(__file__).parent
    )
    
    if result.returncode == 0:
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if line.strip():
                try:
                    obj = json.loads(line)
                    if obj.get("type") == "agent_result":
                        if obj.get("status") == "ok":
                            print(f"✅ Agent test passed: {obj.get('tool')} → {obj.get('out')}")
                            return True
                        else:
                            print(f"❌ Agent returned error: {obj.get('error')}")
                            return False
                except json.JSONDecodeError:
                    continue
    else:
        print(f"❌ Agent process failed: {result.stderr}")
        return False
    
    print("❌ No valid agent result found")
    return False

def test_ui_startup():
    """Test that UI can start (will exit quickly since no display)."""
    print("Testing UI startup...")
    
    try:
        # Start UI and kill it after 2 seconds
        proc = subprocess.Popen(
            ["uv", "run", "neurorelay-ui", "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=Path(__file__).parent
        )
        
        stdout, stderr = proc.communicate(timeout=5)
        
        if "NeuroRelay SSVEP 2×2 UI" in stdout:
            print("✅ UI startup test passed")
            return True
        else:
            print(f"❌ UI startup failed: {stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        proc.kill()
        print("❌ UI startup timed out")
        return False
    except Exception as e:
        print(f"❌ UI startup exception: {e}")
        return False

def main():
    print("=== Phase 4 Integration Test ===\n")
    
    # Check workspace setup
    workspace_in = Path("workspace/in")
    if not workspace_in.exists() or not any(workspace_in.iterdir()):
        print("❌ No files in workspace/in/ - please add a sample document")
        return 1
    
    print(f"📁 Found sample files: {[f.name for f in workspace_in.glob('*') if f.is_file()]}")
    
    # Test agent
    agent_ok = test_agent_standalone()
    if not agent_ok:
        return 1
    
    # Test UI startup
    ui_ok = test_ui_startup()
    if not ui_ok:
        return 1
    
    print("\n🎉 Phase 4 integration test passed!")
    print("\nTo run the full demo:")
    print("  uv run neurorelay-ui --auto-freqs")
    print("\nAgent tools will activate when you dwell-select tiles.")
    print("Check workspace/out/ for results and logs/agent.jsonl for events.")
    
    return 0

if __name__ == "__main__":
    exit(main())