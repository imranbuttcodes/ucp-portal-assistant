import os
import sys
import json
from typing import Annotated, Sequence, TypedDict
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, AIMessageChunk, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from ucp_tools import tools
from prompts import SYSTEM_PROMPT_TEST, SUMMARY_PROMPT_TEMPLATE
from models import llm, llm_with_tools

load_dotenv()

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "ucp_assistant_demo")
BOT_TITLE = os.getenv("BOT_TITLE", "UCP Assistant Reply")
BOT_TAG = os.getenv("BOT_TAG", "ucp_bot_response")

# LANGGRAPH STATE DEFINITION
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

def agent_node(state: AgentState):
    """Agent node that invokes LLM with bound tools."""
    messages = state["messages"]
    full_messages = [SystemMessage(content=SYSTEM_PROMPT_TEST)] + list(messages)
    response = llm_with_tools.invoke(full_messages)
    return {"messages": [response]}

# LANGGRAPH STATEGRAPH WORKFLOW
workflow = StateGraph(AgentState)

# Add Agent Node and Prebuilt ToolNode
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(tools))

# Set entry point
workflow.set_entry_point("agent")

# Add conditional edge using prebuilt langgraph.prebuilt.tools_condition
workflow.add_conditional_edges(
    "agent",
    tools_condition,
)

# Add edge from tools back to agent
workflow.add_edge("tools", "agent")

# Compile LangGraph application
app = workflow.compile()

def chat_loop():    
    print("UNI-ASSISTANT SANDBOX READY (LANGGRAPH STATEGRAPH EDITION)")
    print("I now have access to 100% of the scraper's raw JSON data.")
    print("Type 'exit' or 'quit' to stop.\n")
    
    chat_history = []
    
    THRESHOLD = 10
    RECENT_BUFFER = 6
    
    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ['quit', 'exit']:
                print("Goodbye!")
                break
                
            chat_history.append(HumanMessage(content=user_input))
            
            # In-Memory Cumulative Summary Threshold Check
            if len(chat_history) > THRESHOLD:
                print("[Memory Engine] Compressing older messages into cumulative summary...")
                recent_msgs = chat_history[-RECENT_BUFFER:]
                old_msgs = chat_history[:-RECENT_BUFFER]
                
                formatted_old = []
                for m in old_msgs:
                    role = "User" if isinstance(m, HumanMessage) else "Assistant"
                    content = m.content[:500] if isinstance(m.content, str) else str(m.content)[:500]
                    formatted_old.append(f"{role}: {content}")
                
                old_text = "\n".join(formatted_old)
                summary_prompt = SUMMARY_PROMPT_TEMPLATE.format(
                    summary="None",
                    old_text=old_text
                )
                
                try:
                    res = llm.invoke([HumanMessage(content=summary_prompt)])
                    summary_text = res.content.strip()
                    chat_history = [
                        SystemMessage(content=f"# RECAP OF PRIOR CONVERSATION & USER FACTS:\n{summary_text}")
                    ] + recent_msgs
                except Exception as e:
                    print(f"[Memory Engine Warning] Summary failed: {e}")
            
            print("\n[Thinking...]")
            print("Assistant: ", end="", flush=True)
            
            full_response = ""
            for chunk, metadata in app.stream({"messages": chat_history}, stream_mode="messages"):
                if isinstance(chunk, AIMessageChunk):
                    if chunk.content:
                        if isinstance(chunk.content, str):
                            print(chunk.content, end="", flush=True)
                            full_response += chunk.content
                        elif isinstance(chunk.content, list):
                            for block in chunk.content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text = block.get("text", "")
                                    print(text, end="", flush=True)
                                    full_response += text
                elif isinstance(chunk, ToolMessage):
                    print(f"\n\n[Tool Executed: {chunk.name}]", flush=True)
                    print("Assistant: ", end="", flush=True)
            
            print()
            chat_history.append(AIMessage(content=full_response))
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    chat_loop()
