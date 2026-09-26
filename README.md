# UCP Portal Assistant

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/) [![Framework](https://img.shields.io/badge/Framework-LangGraph%20%7C%20LangChain-orange.svg)](https://langchain-ai.github.io/langgraph/) [![LLM Provider](https://img.shields.io/badge/LLM-Groq-green.svg)](https://groq.com/) [![Push System](https://img.shields.io/badge/Push%20Notifications-ntfy.sh%202--Way-purple.svg)](https://ntfy.sh) [![Database](https://img.shields.io/badge/Database-SQLite%20%2B%20Playwright-yellow.svg)](https://playwright.dev/) [![Observability](https://img.shields.io/badge/Observability-LangSmith-red.svg)](https://smith.langchain.com/)

UCP Portal Assistant is an agentic AI system for managing University of Central Punjab (UCP) Student Portal data.

The system connects to the portal using Playwright web automation, caches records in a local SQLite database, and provides an interface via 2-way ntfy push notifications or a terminal CLI.

## Demo

https://github.com/user-attachments/assets/15611a45-7a32-4c0d-a198-ddc2ab486823

----

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
- [Observability & Tracing](#observability)
- [Important Disclaimer](#disclaimer)
- [Azure Cloud Deployment Guide](#azure)
- [Maintenance & Essential Commands](#maintenance)
- [Contributing](#contributing)

---

## Architecture Overview

The system consists of six main components:

1. **Scraper Layer (`ucp_scraper.py`)**: Uses Playwright to log into the UCP Portal and fetch student records (dashboard, timetables, transcripts, course materials, invoices).
2. **Database & Cache Manager (`uni_db_manager.py`)**: Caches portal data in a local SQLite database (`uni_data.db`).
3. **Tool Registry (`ucp_tools.py`)**: Exposes 11 tools with JSON schema docstrings for LLM function calling.
4. **Agent Engine (`uni_agent_ntfy.py` / `uni_agent_test.py`)**: Implements a LangGraph StateGraph workflow with entry-point memory summarization, conditional tool execution (`tools_condition`), ToolNode, and persistent checkpointer state memory (`SqliteSaver`).
5. **2-Way Mobile Interface**: Listens on ntfy.sh long-polling JSON streams to send push notification replies.
6. **Proactive Alert Engine (`proactive_alerts.py`)**: Runs an APScheduler background process to monitor upcoming classes and injects push reminders with state directly into the LLM's memory.

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
# The bot explicitly uses Groq as the fast LLM inference provider
llm, llm_with_tools = get_llm(provider="groq")
```

---

## Features

- **2-Way Push Communication**: Receive push notifications and send replies using ntfy.
- **Proactive Background Alerts**: Uses `APScheduler` to push class reminders 5 minutes before they start and asks for feedback exactly when they finish.
- **State Injection**: Proactive alerts are injected directly into the LLM's checkpointer memory so the AI remembers the context when you reply.
- **Persistent Memory (SQLite)**: Saves conversation history in a resilient checkpointer database (`memory.db`), so the AI perfectly remembers context even after a server restart.
- **Memory Pruning**: Automatic conversation summarization for long threads to minimize LLM token usage.
- **Smart Error Recovery**: Intercepts API rate limits and execution errors, pushing diagnostic alerts directly to your phone instead of crashing silently.
- **Lightning Fast Inference**: Powered by Groq's LPU inference engine for near-instant responses.
- **Mobile File Attachments & Caching**: Downloads course materials to the server, caches them to save bandwidth, and pushes them directly to your phone as native file attachments!

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

1. **Fork the Repository:** Click the "Fork" button at the top right of this repository to create your own copy (this is required for the auto-updater CD pipeline to work for your own server).
2. **Clone your Fork:**
```bash
git clone https://github.com/<your_github_username>/ucp-portal-assistant.git
cd ucp-portal-assistant
```

3. **Install Dependencies:**

**For Mac/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

**For Windows:**
```powershell
python -m venv .venv
.venv\Scripts\activate
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

# Mobile Push Notification Settings (ntfy.sh)
NTFY_TOPIC=your_ntfy_topic_here
BOT_TITLE="your_bot_title_here"
BOT_TAG=your_bot_tag_here

# LangSmith Observability & Tracing (Optional)
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

<a id="observability"></a>
## 📊 Observability & Tracing

LangSmith tracing is seamlessly integrated. Set `LANGCHAIN_TRACING_V2=true` in your `.env` to monitor agent step tracking, tool execution latency, and overall LLM performance under your configured LangChain project name.

---

<a id="disclaimer"></a>
## ⚠️ Important Disclaimer

**This is an unofficial, community-driven project.** 
It is not affiliated with, endorsed by, or connected to the University of Central Punjab (UCP) in any way. 

- **Privacy First:** Your university credentials (`UCP_EMAIL`, `UCP_PASSWORD`) never leave your local machine. They are exclusively used by the local Playwright instance to authenticate directly with Microsoft SSO.
- **No Cloud Database:** All scraped data is stored locally on your machine in `uni_data.db`.
- **Use at Your Own Risk:** This tool automates portal interactions. The developers are not responsible for any account locks, missed deadlines, or portal availability issues.



<a id="azure"></a>
# ☁️ Azure Cloud Deployment Guide

This guide covers exactly how to deploy the **UCP Portal Assistant** to run 24/7 in the cloud, completely for free using the **GitHub Student Developer Pack** and **Microsoft Azure**.

---

## 1. Create a Free Azure Virtual Machine
Since the bot uses Playwright (a headless browser) and WebSockets (for real-time push notifications), serverless platforms like Vercel or AWS Lambda will not work. A raw Linux Virtual Machine (VM) is required.

1. Go to the [GitHub Student Developer Pack](https://education.github.com/pack) and activate the **Microsoft Azure** offer to get $100 in free credit and free 12-month services (no credit card required).
2. Log into the [Azure Portal](https://portal.azure.com/) using your university email (`@ucp.edu.pk`).
3. Search for **Virtual machines** and click **Create -> Azure virtual machine**.

### Virtual Machine Settings:
- **Subscription:** Azure for Students
- **Resource group:** Create a new one (e.g., `ucp-bot-rg`)
- **Virtual machine name:** `ucp-bot-server`
- **Region:** **IMPORTANT:** Azure heavily restricts student accounts. If you get a `RequestDisallowedByAzure` error, you must select a region allowed by your specific policy. Safe bets are often **Central India**, **UAE North**, **Central US**, or **West Europe**.
- **Availability options:** `No infrastructure redundancy required` (This unlocks the free tier sizes).
- **Image:** Ubuntu Server 24.04 LTS
- **Size:** Click "See all sizes" and search for **`B1`**. Select **`Standard_B1s (free services eligible)`**.
- **Authentication type:** Password (create a username and a strong 12-character password).
- **Inbound port rules:** Allow selected ports -> **SSH (22)**.

Click **Review + create** and then **Create**. Wait 2-3 minutes for deployment to finish, click **Go to resource**, and copy your **Public IP address**.

---

## 2. Configure GitHub Secrets
Since your GitHub repository is public, it doesn't contain your `.env` file for security reasons. You must pass your secrets to GitHub Actions so it can securely deploy them to Azure.

Go to your **GitHub Repository -> Settings -> Secrets and variables -> Actions** and create the following secrets:
- `DOCKER_USERNAME`: Your Docker Hub username.
- `DOCKER_PASSWORD`: Your Docker Hub password or Access Token.
- `AZURE_HOST`: Your Azure Virtual Machine's public IP address.
- `AZURE_USERNAME`: Your Azure VM username (usually `azureuser`).
- `AZURE_PASSWORD`: The password you type to log into your Azure server.
- `ENV_FILE_CONTENTS`: The entire contents of your local `.env` file (copy and paste the whole block).

---

## 3. Deploy via GitHub Actions (CI/CD)
The bot uses a professional Docker + GitHub Actions CI/CD pipeline. You do not need to SSH into the server, install Playwright, or configure `tmux` manually!

Simply commit and push your code to the `main` branch:
```bash
git add .
git commit -m "Deploy bot"
git push
```

Go to the **Actions** tab on your GitHub repository. The pipeline will automatically:
1. Build the Docker image on GitHub's servers.
2. Push the image to Docker Hub.
3. SSH into your Azure server.
4. Inject your `.env` secrets.
5. Pull the new Docker image and spin up the bot in the background.

---

## 4. Persistent Memory (Docker Volumes)
The Docker container maps a local `~/ucp-bot/bot_data` directory on the Azure server to persist your `uni_data.db` and `memory.db`. 
Even when GitHub Actions destroys the old container and boots up a new one during an update, your bot will perfectly remember its scraped timetables and conversation history!

---

<a id="maintenance"></a>
## 🛠️ Maintenance & Essential Commands

### How to view live logs on Azure:
If you want to see the bot processing messages live, SSH into your Azure server (`ssh username@IP_ADDRESS`) and run:
```bash
docker logs -f ucp-portal-assistant
```

### How to restart the bot:
```bash
docker restart ucp-portal-assistant
```

### How to completely wipe the bot from Azure:
If you ever want to start from a 100% clean slate (WARNING: this will permanently delete your database memory!):
```bash
docker rm -f ucp-portal-assistant
rm -rf ~/ucp-bot
```


---

<a id="contributing"></a>
## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
Feel free to check the [issues page](../../issues) if you want to contribute.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---
*Built with ❤️ using LangChain and LangGraph.*
