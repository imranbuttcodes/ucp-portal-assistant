import os
import sys
import json
import time
import urllib.request
import urllib.error
import requests
from datetime import datetime
from dotenv import load_dotenv
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, RemoveMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from ucp_tools import tools
from prompts import SYSTEM_PROMPT_NTFY, SUMMARY_PROMPT_TEMPLATE
from models import llm, llm_with_tools

load_dotenv()

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "ucp_assistant_demo").strip()
BOT_TITLE = os.getenv("BOT_TITLE", "UCP Assistant Reply").strip().strip('"').strip("'")
BOT_TAG = os.getenv("BOT_TAG", "ucp_bot_response").strip().strip('"').strip("'")

# Local cache of sent messages to prevent echo loops
sent_messages_cache = set()

def send_ntfy_push(message: str, title: str = BOT_TITLE, priority: str = "default", tags: str = BOT_TAG):
    """Sends a push notification reply back to the ntfy topic using JSON POST."""
    url = "https://ntfy.sh"
    sent_messages_cache.add(message.strip())
    
    payload = {
        "topic": NTFY_TOPIC,
        "message": message,
        "title": title,
        "tags": [tags]
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception as e:
        print(f"[ntfy Push Error] Failed to send push: {e}")

# LANGGRAPH STATE DEFINITION WITH SUMMARY FIELD
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    summary: str

# LANGGRAPH NODES AND EDGES

def summarize_node(state: AgentState):
    """Memory Summarization Node: Summarizes older messages and prunes them from graph state when threshold is reached."""
    messages = state["messages"]
    summary = state.get("summary", "")
    
    # Message threshold check (e.g. > 6 messages)
    if len(messages) > 6:
        print(f"[Memory Node] Total messages ({len(messages)}) exceeds threshold. Summarizing & pruning...")
        
        # Keep last 4 messages, summarize older ones
        old_msgs = messages[:-4]
        
        formatted_old = []
        for m in old_msgs:
            if isinstance(m, SystemMessage):
                continue
            role = "User" if isinstance(m, HumanMessage) else ("Assistant" if isinstance(m, AIMessage) else "Tool")
            content = m.content if isinstance(m.content, str) else str(m.content)
            formatted_old.append(f"{role}: {content[:300]}")
            
        old_text = "\n".join(formatted_old)
        summary_prompt = SUMMARY_PROMPT_TEMPLATE.format(
            summary=summary if summary else "None",
            old_text=old_text
        )

        try:
            res = llm.invoke([HumanMessage(content=summary_prompt)])
            new_summary = res.content.strip()
            
            # Generate RemoveMessage directives for old messages to prune them from state checkpointer
            delete_msgs = [RemoveMessage(id=m.id) for m in old_msgs if hasattr(m, "id") and m.id]
            print(f"[Memory Node] Summary updated. Pruned {len(delete_msgs)} old messages from state.")
            return {"summary": new_summary, "messages": delete_msgs}
        except Exception as e:
            print(f"[Memory Node Warning] Summarization failed: {e}")
            
    return {}

def agent_node(state: AgentState):
    """Agent Node: Invokes LLM with bound tools and appends conversation summary to system prompt if present."""
    messages = state["messages"]
    summary = state.get("summary", "")
    print("[Agent Node] Invoking LLM with tools...")
    
    system_message_content = SYSTEM_PROMPT_NTFY
    if summary:
        system_message_content += f"\n\n# RECAP OF PRIOR CONVERSATION & USER FACTS:\n{summary}"
        
    full_messages = [SystemMessage(content=system_message_content)] + list(messages)
    response = llm_with_tools.invoke(full_messages)
    return {"messages": [response]}

# CHECKPOINTER MEMORY
checkpointer = MemorySaver()

# LANGGRAPH STATEGRAPH WORKFLOW
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("summarize", summarize_node)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(tools))

# Set entry point to summarize node
workflow.set_entry_point("summarize")
workflow.add_edge("summarize", "agent")

# Add conditional edge using prebuilt tools_condition
workflow.add_conditional_edges(
    "agent",
    tools_condition,
)

# Edge from tools back to agent
workflow.add_edge("tools", "agent")

# Compile LangGraph application with Checkpointer Memory
app = workflow.compile(checkpointer=checkpointer)

def listen_and_respond():
    print("UCP PORTAL ASSISTANT - LANGGRAPH STATEGRAPH (CHECKPOINTER + SUMMARY MEMORY)", flush=True)
    print(f"Topic Web UI:  https://ntfy.sh/{NTFY_TOPIC}", flush=True)
    print(f"Listening on:  https://ntfy.sh/{NTFY_TOPIC}/json", flush=True)
    print("Architecture: Summarize Node -> Agent Node -> tools_condition -> ToolNode -> Checkpointer", flush=True)
    print("\nPress Ctrl+C to exit.\n", flush=True)
    
    # Thread config for Checkpointer MemorySaver
    config = {"configurable": {"thread_id": NTFY_TOPIC}}
    
    from websockets.sync.client import connect
    
    ws_url = f"wss://ntfy.sh/{NTFY_TOPIC}/ws"
    
    # Thread config for Checkpointer MemorySaver
    config = {"configurable": {"thread_id": NTFY_TOPIC}}
    
    while True:
        try:
            with connect(ws_url) as websocket:
                print(f"[Connected] Active & listening for incoming commands on wss://ntfy.sh/{NTFY_TOPIC} ...\n", flush=True)
                for line_str in websocket:
                    if not line_str:
                        continue
                    try:
                        data = json.loads(line_str)
                        
                        if data.get("event") == "message":
                            incoming_text = data.get("message", "").strip()
                            msg_title = data.get("title", "")
                            tags = data.get("tags", [])
                            
                            # IGNORE messages posted by the bot itself
                            if msg_title == BOT_TITLE or BOT_TAG in tags or incoming_text in sent_messages_cache:
                                continue
                                
                            print(f"[Incoming Mobile Query]: '{incoming_text}'", flush=True)
                            
                            # Invoke LangGraph app with thread_id checkpointer configuration
                            result_state = app.invoke(
                                {"messages": [HumanMessage(content=incoming_text)]},
                                config=config
                            )
                            
                            final_ai_msg = result_state["messages"][-1]
                            answer = final_ai_msg.content
                            
                            print(f"[Bot Output]:\n{answer}", flush=True)
                            print(f"[Pushing response to phone via ntfy.sh/{NTFY_TOPIC}]...", flush=True)
                            send_ntfy_push(answer, title=BOT_TITLE)
                            print("[Push Notification Delivered - Ready for next query!]\n")
                            
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        print(f"[Error processing command]: {e}", flush=True)
                        
        except Exception as e:
            print(f"[Stream disconnected, reconnecting in 3 seconds...]: {e}", flush=True)
            time.sleep(3)

if __name__ == "__main__":
    listen_and_respond()