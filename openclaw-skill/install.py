#!/usr/bin/env python3
"""
One-liner installer for Octopoda Memory OpenClaw skill.

Usage:
    python install.py
    python install.py --key sk-octopoda-YOUR_KEY_HERE

What it does:
    1. Copies octopoda-memory/ to ~/.openclaw/skills/
    2. Optionally sets your API key in openclaw.json
    3. Runs setup validation
"""

import os
import sys
import shutil
import json
import argparse


def main():
    parser = argparse.ArgumentParser(description="Install Octopoda Memory for OpenClaw")
    parser.add_argument("--key", help="Your Octopoda API key (sk-octopoda-...)")
    args = parser.parse_args()

    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_src = os.path.join(script_dir, "octopoda-memory")
    openclaw_dir = os.path.join(os.path.expanduser("~"), ".openclaw")
    skills_dir = os.path.join(openclaw_dir, "skills")
    skill_dest = os.path.join(skills_dir, "octopoda-memory")
    config_path = os.path.join(openclaw_dir, "openclaw.json")

    # Check source exists
    if not os.path.isdir(skill_src):
        print(f"[FAIL] Skill source not found at: {skill_src}")
        print("  Make sure you're running this from the openclaw-skill/ directory")
        sys.exit(1)

    # Check OpenClaw is installed
    if not os.path.isdir(openclaw_dir):
        print(f"[FAIL] OpenClaw not found at: {openclaw_dir}")
        print("  Install OpenClaw first: npm install -g openclaw@latest")
        sys.exit(1)

    # Create skills directory if needed
    os.makedirs(skills_dir, exist_ok=True)

    # Copy skill
    if os.path.exists(skill_dest):
        shutil.rmtree(skill_dest)
        print(f"[OK]   Removed old skill at {skill_dest}")
    shutil.copytree(skill_src, skill_dest)
    print(f"[OK]   Skill installed to {skill_dest}", flush=True)

    # Set API key if provided
    if args.key:
        config = {}
        if os.path.isfile(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except Exception:
                pass

        # Ensure nested structure exists
        if "skills" not in config:
            config["skills"] = {}
        if "entries" not in config["skills"]:
            config["skills"]["entries"] = {}
        if "octopoda-memory" not in config["skills"]["entries"]:
            config["skills"]["entries"]["octopoda-memory"] = {}

        config["skills"]["entries"]["octopoda-memory"]["enabled"] = True
        if "env" not in config["skills"]["entries"]["octopoda-memory"]:
            config["skills"]["entries"]["octopoda-memory"]["env"] = {}
        config["skills"]["entries"]["octopoda-memory"]["env"]["OCTOPODA_API_KEY"] = args.key

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"[OK]   API key saved to {config_path}", flush=True)

    elif not os.environ.get("OCTOPODA_API_KEY"):
        print("[INFO] No API key provided.", flush=True)
        print("  Get your free key at https://octopodas.com")
        print("  Then run: python install.py --key sk-octopoda-YOUR_KEY")
        print("  Or set OCTOPODA_API_KEY in your environment")

    # Run setup validation
    print(flush=True)
    memory_script = os.path.join(skill_dest, "scripts", "memory.py")
    os.system(f'{sys.executable} "{memory_script}" setup')

    print()
    print("Done! Restart OpenClaw to pick up the new skill:")
    print("  openclaw gateway stop")
    print("  openclaw gateway run")


if __name__ == "__main__":
    main()
