import os
import sys
import json
import time
import urllib.request
import urllib.error
from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

load_dotenv()

# Topic name on ntfy.sh
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "ucp_assistant_demo")
BOT_TITLE = os.getenv("BOT_TITLE", "Assistant Reply")
BOT_TAG = os.getenv("BOT_TAG", "assistant_bot_response")

# Local cache of bot-sent messages to guarantee no self-echo loops
sent_messages_cache = set()

def send_ntfy_push(message: str, title: str = BOT_TITLE, priority: str = "default", tags: str = BOT_TAG):
    """Sends a push notification reply back to the ntfy topic using JSON POST."""
    url = "https://ntfy.sh"
    
    # Store in local cache to ignore self-echoes
    sent_messages_cache.add(message.strip())
    
    payload = {
        "topic": NTFY_TOPIC,
        "message": message,
        "title": title,
        "priority": 3 if priority == "default" else 4,
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

tools = []

llm = ChatOllama(
    model="llama3.2:3b",
    temperature=0.2
)

system_prompt = """You are 'NtfyBot', a smart assistant that communicates with the user via mobile push notifications.
Keep your responses helpful, clear, and reasonably concise so they are easy to read on a phone screen notification."""

agent = create_react_agent(llm, tools=tools, prompt=system_prompt)

def listen_and_respond():
    print("=" * 65)
    print("TWO-WAY NTFY MOBILE CHATBOT LISTENER READY")
    print("=" * 65)
    print(f"Topic Web UI:  https://ntfy.sh/{NTFY_TOPIC}")
    print(f"Listening on:  https://ntfy.sh/{NTFY_TOPIC}/json")
    print("\nHow to use:")
    print(f"1. Open https://ntfy.sh/{NTFY_TOPIC} in your browser or ntfy phone app.")
    print("2. Send any message from your phone or browser.")
    print("3. The bot will receive it here, generate an AI reply, and push it back to your phone!")
    print("\nPress Ctrl+C to exit.\n")
    
    chat_history = [SystemMessage(content=system_prompt)]
    stream_url = f"https://ntfy.sh/{NTFY_TOPIC}/json"
    
    while True:
        try:
            req = urllib.request.Request(stream_url)
            with urllib.request.urlopen(req, timeout=60) as response:
                print(f"[Connected] Active & listening for incoming messages on ntfy.sh/{NTFY_TOPIC} ...\n")
                for line in response:
                    if not line:
                        continue
                    try:
                        line_str = line.decode("utf-8").strip()
                        if not line_str:
                            continue
                            
                        data = json.loads(line_str)
                        
                        # Process only 'message' events
                        if data.get("event") == "message":
                            incoming_text = data.get("message", "").strip()
                            msg_title = data.get("title", "")
                            tags = data.get("tags", [])
                            
                            # IGNORE messages posted by the bot itself!
                            if msg_title == BOT_TITLE or BOT_TAG in tags or incoming_text in sent_messages_cache:
                                continue
                                
                            print(f"[Incoming Phone Message]: '{incoming_text}'")
                            chat_history.append(HumanMessage(content=incoming_text))
                            
                            print("[Thinking...]")
                            result = agent.invoke({"messages": chat_history})
                            answer = result["messages"][-1].content
                            chat_history.append(AIMessage(content=answer))
                            
                            print(f"[Bot Output]: {answer}")
                            print(f"[Pushing response back to phone via ntfy.sh/{NTFY_TOPIC}]...")
                            send_ntfy_push(answer, title=BOT_TITLE)
                            print("[Reply Delivered - Waiting for next message...]\n")
                            
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        print(f"[Error processing message]: {e}")
                        
        except (urllib.error.URLError, TimeoutError, Exception) as e:
            print(f"[Stream disconnected, reconnecting in 3 seconds...]: {e}")
            time.sleep(3)

if __name__ == "__main__":
    listen_and_respond()
