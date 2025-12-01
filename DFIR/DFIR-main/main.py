"""
Main entry point for DFIR Report Generation

This module orchestrates the sequential execution of DFIR analysis and report generation.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from cai.sdk.agents import Runner, trace, set_tracing_disabled

# Import agents with absolute imports
# Add current directory to path for local imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from agents.dfir_agent import create_dfir_agent
from agents.reporting_agent import create_reporting_agent


class DFIRReportManager:
    """Manages the DFIR analysis and report generation workflow"""
    
    def __init__(self):
        # Configure tracing for detailed logs
        set_tracing_disabled(False)  # Enable detailed tracing
        
        self.dfir_agent = create_dfir_agent()
        self.reporting_agent = create_reporting_agent()
        
    def get_latest_file_in_logs_directory(self) -> str:
        """Get the latest file in the logs/ directory"""
        logs_dir = Path("logs")
        if logs_dir.exists() and logs_dir.is_dir():
            log_files = [f for f in logs_dir.iterdir() if f.is_file()]
            if log_files:
                return str(max(log_files, key=lambda f: f.stat().st_mtime))
        return None

    async def run_dfir_analysis(self, user_prompt: str = None, file_path: str = None) -> str:
        """
        Run DFIR analysis with user prompt and optional file
        
        Args:
            user_prompt (str, optional): User's analysis request. If None, uses default prompt.
            file_path (str, optional): Path to file to analyze
            
        Returns:
            str: DFIR analysis results
        """
        # Set default prompt if none provided
        if user_prompt is None:
            if file_path:
                user_prompt = f"Using the Wazuh log in {file_path} please conduct a complete forensics analysis to discover the potential entry points of the attacker, pivoting points, and objectives"
            else:
                user_prompt = "Please conduct a complete forensics analysis to discover the potential entry points of the attacker, pivoting points, and objectives"
        
        # Construct full prompt for DFIR analysis
        full_prompt = f"{user_prompt}"
        
        if file_path and Path(file_path).exists():
            # Only add file reference if not already in user prompt
            if file_path not in user_prompt:
                full_prompt += f"\n\nFile to analyze: {file_path}"
            full_prompt += f"\nPlease read and analyze this file conducting a complete forensic analysis."
        
        full_prompt += """
        
        Conduct a complete digital forensics analysis and output the results as a STRUCTURED JSON object.

        **CRITICAL OUTPUT FORMAT:**
        You MUST save your analysis as a valid JSON object to `dfir_reports/dfir_analysis.json` with field names that EXACTLY match the HTML template placeholders:
        
        **REQUIRED FIELDS (must match template placeholders exactly):**
        - INCIDENT_TITLE: Title of the incident (string)
        - INCIDENT_DATES: Date range of the incident (string, e.g., "2024-01-15 08:12:02 - 2024-01-15 08:12:21 UTC")
        - EXECUTIVE_SUMMARY: Brief 2-3 sentence summary (string)
        - STATISTICS_CARDS: Array of objects with "number" and "label" fields (e.g., [{"number": 18, "label": "Total IOCs"}, ...])
        - ENTRY_POINTS_CONTENT: HTML formatted content for entry points (string with HTML, use <div class='ip-list'> and <div class='ip-card'>)
        - TIMELINE_DESCRIPTION: Brief description of timeline (string)
        - TIMELINE_EVENTS: Array of objects with timestamp, title, description, source_ip, target_ip
        - ATTACK_OBJECTIVES: Array of objects with "objective" (string) and "details" (array of strings)
        - IOCS_CONTENT: HTML formatted content for IOCs (string with HTML, use <div class='ioc-list'>)
        - RECOMMENDATIONS_CONTENT: HTML formatted content for recommendations (string with HTML, use <div class='recommendation-box'>)
        - FORENSIC_CONCLUSION: Complete forensic conclusion text (string)
        - REPORT_FOOTER: Footer text with metadata (string)
        
        **IMPORTANT:** Field names must be in UPPERCASE with underscores to match template placeholders exactly!

        **IMPORTANT:**
        - DO NOT create a JSON with a single "analysis" field containing markdown
        - DO create a properly structured JSON with all fields as separate JSON properties
        - All text values must be plain strings (no markdown formatting)
        - Use arrays for lists, objects for structured data
        - The JSON must be valid and parseable
        - Save the JSON to `dfir_reports/dfir_analysis.json` using file writing tools
        - After saving, your final output should be a brief confirmation like "Analysis saved to dfir_reports/dfir_analysis.json"
        - DO NOT return the full JSON or markdown in your final output - just confirm the file was saved

        Extract and organize all findings into this structured format.
        """
        
        # Run DFIR analysis
        print("🔍 Running DFIR analysis...")
        # print(f"   📝 Prompt length: {len(full_prompt):,} characters")
        print(f"   📝 Prompt: {full_prompt}")
        
        # Configure analysis timeout (very high value)
        analysis_timeout = int(os.getenv('CAI_ANALYSIS_TIMEOUT', '3600'))  # 1 hora por defecto
        print(f"⏱️  Analysis timeout: {analysis_timeout}s ({analysis_timeout/60:.1f} minutes)")
        
        # Run DFIR analysis using Runner with timeout
        result = await asyncio.wait_for(
            Runner.run(
                starting_agent=self.dfir_agent,
                input=full_prompt,
                max_turns=30  # Allow enough turns for complex analysis
            ),
            timeout=analysis_timeout
        )
        
        # CRITICAL: The agent should have saved the JSON file directly
        # Check if the JSON file exists and is valid - use that instead of final_output
        # (final_output may contain markdown summary that would overwrite the JSON)
        analysis_file = Path("dfir_reports") / "dfir_analysis.json"
        if analysis_file.exists():
            try:
                with open(analysis_file, 'r', encoding='utf-8') as f:
                    saved_json = json.load(f)
                    # Verify it's structured JSON (check for template placeholder fields)
                    if isinstance(saved_json, dict) and ("EXECUTIVE_SUMMARY" in saved_json or "executive_summary" in saved_json):
                        print("✅ Using structured JSON from file (agent saved it correctly)")
                        return json.dumps(saved_json, indent=2, ensure_ascii=False)
                    elif isinstance(saved_json, dict) and "analysis" in saved_json:
                        # Old format - return as is
                        print("⚠️  Found old format JSON with 'analysis' field")
                        return json.dumps(saved_json, indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, Exception) as e:
                print(f"⚠️  Error reading saved JSON file: {e}")
                print("   Using final_output instead")
        
        # Fallback: use final_output if file doesn't exist or is invalid
        print("⚠️  JSON file not found or invalid, using final_output")
        return result.final_output
    
    async def generate_report(self,
                              incident_title: str = "DFIR Analysis Report") -> str:
        """
        Generate HTML report from DFIR analysis
        
        Args:
            dfir_analysis (str): Results from DFIR analysis
            incident_title (str): Title for the report
            
        Returns:
            str: Generated HTML report
        """
        # Construct prompt for report generation
        # IMPORTANT: Explicitly tell the agent to read from dfir_analysis.json, not from logs
        report_prompt = f"""Generate HTML report. Follow these steps EXACTLY:

Step 1: Call generate_html_from_template() - this tool reads everything automatically, no parameters needed
Step 2: Return the HTML string from step 1 as your final answer

DO NOT use any other tools.
DO NOT try to read files manually.
DO NOT add explanations - just call generate_html_from_template() and return its result.
The tool does EVERYTHING automatically."""
        
        print("📋 Generating HTML report from DFIR analysis...")
        
        # Configure report generation timeout (very high value)
        report_timeout = int(os.getenv('CAI_REPORT_TIMEOUT', '3600'))  # 1 hora por defecto
        print(f"⏱️  Report generation timeout: {report_timeout}s ({report_timeout/60:.1f} minutes)")
        
        # Run report generation using Runner with timeout
        # The agent will call generate_html_from_template() which saves the file directly
        result = await asyncio.wait_for(
            Runner.run(
                starting_agent=self.reporting_agent,
                input=report_prompt,
                max_turns=8  # Just need to call generate_html_from_template() and return
            ),
            timeout=report_timeout
        )
        
        # Log what we got back
        print(f"📋 Report generation completed. Agent output: {result.final_output[:200]}...")
        
        # The HTML is saved directly by generate_html_from_template, so read it from file
        report_path = Path("dfir_reports") / "dfir_report.html"
        if report_path.exists():
            print(f"📄 Reading generated HTML from: {report_path}")
            with open(report_path, 'r', encoding='utf-8') as f:
                html_report = f.read()
            print(f"✅ Successfully read HTML report, length: {len(html_report)} chars")
            return html_report
        else:
            # Fallback: return agent output (should contain error message)
            print(f"⚠️  HTML file not found at {report_path}, returning agent output")
            return result.final_output
    
    async def run_complete_workflow(self, user_prompt: str, file_path: str = None, 
                                  incident_title: str = "DFIR Analysis Report") -> tuple[str, str]:
        """
        Run the complete DFIR analysis and report generation workflow
        
        Args:
            user_prompt (str): User's analysis request
            file_path (str, optional): Path to file to analyze
            incident_title (str): Title for the report
            
        Returns:
            tuple[str, str]: (dfir_analysis, html_report)
        """
        with trace(workflow_name="DFIR Report Generation"):
            # Step 1: DFIR Analysis
            try:
                print("🚀 Step 1/2: Running DFIR Analysis...")
                dfir_analysis = await self.run_dfir_analysis(user_prompt, file_path)
                print("🟢 Step 1/2: DFIR Analysis completed\n")
                
            except Exception as e:
                print(f"❌ Step 1/2: DFIR Analysis failed: {e}")
                raise

            # Step 2: Report Generation
            try:
                print(f"🚀 Step 2/2: Generating HTML Report for the DFIR Analysis...")
                html_report = await self.generate_report(incident_title)
                print("🟢 Step 2/2: HTML Report generated\n")
            except Exception as e:
                error_msg = str(e).lower()
                if "timeout" in error_msg or "time" in error_msg:
                    print(f"⏱️ HTML Report generation timed out: {e}")
                    print("💡 Possible causes:")
                    print("   - Analysis too long for processing")
                    print("   - Template complexity issues") 
                    print("   - Model context limits exceeded")
                elif "token" in error_msg or "context" in error_msg:
                    print(f"📜 Context/Token limit exceeded: {e}")
                    print("💡 Suggestion: Reduce analysis length or simplify template")
                else:
                    print(f"❌ HTML Report generation failed: {e}")
                raise
            
            # Save report to file
            output_dir = Path("dfir_reports")
            output_dir.mkdir(exist_ok=True)
            
            report_filename = f"dfir_report_{incident_title.replace(' ', '_').lower()}.html"
            report_path = output_dir / report_filename
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_report)
            
            print("\n" + "="*60)
            print("HTML REPORT GENERATED")
            print("="*60)
            print(f"📁 Saved at: {report_path.absolute()}")
            
            return dfir_analysis, html_report


async def main() -> None:
    """Main entry point for the DFIR report generation workflow"""
    
    import sys
    
    print("🚀 DFIR REPORT GENERATOR")
    print("="*50)
    
    # Support non-interactive mode via environment variables or command line args
    if len(sys.argv) > 1:
        # Command line mode
        file_path = sys.argv[1] if len(sys.argv) > 1 else None
        user_prompt = sys.argv[2] if len(sys.argv) > 2 else None
        incident_title = sys.argv[3] if len(sys.argv) > 3 else "DFIR Analysis Report"
    else:
        # Environment variable mode (for Docker)
        file_path = os.getenv("DFIR_FILE_PATH")
        user_prompt = os.getenv("DFIR_USER_PROMPT")
        incident_title = os.getenv("DFIR_INCIDENT_TITLE", "DFIR Analysis Report")
        
        # If still not set, use interactive mode
        if file_path is None and user_prompt is None:
            # Get user input
            user_prompt = input("📝 Enter your DFIR analysis prompt (press Enter for default): ").strip()
            if not user_prompt:
                user_prompt = None  # Will use default prompt
            
            file_path = input("📁 Path to file to analyze (optional, press Enter to skip): ").strip()
            if not file_path:
                file_path = None
            elif not Path(file_path).exists():
                print(f"⚠️  Warning: File {file_path} does not exist. Continuing without file.")
                file_path = None
            
            incident_title = input("📋 Incident title (optional): ").strip()
            if not incident_title:
                incident_title = "DFIR Analysis Report"
    
    # Default file path if none provided
    if file_path is None:
        # Try to find a file in test_data directory
        test_data_dir = Path("test_data")
        if test_data_dir.exists():
            test_files = list(test_data_dir.glob("*.json"))
            if test_files:
                file_path = str(test_files[0])
                print(f"📁 Using test file: {file_path}")
    
    # Run workflow
    manager = DFIRReportManager()
    try:
        dfir_analysis, html_report = await manager.run_complete_workflow(
            user_prompt=user_prompt,
            file_path=file_path,
            incident_title=incident_title
        )
        
        print("\n✅ Workflow completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during workflow: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
