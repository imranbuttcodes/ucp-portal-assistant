#!/bin/bash

{
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
    
    # Start a new detached session with full logging to catch any errors
    tmux new -d -s ucpbot 'bash -c "cd /home/imranbuttcodes/ucp-portal-assistant && source .venv/bin/activate && python uni_agent_ntfy.py >> bot_crash.log 2>&1"'
    
    echo "Bot successfully updated and restarted."
fi
}
