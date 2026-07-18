#!/usr/bin/env python3
"""Root launcher for the *arr cleaner.

Usage: python cleanup.py radarr [options]
       python cleanup.py sonarr [options]
       python cleanup.py --help
"""

from arr_cleanup.cli import app

if __name__ == "__main__":
    app()
