import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from ucp_tools import tools

load_dotenv()

def get_llm(provider: str = "groq", temperature: float = 0.0):
    """Factory function to instantiate and bind tools to the selected LLM provider.
    Supported providers: 'groq' (default)"""
    
    provider_clean = provider.lower().strip()
    
    if provider_clean == "groq":
        # Groq Flagship OpenAI GPT-OSS 120B 
        llm = ChatGroq(
            model="openai/gpt-oss-120b",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=temperature
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Currently only 'groq' is fully supported in this branch.")
        
    llm_with_tools = llm.bind_tools(tools)
    return llm, llm_with_tools

# Default LLM instances for quick import across scripts
llm, llm_with_tools = get_llm(provider="groq")
