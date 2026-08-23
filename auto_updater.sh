#!/bin/bash

# Change to the directory where this script is located
cd "$(dirname "$0")"

# Fetch latest from remote
git fetch

# Compare local branch with remote tracking branch
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse @{u})

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "New changes detected from GitHub! Updating..."
    
    # Pull new code
    git pull
    
    # Activate virtual environment and install new requirements
    source .venv/bin/activate
    pip install -r requirements.txt
    
    # Restart the bot in tmux
    # First, kill the existing session if it exists
    tmux kill-session -t ucpbot 2>/dev/null
    
    # Start a new detached session by calling the virtual environment Python directly
    tmux new -d -s ucpbot '.venv/bin/python uni_agent_ntfy.py'
    
    echo "Bot successfully updated and restarted."
fi
