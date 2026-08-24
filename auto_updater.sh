#!/bin/bash

{
# Change to the directory where this script is located
cd "$(dirname "$0")"

# Fetch latest from remote
git fetch

# Compare local branch with remote tracking branch
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse @{u})

# Check if code changed OR if the bot crashed/server rebooted (tmux session missing)
if [ "$LOCAL" != "$REMOTE" ] || ! tmux has-session -t ucpbot 2>/dev/null; then
    echo "Update or Crash detected! Deploying..."
    
    # Pull new code
    git pull
    
    # Activate virtual environment and install new requirements
    source .venv/bin/activate
    pip install -r requirements.txt
    
    # Restart the bot in tmux
    # First, kill the existing session if it exists
    tmux kill-session -t ucpbot 2>/dev/null
    
    # Start a new detached session and use 'tee' to print logs to the screen AND save them to bot_crash.log
    tmux new -d -s ucpbot 'bash -c "cd /home/imranbuttcodes/ucp-portal-assistant && source .venv/bin/activate && python uni_agent_ntfy.py 2>&1 | tee -a bot_crash.log"';
    
    echo "Bot successfully updated and restarted."
fi
}
