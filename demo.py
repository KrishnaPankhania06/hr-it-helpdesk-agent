"""One-command demo: python demo.py

Starts the HR database (embedded Postgres if DATABASE_URL is unset), seeds
demo data, builds the policy vector index, and drops you into a chat with
the helpdesk agent.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from agent import main

if __name__ == "__main__":
    main()
