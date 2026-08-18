# UCP Portal Assistant

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/) [![Framework](https://img.shields.io/badge/Framework-LangGraph%20%7C%20LangChain-orange.svg)](https://langchain-ai.github.io/langgraph/) [![LLM Provider](https://img.shields.io/badge/LLM-Groq%20%7C%20DeepSeek%20%7C%20Ollama-green.svg)](https://groq.com/) [![Push System](https://img.shields.io/badge/Push%20Notifications-ntfy.sh%202--Way-purple.svg)](https://ntfy.sh) [![Database](https://img.shields.io/badge/Database-SQLite%20%2B%20Playwright-yellow.svg)](https://playwright.dev/) [![Observability](https://img.shields.io/badge/Observability-LangSmith-red.svg)](https://smith.langchain.com/)

UCP Portal Assistant is an agentic AI system for managing University of Central Punjab (UCP) Student Portal data.

The system connects to the portal using Playwright web automation, caches records in a local SQLite database, and provides an interface via 2-way ntfy push notifications or a terminal CLI.

---

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Agent Workflow Diagram](#agent-workflow-diagram)
- [Active Model Configuration](#active-model-configuration)
- [Features](#features)
- [Project Directory Map](#project-directory-map)
- [Tool Suite](#tool-suite)
- [Installation & Setup](#installation--setup)
- [Configuration (.env)](#configuration-env)
- [Usage Guide](#usage-guide)
- [Observability & Tracing](#observability--tracing)
- [24/7 Cloud Deployment Guide](#247-cloud-deployment-guide)

---

## Architecture Overview

The system consists of five main components:

1. **Scraper Layer (`ucp_scraper.py`)**: Uses Playwright to log into the UCP Portal and fetch student records (dashboard, timetables, transcripts, course materials, invoices).
2. **Database & Cache Manager (`uni_db_manager.py`)**: Caches portal data in a local SQLite database (`uni_data.db`).
3. **Tool Registry (`ucp_tools.py`)**: Exposes 11 tools with JSON schema docstrings for LLM function calling.
4. **Agent Engine (`uni_agent_ntfy.py` / `uni_agent_test.py`)**: Implements a LangGraph StateGraph workflow with entry-point memory summarization, conditional tool execution (`tools_condition`), ToolNode, and checkpointer state memory (`MemorySaver`).
5. **2-Way Mobile Interface**: Listens on ntfy.sh long-polling JSON streams to send push notification replies.

---

## Agent Workflow Diagram

### High-Level Graph Flow

![UCP Agent Graph](agent_graph.png)

```mermaid
graph TD;
    __start__([__start__])
    summarize(summarize_node)
    agent(agent_node)
    tools(ToolNode)
    __end__([__end__])
    
    __start__ --> summarize;
    summarize --> agent;
    agent -.-> tools_condition;
    tools_condition -.-> tools;
    tools_condition -.-> __end__;
    tools --> agent;
```

### Graph Execution Cycle
1. **User Query**: Received via ntfy.sh or Terminal.
2. **Summarize Node (`summarize`)**: Compresses conversation history when message count exceeds threshold, removing old messages using `RemoveMessage`.
3. **Agent Node (`agent`)**: Injects existing summary into SystemMessage and invokes the bound LLM.
4. **Conditional Router (`tools_condition`)**: Routes to ToolNode if tools are requested, or END if no tool call is needed.
5. **Tool Execution (`tools`)**: Executes the database tool and routes results back to agent.

---

## Active Model Configuration

The project's LLM bindings are managed in `models.py`.

- **Currently Active Provider**: Groq API (`ChatGroq`)
- **Currently Active Model**: `openai/gpt-oss-120b`

You can switch models in `models.py` by changing the provider parameter:
```python
# Select from 'groq', 'deepseek', or 'ollama'
llm, llm_with_tools = get_llm(provider="groq")
```

---

## Features

- **2-Way Push Communication**: Receive push notifications and send replies using ntfy.
- **Memory Pruning**: Automatic conversation summarization for long threads.
- **Multi-Provider Support**: Compatible with Groq (`openai/gpt-oss-120b`), DeepSeek (`deepseek-chat`), and Ollama (`llama3.2:3b`).
- **File Download Support**: Downloads uploaded course materials directly to local storage.

---

## Project Directory Map

```
UCP-Portal-Assistant/
├── .env                  # Environment configuration template
├── .gitignore            # Git exclusion rules
├── agent_graph.png       # Workflow graph diagram
├── ucp_tools.py          # 11 UCP database tools
├── prompts.py            # System prompts & summary templates
├── models.py             # LLM provider factory & tool bindings
├── uni_agent_ntfy.py     # 2-Way Mobile Push Agent
├── uni_agent_test.py     # Terminal Sandbox CLI
├── ucp_scraper.py        # Playwright Portal Scraper
├── uni_db_manager.py     # SQLite Database Manager
├── ntfy_twoway_bot.py    # ntfy listener script
└── README.md             # Documentation
```

---

## Tool Suite

| Tool Name | Purpose |
| :--- | :--- |
| `get_student_dashboard` | Returns Roll Number, Department, CGPA, Credits, and Enrolled Courses. |
| `get_full_timetable` | Returns weekly schedule with start/end times, instructor names, and rooms. |
| `get_academic_history` | Returns past transcripts and course grades. |
| `get_full_course_details` | Returns course outline, attendance logs, gradebooks, and assignment due dates. |
| `download_file` | Downloads course materials to local storage. |
| `get_invoices` | Returns financial invoices, payable amounts, and payment status. |
| `get_notifications` | Returns portal alerts and announcements. |
| `get_exam_datesheet` | Returns exam dates, times, and venues. |
| `get_detailed_profile` | Returns profile, address, and guardian information. |
| `get_current_time` | Returns local timestamp and day of week. |
| `sync_university_data` | Triggers a fresh live portal re-scrape. |

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- Playwright Chromium

### Installation Steps

```bash
git clone <repository_url>
cd <repository_directory>

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

---

## Configuration (.env)

Create a `.env` file in the project root:

```env
# UCP Portal Credentials
UCP_EMAIL=your_student_email_here
UCP_PASSWORD=your_portal_password_here

# LLM Provider API Keys
GROQ_API_KEY=your_groq_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Mobile Push Notification Settings (ntfy.sh)
NTFY_TOPIC=your_ntfy_topic_here
BOT_TITLE="your_bot_title_here"
BOT_TAG=your_bot_tag_here

# LangSmith Observability & Tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langchain_api_key_here
LANGCHAIN_PROJECT=your_project_name_here
```

---

## Usage Guide

### 1. Mobile Push Agent (`uni_agent_ntfy.py`)

```bash
python uni_agent_ntfy.py
```

- Subscribe to your ntfy topic on your mobile device.
- Send messages via ntfy to communicate with the agent.

### 2. Terminal CLI (`uni_agent_test.py`)

```bash
python uni_agent_test.py
```

Runs the CLI with token streaming.

---

## Observability & Tracing

LangSmith tracing is integrated for step tracking, tool calls, and performance monitoring under the configured project name.

---

## 24/7 Cloud Deployment Guide

To run `uni_agent_ntfy.py` continuously 24/7 without needing to manually run the script on your computer, you can deploy it as a background service.

### Option 1: Systemd Service (Linux VPS / Oracle Cloud / AWS EC2)

Create a service configuration `/etc/systemd/system/ucp-agent.service`:

```ini
[Unit]
Description=UCP Agent 24/7 Mobile Push Listener
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/python uni_agent_ntfy.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ucp-agent
sudo systemctl start ucp-agent
```

### Option 2: Docker Container / Background Worker

Deploy `uni_agent_ntfy.py` as a background worker process on hosting providers like Render, Railway, or Fly.io so it continuously listens to the ntfy long-polling stream 24/7.
