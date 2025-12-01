"""
DFIR Analysis Agent

This agent replicates and extends the functionality of the main DFIR agent
with additional capabilities for user prompts and file analysis.
"""

import os
from pathlib import Path
from openai import AsyncOpenAI
from cai.sdk.agents import Agent, OpenAIChatCompletionsModel, function_tool
from dotenv import load_dotenv

# Import tools from CAI framework
try:
    from cai.tools.reconnaissance.generic_linux_command import generic_linux_command
    from cai.tools.reconnaissance.exec_code import execute_code
    from cai.tools.command_and_control.sshpass import run_ssh_command_with_credentials
    from cai.tools.web.search_web import make_web_search_with_explanation
    from cai.tools.reconnaissance.shodan import shodan_search
    from cai.tools.web.google_search import google_search
    from cai.tools.misc.reasoning import think
except ImportError:
    # Fallback simple implementations if CAI tools not available
    @function_tool
    def generic_linux_command(command: str) -> str:
        """Execute a Linux command"""
        import subprocess
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return f"Exit code: {result.returncode}\nStdout: {result.stdout}\nStderr: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    @function_tool 
    def execute_code(code: str, language: str = "python") -> str:
        """Execute code"""
        return f"Code execution simulated for: {code[:100]}..."
    
    @function_tool
    def think(reasoning: str) -> str:
        """Reasoning tool"""
        return f"Thinking: {reasoning}"

load_dotenv()

def _load_system_prompt(prompt_file: str) -> str:
    """
    Load system prompt from agents/prompts/ directory
    
    Args:
        prompt_file: Name of the prompt file (e.g., 'system_dfir_agent.md')
        
    Returns:
        str: Content of the prompt file
    """
    prompt_path = Path(__file__).parent / "prompts" / prompt_file
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"⚠️  Warning: Prompt file {prompt_file} not found at {prompt_path}")
        print(f"   Using fallback prompt")
        return ""
    except Exception as e:
        print(f"⚠️  Error loading prompt file {prompt_file}: {e}")
        return ""

def create_dfir_agent() -> Agent:
    """
    Create and configure the DFIR analysis agent
    
    Returns:
        Agent: Configured DFIR agent
    """
    
    # Define tool list based on available API keys and imports
    tools = [
        generic_linux_command,
        execute_code,
        think,
    ]
    
    # Add additional tools if available and configured
    if os.getenv("PERPLEXITY_API_KEY"):
        try:
            tools.append(make_web_search_with_explanation)
        except NameError:
            pass
    
    if os.getenv("SHODAN_API_KEY"):
        try:
            tools.append(shodan_search)
        except NameError:
            pass
    
    if os.getenv("GOOGLE_SEARCH_API_KEY") and os.getenv("GOOGLE_SEARCH_CX"):
        try:
            tools.append(google_search)
        except NameError:
            pass
    
    # Try to add SSH tool if available
    try:
        tools.append(run_ssh_command_with_credentials)
    except NameError:
        pass
    
    # Configure model client more explicitly
    model_name = os.getenv("CAI_MODEL", "alias1")
    
    print(f"🤖 Configuring DFIR agent with model: {model_name}")
    
    # Create model client based on configuration
    # Configure timeouts (very high values to avoid timeouts)
    ollama_timeout = float(os.getenv("OLLAMA_API_TIMEOUT", "1800.0"))  # 30 minutos por defecto
    openai_timeout = float(os.getenv("OPENAI_API_TIMEOUT", "600.0"))   # 10 minutos por defecto
    
    if model_name.lower() == "ollama":
        # Use Ollama local instance
        ollama_base_url = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1")
        ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
        print(f"✅ Using Ollama configuration: {ollama_base_url} with model {ollama_model}")
        print(f"⏱️  API Timeout: {ollama_timeout}s ({ollama_timeout/60:.1f} minutes)")
        openai_client = AsyncOpenAI(
            base_url=ollama_base_url,
            api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
            timeout=ollama_timeout
        )
        # Override model name to use the Ollama model
        model_name = ollama_model
    elif "alias" in model_name.lower():
        print("✅ Using Alias model configuration")
        print(f"🔍 ALIAS_API_KEY configured: {'✅' if os.getenv('ALIAS_API_KEY') else '❌'}")
        print(f"⏱️  API Timeout: {openai_timeout}s ({openai_timeout/60:.1f} minutes)")
        openai_client = AsyncOpenAI(
            timeout=openai_timeout
        )  # CAI handles Alias routing automatically
    else:
        print("✅ Using standard OpenAI/external API configuration")
        print(f"⏱️  API Timeout: {openai_timeout}s ({openai_timeout/60:.1f} minutes)")
        # Support custom API base URL for external endpoints
        api_base = os.getenv("OPENAI_API_BASE")
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ALIAS_API_KEY")
        if api_base:
            print(f"   Using custom API base: {api_base}")
            openai_client = AsyncOpenAI(base_url=api_base, api_key=api_key, timeout=openai_timeout)
        else:
            openai_client = AsyncOpenAI(api_key=api_key, timeout=openai_timeout)
    
    # Create the agent
    dfir_agent = Agent(
        name="DFIR Analysis Agent",
        instructions=_load_system_prompt("system_dfir_agent.md"),
        description="""Specialized agent for Digital Forensics and Incident Response.
                       Expert in investigating security incidents and analyzing digital evidence.
                       Provides comprehensive forensic analysis with technical details.""",
        model=OpenAIChatCompletionsModel(
            model=model_name,
            openai_client=openai_client,
        ),
        tools=tools,
    )
    
    return dfir_agent
