"""
Reporting Agent

This agent replicates and extends the functionality of the main reporting agent
with specialized capabilities for generating DFIR HTML reports.
"""

import os
from openai import AsyncOpenAI
from cai.sdk.agents import Agent, OpenAIChatCompletionsModel, function_tool
from dotenv import load_dotenv
from pathlib import Path

# Import tools from CAI framework
try:
    from cai.tools.reconnaissance.generic_linux_command import generic_linux_command
    from cai.tools.reconnaissance.exec_code import execute_code
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

load_dotenv()

def _load_system_prompt(prompt_file: str) -> str:
    """
    Load system prompt from agents/prompts/ directory
    
    Args:
        prompt_file: Name of the prompt file (e.g., 'system_reporting_agent.md')
        
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

@function_tool
def get_html_template() -> str:
    """Get the HTML template for DFIR reports"""
    try:
        template_path = Path(__file__).parent.parent / "html_template" / "html_report_template.html"
        print(f"📄 Reading HTML template from: {template_path}")
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
            print(f"✅ Successfully read template, length: {len(template)} chars")
            return template
    except Exception as e:
        error_msg = f"Error loading HTML template: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

@function_tool
def read_dfir_analysis_json() -> str:
    """Read and return the DFIR analysis from dfir_reports/dfir_analysis.json"""
    try:
        import json
        analysis_path = Path(__file__).parent.parent / "dfir_reports" / "dfir_analysis.json"
        print(f"📖 Reading DFIR analysis from: {analysis_path}")
        with open(analysis_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            result = json.dumps(data, indent=2, ensure_ascii=False)
            print(f"✅ Successfully read JSON, length: {len(result)} chars")
            return result
    except FileNotFoundError:
        error_msg = "Error: dfir_reports/dfir_analysis.json not found. Please run DFIR analysis first."
        print(f"❌ {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Error reading DFIR analysis: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

@function_tool
def generate_html_from_template() -> str:
    """
    Generate HTML report by reading the template and JSON files directly.
    This tool does ALL the work - no parameters needed.
    It automatically reads dfir_reports/dfir_analysis.json and html_template/html_report_template.html.
    
    Returns:
        Complete HTML document with all placeholders replaced
    """
    try:
        import json
        print("="*60)
        print("🔧 generate_html_from_template CALLED - STARTING PROCESSING")
        print("="*60)
        
        # Read JSON data directly
        analysis_path = Path(__file__).parent.parent / "dfir_reports" / "dfir_analysis.json"
        print(f"📖 Reading JSON from: {analysis_path}")
        with open(analysis_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ JSON loaded, found {len(data)} fields")
        
        # Read template directly
        template_path = Path(__file__).parent.parent / "html_template" / "html_report_template.html"
        print(f"📄 Reading template from: {template_path}")
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
        print(f"✅ Template loaded, length: {len(template)} chars")
        
        # Start with template
        html = template
        
        # Replace simple string placeholders
        simple_replacements = {
            "INCIDENT_TITLE": data.get("INCIDENT_TITLE", ""),
            "INCIDENT_DATES": data.get("INCIDENT_DATES", ""),
            "EXECUTIVE_SUMMARY": data.get("EXECUTIVE_SUMMARY", ""),
            "TIMELINE_DESCRIPTION": data.get("TIMELINE_DESCRIPTION", ""),
            "FORENSIC_CONCLUSION": data.get("FORENSIC_CONCLUSION", ""),
            "REPORT_FOOTER": data.get("REPORT_FOOTER", ""),
        }
        
        print("🔄 Starting placeholder replacements...")
        
        # Replace simple string placeholders
        for placeholder, value in simple_replacements.items():
            html = html.replace(f"{{{{{placeholder}}}}}", str(value))
            print(f"  ✓ Replaced {placeholder}")
        
        # Replace HTML content placeholders (already formatted)
        html_content = {
            "ENTRY_POINTS_CONTENT": data.get("ENTRY_POINTS_CONTENT", ""),
            "IOCS_CONTENT": data.get("IOCS_CONTENT", ""),
            "RECOMMENDATIONS_CONTENT": data.get("RECOMMENDATIONS_CONTENT", ""),
        }
        
        for placeholder, value in html_content.items():
            html = html.replace(f"{{{{{placeholder}}}}}", str(value))
            print(f"  ✓ Replaced {placeholder}")
        
        # Convert STATISTICS_CARDS array to HTML
        print("🔄 Processing STATISTICS_CARDS...")
        if "STATISTICS_CARDS" in data and isinstance(data["STATISTICS_CARDS"], list):
            stats_html = ""
            for stat in data["STATISTICS_CARDS"]:
                number = stat.get("number", 0)
                label = stat.get("label", "")
                stats_html += f'<div class="stat-card"><div class="number">{number}</div><div class="label">{label}</div></div>\n'
            html = html.replace("{{STATISTICS_CARDS}}", stats_html)
            print(f"✅ STATISTICS_CARDS converted: {len(data['STATISTICS_CARDS'])} cards")
        else:
            html = html.replace("{{STATISTICS_CARDS}}", "")
            print("⚠️  STATISTICS_CARDS not found or not a list, replaced with empty string")
        
        # Convert TIMELINE_EVENTS array to HTML
        print("🔄 Processing TIMELINE_EVENTS...")
        if "TIMELINE_EVENTS" in data and isinstance(data["TIMELINE_EVENTS"], list):
            timeline_html = ""
            for i, event in enumerate(data["TIMELINE_EVENTS"], 1):
                timestamp = event.get("timestamp", "")
                title = event.get("title", "")
                description = event.get("description", "")
                source_ip = event.get("source_ip", "N/A")
                target_ip = event.get("target_ip", "N/A")
                
                timeline_html += f'''<div class="timeline-item">
                    <div class="timeline-dot"></div>
                    <div class="timeline-time">{timestamp}</div>
                    <div class="timeline-content">
                        <div class="timeline-title">{title}</div>
                        <p>{description}</p>
                        <small>Source: {source_ip} → Target: {target_ip}</small>
                    </div>
                </div>
'''
            html = html.replace("{{TIMELINE_EVENTS}}", timeline_html)
            print(f"✅ TIMELINE_EVENTS converted: {len(data['TIMELINE_EVENTS'])} events")
        else:
            html = html.replace("{{TIMELINE_EVENTS}}", "")
            print("⚠️  TIMELINE_EVENTS not found or not a list, replaced with empty string")
        
        # Convert ATTACK_OBJECTIVES array to HTML
        print("🔄 Processing ATTACK_OBJECTIVES...")
        if "ATTACK_OBJECTIVES" in data and isinstance(data["ATTACK_OBJECTIVES"], list):
            objectives_html = ""
            for obj in data["ATTACK_OBJECTIVES"]:
                objective = obj.get("objective", "")
                details = obj.get("details", [])
                details_list = "".join([f"<li>{detail}</li>" for detail in details])
                objectives_html += f'''<div class="objective-card">
                    <h3>{objective}</h3>
                    <ul>{details_list}</ul>
                </div>
'''
            html = html.replace("{{ATTACK_OBJECTIVES}}", objectives_html)
            print(f"✅ ATTACK_OBJECTIVES converted: {len(data['ATTACK_OBJECTIVES'])} objectives")
        else:
            html = html.replace("{{ATTACK_OBJECTIVES}}", "")
            print("⚠️  ATTACK_OBJECTIVES not found or not a list, replaced with empty string")
        
        # Save HTML to file immediately
        output_path = Path(__file__).parent.parent / "dfir_reports" / "dfir_report.html"
        print(f"💾 Saving HTML to: {output_path}")
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ HTML saved successfully, {len(html)} chars written to file")
        
        print(f"✅ HTML generation complete, final length: {len(html)} chars")
        print("="*60)
        
        # Return a short confirmation instead of the full HTML to avoid timeout
        return f"HTML report generated successfully and saved to {output_path}. Report length: {len(html)} characters."
        
    except Exception as e:
        error_msg = f"Error generating HTML: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

def create_reporting_agent() -> Agent:
    """
    Create and configure the reporting agent
    
    Returns:
        Agent: Configured reporting agent
    """
    
    # Define tools for the reporting agent
    # Simplified: generate_html_from_template reads files directly, no need for other tools
    tools = [
        generate_html_from_template,  # This tool does everything - reads JSON and template internally
    ]
    
    # Configure model client more explicitly
    model_name = os.getenv("CAI_MODEL", "alias1")
    
    print(f"🤖 Configuring Reporting agent with model: {model_name}")
    
    # Create model client based on configuration
    # Configure timeouts (very high values to avoid timeouts)
    # IMPORTANT: These must be higher than CAI_REPORT_TIMEOUT to prevent premature API timeouts
    ollama_timeout = float(os.getenv("OLLAMA_API_TIMEOUT", "3600.0"))  # 60 minutos por defecto
    openai_timeout = float(os.getenv("OPENAI_API_TIMEOUT", "3600.0"))   # 60 minutos por defecto
    
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
    
    # Add input and output path files to system prompt
    system_prompt = _load_system_prompt("system_reporting_agent.md")
    system_prompt += f"\n\n**IMPORTANT**: Read the DFIR analysis from the JSON file: dfir_reports/dfir_analysis.json"
    system_prompt += f"\nDo NOT use the logs directory. The analysis is stored in dfir_reports/dfir_analysis.json"
    system_prompt += f"\nOutput path: dfir_reports/dfir_report.html"

    # Create the agent
    reporting_agent = Agent(
        name="DFIR Reporting Agent",
        instructions=system_prompt,
        description="""Specialized agent for generating professional HTML reports from DFIR analysis.
                       Expert in transforming technical forensic data into comprehensive,
                       visually appealing reports for stakeholders.""",
        model=OpenAIChatCompletionsModel(
            model=model_name,
            openai_client=openai_client,
        ),
        tools=tools,
    )
    
    return reporting_agent
