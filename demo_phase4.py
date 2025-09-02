#!/usr/bin/env python3

"""
Phase 4 Demo Script - shows the complete SSVEP to agent flow
Run this to see the agent working with sample brain selections
"""

import json
import time
import subprocess
from pathlib import Path

def simulate_brain_selection(label: str, confidence: float, context: dict = None):
    """Simulate a brain selection by sending JSON to the agent."""
    print(f"\n🧠 Simulating brain selection: {label} (confidence: {confidence:.2f})")
    
    event = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "decoder": {"type": "SSVEP", "version": "0.1.0"},
        "intent": {"name": "SELECT", "args": {"label": label, "index": ["SUMMARIZE", "TODOS", "DEADLINES", "EMAIL"].index(label)}},
        "confidence": confidence,
        "context": context or {}
    }
    
    print(f"📡 BrainBus event: {json.dumps(event, indent=2)}")
    
    # Send to agent
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
                        print(f"🤖 Agent result: {obj}")
                        if obj.get("status") == "ok":
                            out_path = Path(obj.get("out", ""))
                            if out_path.exists():
                                print(f"📝 Output preview: {out_path}")
                                content = out_path.read_text()[:300]
                                print(f"   {content}{'...' if len(content) >= 300 else ''}")
                        return obj.get("status") == "ok"
                except json.JSONDecodeError:
                    continue
    else:
        print(f"❌ Agent failed: {result.stderr}")
        return False
    
    return False

def main():
    print("🚀 Phase 4 Demo: Brain-to-Agent Pipeline")
    print("=" * 50)
    
    # Check prerequisites
    workspace_in = Path("workspace/in")
    if not workspace_in.exists() or not any(workspace_in.iterdir()):
        print("❌ Please add a sample document to workspace/in/")
        return 1
    
    sample_file = next(workspace_in.glob("*.md"))
    print(f"📄 Using sample file: {sample_file.name}")
    
    # Demo sequence - simulate different brain selections
    demos = [
        ("SUMMARIZE", 0.85, {"file": str(sample_file)}),
        ("TODOS", 0.78, {"file": str(sample_file)}),
        ("DEADLINES", 0.82, {"file": str(sample_file)}),
        ("EMAIL", 0.88, {"topic": "Project status update"}),
    ]
    
    successful = 0
    for label, conf, context in demos:
        if simulate_brain_selection(label, conf, context):
            successful += 1
        time.sleep(0.5)  # Brief pause between selections
    
    print(f"\n✅ Demo complete: {successful}/{len(demos)} selections successful")
    print(f"\n📁 Check outputs in: workspace/out/")
    print(f"📊 Check logs in: logs/agent.jsonl")
    
    # Show what was created
    out_dir = Path("workspace/out")
    if out_dir.exists():
        recent_files = sorted(out_dir.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]
        print(f"\n📋 Recent outputs:")
        for f in recent_files:
            print(f"   • {f.name}")
    
    print(f"\n🎯 To run the full UI demo:")
    print(f"   uv run neurorelay-ui --auto-freqs")
    print(f"\n   Look at tiles, dwell for 1.2s, and watch the Agent Dock!")
    
    return 0

if __name__ == "__main__":
    exit(main())