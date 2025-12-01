"""
Flask Web Interface for DFIR Report System
Simple and aesthetic GUI for file upload, analysis execution, and report visualization
"""
import os
import sys
import asyncio
import json
import threading
import multiprocessing
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename
import queue

# Add parent directory to path to import main modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Lazy import - only import when needed to avoid initializing agents on startup
# from main import DFIRReportManager  # Moved to run_analysis_async

app = Flask(__name__, template_folder='templates', static_folder='static')

# Get the app root directory (parent of frontend)
app_root = Path(__file__).parent.parent
app.config['UPLOAD_FOLDER'] = str(app_root / 'test_data')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['SECRET_KEY'] = 'dfir-secret-key-change-in-production'

# Ensure upload directory exists
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)

# Global variables for status tracking
analysis_status = {
    'running': False,
    'progress': '',
    'errors': [],
    'warnings': [],
    'current_step': '',
    'report_path': None
}

# Queue for real-time log messages
log_queue = queue.Queue()

def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'json', 'txt', 'log', 'csv', 'xml'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def run_dfir_analysis_worker(file_path, user_prompt, status_dict, log_queue_dict):
    """Run DFIR analysis only in a separate process (worker function)"""
    import sys
    from pathlib import Path
    import os
    import asyncio
    import json
    from datetime import datetime
    
    # Add parent directory to path
    app_root = Path(__file__).parent.parent
    sys.path.insert(0, str(app_root))
    
    # Ensure required directories exist with proper permissions
    try:
        logs_dir = app_root / 'logs'
        logs_dir.mkdir(exist_ok=True)
        try:
            os.chmod(str(logs_dir), 0o777)
        except (OSError, PermissionError):
            pass
        
        reports_dir = app_root / 'dfir_reports'
        reports_dir.mkdir(exist_ok=True)
        try:
            os.chmod(str(reports_dir), 0o777)
        except (OSError, PermissionError):
            pass
    except Exception as e:
        error_msg = f"Error creating directories: {str(e)}"
        if 'errors' in status_dict:
            status_dict['errors'].append(error_msg)
        status_dict['progress'] = f'Error: {error_msg}'
        status_dict['running'] = False
        return
    
    loop = None
    try:
        status_dict['running'] = True
        if 'errors' in status_dict and hasattr(status_dict['errors'], 'clear'):
            status_dict['errors'][:] = []
        if 'warnings' in status_dict and hasattr(status_dict['warnings'], 'clear'):
            status_dict['warnings'][:] = []
        status_dict['progress'] = 'Starting DFIR analysis...'
        status_dict['current_step'] = 'DFIR Analysis'
        
        # Change to app root directory
        original_cwd = os.getcwd()
        try:
            os.chdir(str(app_root))
        except OSError:
            pass
        
        # Lazy import
        from main import DFIRReportManager
        
        status_dict['progress'] = 'Initializing CAI agents...'
        
        # Create manager
        manager = DFIRReportManager()
        
        # Run in async context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        status_dict['progress'] = 'Running DFIR analysis...'
        status_dict['current_step'] = 'DFIR Analysis'
        
        # Configure analysis timeout
        workflow_timeout = int(os.getenv('CAI_ANALYSIS_TIMEOUT', '3600'))
        print(f"⏱️  DFIR Analysis timeout: {workflow_timeout}s ({workflow_timeout/60:.1f} minutes)")
        
        # Run only DFIR analysis
        dfir_analysis = loop.run_until_complete(
            asyncio.wait_for(
                manager.run_dfir_analysis(user_prompt=user_prompt, file_path=file_path),
                timeout=workflow_timeout
            )
        )
        
        # CRITICAL: The agent should have already saved the JSON file
        # Check if the JSON file exists and is valid - use that instead of final_output
        # (final_output may contain markdown summary that would overwrite the JSON)
        analysis_file = app_root / 'dfir_reports' / 'dfir_analysis.json'
        
        if analysis_file.exists():
            try:
                with open(analysis_file, 'r', encoding='utf-8') as f:
                    saved_json = json.load(f)
                    # Verify it's structured JSON (check for template placeholder fields)
                    if isinstance(saved_json, dict) and ("EXECUTIVE_SUMMARY" in saved_json or "executive_summary" in saved_json):
                        # Structured JSON - just add metadata if not present
                        if 'timestamp' not in saved_json:
                            saved_json['timestamp'] = datetime.now().isoformat()
                        if 'file_path' not in saved_json:
                            saved_json['file_path'] = file_path
                        with open(analysis_file, 'w', encoding='utf-8') as f:
                            json.dump(saved_json, f, indent=2, ensure_ascii=False)
                        print("✅ Using structured JSON from file (agent saved it correctly)")
                    elif isinstance(saved_json, dict) and "analysis" in saved_json:
                        # Old format - keep as is, just add metadata
                        if 'timestamp' not in saved_json:
                            saved_json['timestamp'] = datetime.now().isoformat()
                        if 'file_path' not in saved_json:
                            saved_json['file_path'] = file_path
                        with open(analysis_file, 'w', encoding='utf-8') as f:
                            json.dump(saved_json, f, indent=2, ensure_ascii=False)
                        print("⚠️  Found old format JSON with 'analysis' field")
                    else:
                        # Invalid structure - try to parse final_output
                        raise ValueError("Invalid JSON structure")
            except (json.JSONDecodeError, Exception) as e:
                print(f"⚠️  Error reading saved JSON file: {e}")
                print("   Attempting to parse final_output instead")
                # Fall through to parse final_output
                saved_json = None
        else:
            saved_json = None
        
        # If file doesn't exist or is invalid, try to parse final_output
        if saved_json is None:
            try:
                # Try to parse as JSON first
                parsed_analysis = json.loads(dfir_analysis)
                # If successful, it's already structured JSON - add metadata
                if isinstance(parsed_analysis, dict):
                    parsed_analysis['timestamp'] = datetime.now().isoformat()
                    parsed_analysis['file_path'] = file_path
                    with open(analysis_file, 'w', encoding='utf-8') as f:
                        json.dump(parsed_analysis, f, indent=2, ensure_ascii=False)
                else:
                    # If it's not a dict, wrap it
                    with open(analysis_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'analysis': dfir_analysis,
                            'timestamp': datetime.now().isoformat(),
                            'file_path': file_path
                        }, f, indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                # If not valid JSON, wrap it in the old format (backward compatibility)
                with open(analysis_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'analysis': dfir_analysis,
                        'timestamp': datetime.now().isoformat(),
                        'file_path': file_path
                    }, f, indent=2, ensure_ascii=False)
        
        status_dict['progress'] = 'DFIR analysis completed successfully'
        status_dict['current_step'] = 'DFIR Completed'
        status_dict['dfir_analysis_ready'] = True
        status_dict['running'] = False
        
    except asyncio.TimeoutError as e:
        error_msg = f"Timeout during DFIR analysis: {str(e)}"
        if 'errors' in status_dict:
            status_dict['errors'].append(error_msg)
        if 'warnings' in status_dict:
            status_dict['warnings'].append("DFIR analysis exceeded the time limit.")
        status_dict['progress'] = 'Error: Timeout'
        status_dict['current_step'] = 'Error'
        status_dict['running'] = False
        
    except Exception as e:
        error_msg = f"Error during DFIR analysis: {str(e)}"
        
        if 'errors' in status_dict:
            status_dict['errors'].append(error_msg)
        status_dict['progress'] = f'Error: {str(e)[:100]}'
        status_dict['current_step'] = 'Error'
        status_dict['running'] = False
        
        # Print error for debugging (without full traceback)
        print(f"❌ {error_msg}")
        
        error_str = str(e).lower()
        if 'warnings' in status_dict:
            if 'timeout' in error_str or 'time' in error_str:
                status_dict['warnings'].append("⚠️ Timeout detected during DFIR analysis.")
            elif 'token' in error_str or 'context' in error_str:
                status_dict['warnings'].append("⚠️ Context/token limit exceeded.")
    
    finally:
        if loop:
            loop.close()
        try:
            if 'original_cwd' in locals():
                os.chdir(original_cwd)
        except OSError:
            pass

def run_report_generation_worker(incident_title, status_dict, log_queue_dict):
    """Run HTML report generation only in a separate process (worker function)"""
    import sys
    from pathlib import Path
    import os
    
    # Add parent directory to path
    app_root = Path(__file__).parent.parent
    sys.path.insert(0, str(app_root))
    
    # Ensure required directories exist (including logs/ for CAI tracing)
    try:
        logs_dir = app_root / 'logs'
        logs_dir.mkdir(exist_ok=True)
        try:
            os.chmod(str(logs_dir), 0o777)
        except (OSError, PermissionError):
            pass
        
        reports_dir = app_root / 'dfir_reports'
        reports_dir.mkdir(exist_ok=True)
        try:
            os.chmod(str(reports_dir), 0o777)
        except (OSError, PermissionError):
            pass
    except Exception as e:
        error_msg = f"Error creating directories: {str(e)}"
        if 'errors' in status_dict:
            status_dict['errors'].append(error_msg)
        status_dict['progress'] = f'Error: {error_msg}'
        status_dict['running'] = False
        return
    
    loop = None
    try:
        status_dict['running'] = True
        if 'errors' in status_dict and hasattr(status_dict['errors'], 'clear'):
            status_dict['errors'][:] = []
        if 'warnings' in status_dict and hasattr(status_dict['warnings'], 'clear'):
            status_dict['warnings'][:] = []
        status_dict['progress'] = 'Starting report generation...'
        status_dict['current_step'] = 'Report Generation'
        
        # Check if analysis exists
        analysis_file = app_root / 'dfir_reports' / 'dfir_analysis.json'
        if not analysis_file.exists():
            error_msg = "DFIR analysis not found. Please run the analysis first."
            if 'errors' in status_dict:
                status_dict['errors'].append(error_msg)
            status_dict['progress'] = 'Error: Analysis not found'
            status_dict['current_step'] = 'Error'
            status_dict['running'] = False
            return
        
        # Change to app root directory
        original_cwd = os.getcwd()
        try:
            os.chdir(str(app_root))
        except OSError:
            pass
        
        # CRITICAL: Ensure logs directory exists AFTER changing directory
        # CAI will try to write logs when the process exits (atexit_handler)
        # If logs/ doesn't exist, it will fail with FileNotFoundError
        logs_dir = app_root / 'logs'
        if not logs_dir.exists():
            try:
                logs_dir.mkdir(exist_ok=True)
                os.chmod(str(logs_dir), 0o777)
                print(f"✅ Created logs directory: {logs_dir}")
            except (OSError, PermissionError) as e:
                print(f"⚠️  Warning: Could not create logs directory: {e}")
        else:
            # Ensure it's writable
            try:
                os.chmod(str(logs_dir), 0o777)
            except (OSError, PermissionError):
                pass
        
        # Lazy import
        from main import DFIRReportManager
        
        status_dict['progress'] = 'Initializing reporting agent...'
        
        # Create manager (this will enable tracing, which may create logs)
        # Note: Each process creates its own CAI session, so logs may be separate
        # The logs/ directory must exist before this point to avoid FileNotFoundError
        manager = DFIRReportManager()
        
        # Verify that dfir_analysis.json exists
        if not analysis_file.exists():
            error_msg = f"Analysis file does not exist: {analysis_file}"
            if 'errors' in status_dict:
                status_dict['errors'].append(error_msg)
            status_dict['progress'] = 'Error: Analysis not found'
            status_dict['current_step'] = 'Error'
            status_dict['running'] = False
            return
        
        # Run in async context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        status_dict['progress'] = 'Generating HTML report...'
        status_dict['current_step'] = 'Report Generation'
        
        # Configure report timeout
        report_timeout = int(os.getenv('CAI_REPORT_TIMEOUT', '3600'))
        print(f"⏱️  Report generation timeout: {report_timeout}s ({report_timeout/60:.1f} minutes)")
        
        # Run only report generation
        html_report = loop.run_until_complete(
            asyncio.wait_for(
                manager.generate_report(incident_title=incident_title),
                timeout=report_timeout
            )
        )
        
        # Save report
        report_filename = f"dfir_report_{incident_title.replace(' ', '_').lower()}.html"
        report_path = app_root / 'dfir_reports' / report_filename
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_report)
        
        status_dict['report_path'] = str(report_path)
        status_dict['progress'] = 'HTML report generated successfully'
        status_dict['current_step'] = 'Completed'
        status_dict['running'] = False
        
    except asyncio.TimeoutError as e:
        error_msg = f"Timeout during report generation: {str(e)}"
        if 'errors' in status_dict:
            status_dict['errors'].append(error_msg)
        if 'warnings' in status_dict:
            status_dict['warnings'].append("Report generation exceeded the time limit.")
        status_dict['progress'] = 'Error: Timeout'
        status_dict['current_step'] = 'Error'
        status_dict['running'] = False
        
    except Exception as e:
        error_msg = f"Error during report generation: {str(e)}"
        
        if 'errors' in status_dict:
            status_dict['errors'].append(error_msg)
        status_dict['progress'] = f'Error: {str(e)[:100]}'
        status_dict['current_step'] = 'Error'
        status_dict['running'] = False
        
        # Print error for debugging (without full traceback)
        print(f"❌ {error_msg}")
        
        error_str = str(e).lower()
        if 'warnings' in status_dict:
            if 'timeout' in error_str or 'time' in error_str:
                status_dict['warnings'].append("⚠️ Timeout detected during report generation.")
            elif 'token' in error_str or 'context' in error_str:
                status_dict['warnings'].append("⚠️ Context/token limit exceeded.")
    
    finally:
        if loop:
            loop.close()
        try:
            if 'original_cwd' in locals():
                os.chdir(original_cwd)
        except OSError:
            pass

def run_analysis_worker(file_path, incident_title, user_prompt, status_dict, log_queue_dict):
    """Run analysis in a separate process (worker function)"""
    import sys
    from pathlib import Path
    import os
    
    # Add parent directory to path
    app_root = Path(__file__).parent.parent
    sys.path.insert(0, str(app_root))
    
    # Ensure required directories exist with proper permissions
    try:
        logs_dir = app_root / 'logs'
        logs_dir.mkdir(exist_ok=True)
        # Try to set permissions (may fail in some cases, but try anyway)
        try:
            os.chmod(str(logs_dir), 0o777)
        except (OSError, PermissionError):
            pass  # Ignore if we can't change permissions
        
        reports_dir = app_root / 'dfir_reports'
        reports_dir.mkdir(exist_ok=True)
        try:
            os.chmod(str(reports_dir), 0o777)
        except (OSError, PermissionError):
            pass
    except Exception as e:
        error_msg = f"Error creating directories: {str(e)}"
        if 'errors' in status_dict:
            status_dict['errors'].append(error_msg)
        status_dict['progress'] = f'Error: {error_msg}'
        status_dict['running'] = False
        return
    
    loop = None
    try:
        status_dict['running'] = True
        # Clear previous errors/warnings
        if 'errors' in status_dict and hasattr(status_dict['errors'], 'clear'):
            status_dict['errors'][:] = []
        if 'warnings' in status_dict and hasattr(status_dict['warnings'], 'clear'):
            status_dict['warnings'][:] = []
        status_dict['progress'] = 'Starting analysis...'
        status_dict['current_step'] = 'Initialization'
        
        # Change to app root directory to ensure relative paths work
        original_cwd = os.getcwd()
        try:
            os.chdir(str(app_root))
        except OSError:
            pass  # If we can't change directory, continue anyway
        
        # Lazy import - only import and create manager when analysis is requested
        from main import DFIRReportManager
        
        status_dict['progress'] = 'Initializing CAI agents...'
        
        # Create manager and run workflow (this is when agents are actually created)
        manager = DFIRReportManager()
        
        # Run in async context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        status_dict['progress'] = 'Running DFIR analysis...'
        status_dict['current_step'] = 'DFIR Analysis'
        
        # Configure workflow timeout (very high value to avoid timeouts)
        workflow_timeout = int(os.getenv('CAI_WORKFLOW_TIMEOUT', '7200'))  # 2 horas por defecto
        print(f"⏱️  Workflow timeout: {workflow_timeout}s ({workflow_timeout/60:.1f} minutes)")
        
        dfir_analysis, html_report = loop.run_until_complete(
            asyncio.wait_for(
                manager.run_complete_workflow(
                    user_prompt=user_prompt,
                    file_path=file_path,
                    incident_title=incident_title
                ),
                timeout=workflow_timeout
            )
        )
        
        # Find the generated report
        reports_dir = app_root / 'dfir_reports'
        if reports_dir.exists():
            report_files = sorted(
                reports_dir.glob('dfir_report_*.html'),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            if report_files:
                status_dict['report_path'] = str(report_files[0])
        
        status_dict['progress'] = 'Analysis completed successfully'
        status_dict['current_step'] = 'Completed'
        status_dict['running'] = False
        
    except asyncio.TimeoutError as e:
        error_msg = f"Timeout during analysis: {str(e)}"
        if 'errors' in status_dict:
            status_dict['errors'].append(error_msg)
        if 'warnings' in status_dict:
            status_dict['warnings'].append("Analysis exceeded the time limit. Try with a smaller file or a more specific prompt.")
        status_dict['progress'] = 'Error: Timeout'
        status_dict['current_step'] = 'Error'
        status_dict['running'] = False
        
    except Exception as e:
        error_msg = f"Error during analysis: {str(e)}"
        if 'errors' in status_dict:
            status_dict['errors'].append(error_msg)
        status_dict['progress'] = f'Error: {str(e)[:100]}'
        status_dict['current_step'] = 'Error'
        status_dict['running'] = False
        
        # Check for timeout-related errors
        error_str = str(e).lower()
        if 'warnings' in status_dict:
            if 'timeout' in error_str or 'time' in error_str:
                status_dict['warnings'].append("⚠️ Timeout detected. Possible causes: very long analysis, model context limits, or template complexity.")
            elif 'token' in error_str or 'context' in error_str:
                status_dict['warnings'].append("⚠️ Context/token limit exceeded. Try reducing the analysis length or simplifying the template.")
            elif 'signal' in error_str:
                status_dict['warnings'].append("⚠️ Signal error detected. This may occur if the analysis runs in an incompatible context.")
    
    finally:
        if loop:
            loop.close()
        # Restore original working directory
        try:
            if 'original_cwd' in locals():
                os.chdir(original_cwd)
        except OSError:
            pass

# Global process and manager
analysis_process = None
report_process = None
manager = None
analysis_status_shared = None

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'path': file_path,
            'message': f'File {filename} uploaded successfully'
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/analyze-dfir', methods=['POST'])
def analyze_dfir():
    """Start DFIR analysis only"""
    global analysis_status, analysis_process, manager, analysis_status_shared
    
    try:
        # Check if process is still running
        if analysis_process and analysis_process.is_alive():
            return jsonify({'error': 'DFIR analysis already running'}), 400
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        file_path = data.get('file_path')
        user_prompt = data.get('user_prompt')
        
        if not file_path:
            return jsonify({'error': 'File path not provided'}), 400
            
        if not os.path.exists(file_path):
            return jsonify({'error': f'File not found: {file_path}'}), 400
        
        # Create multiprocessing manager for shared state
        try:
            if manager is None:
                manager = multiprocessing.Manager()
                analysis_status_shared = manager.dict({
                    'running': False,
                    'progress': '',
                    'errors': manager.list(),
                    'warnings': manager.list(),
                    'current_step': '',
                    'report_path': None,
                    'dfir_analysis_ready': False
                })
        except Exception as e:
            return jsonify({'error': f'Failed to create multiprocessing manager: {str(e)}'}), 500
        
        # Reset status
        try:
            analysis_status_shared['running'] = True
            analysis_status_shared['progress'] = 'Starting DFIR analysis...'
            analysis_status_shared['errors'][:] = []
            analysis_status_shared['warnings'][:] = []
            analysis_status_shared['current_step'] = 'DFIR Analysis'
            analysis_status_shared['dfir_analysis_ready'] = False
        except Exception as e:
            return jsonify({'error': f'Failed to reset status: {str(e)}'}), 500
        
        # Update local status
        analysis_status = {
            'running': True,
            'progress': 'Starting DFIR analysis...',
            'errors': [],
            'warnings': [],
            'current_step': 'DFIR Analysis',
            'report_path': None,
            'dfir_analysis_ready': False
        }
        
        log_queue_dict = manager.dict()
        
        # Run DFIR analysis in separate process
        try:
            analysis_process = multiprocessing.Process(
                target=run_dfir_analysis_worker,
                args=(file_path, user_prompt, analysis_status_shared, log_queue_dict)
            )
            analysis_process.daemon = True
            analysis_process.start()
            
            if not analysis_process.is_alive():
                return jsonify({'error': 'Failed to start DFIR analysis process'}), 500
                
        except Exception as e:
            return jsonify({'error': f'Failed to start DFIR analysis process: {str(e)}'}), 500
        
        return jsonify({'success': True, 'message': 'DFIR analysis started'})
        
    except Exception as e:
        error_msg = f'Unexpected error: {str(e)}'
        print(f"❌ Error in analyze-dfir route: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/generate-report', methods=['POST'])
def generate_report():
    """Start HTML report generation only"""
    global analysis_status, report_process, manager, analysis_status_shared
    
    try:
        # Check if process is still running
        if report_process and report_process.is_alive():
            return jsonify({'error': 'Report generation already running'}), 400
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        incident_title = data.get('incident_title', 'DFIR Analysis Report')
        
        # Check if DFIR analysis is ready
        if analysis_status_shared is None:
            analysis_status_shared = manager.dict({
                'dfir_analysis_ready': False
            }) if manager else None
        
        if analysis_status_shared and not analysis_status_shared.get('dfir_analysis_ready', False):
            # Check if analysis file exists
            analysis_file = app_root / 'dfir_reports' / 'dfir_analysis.json'
            if not analysis_file.exists():
                return jsonify({'error': 'DFIR analysis not found. Please run DFIR analysis first.'}), 400
        
        # Create multiprocessing manager if needed
        try:
            if manager is None:
                manager = multiprocessing.Manager()
            
            if analysis_status_shared is None:
                analysis_status_shared = manager.dict({
                    'running': False,
                    'progress': '',
                    'errors': manager.list(),
                    'warnings': manager.list(),
                    'current_step': '',
                    'report_path': None,
                    'dfir_analysis_ready': True
                })
        except Exception as e:
            return jsonify({'error': f'Failed to create multiprocessing manager: {str(e)}'}), 500
        
        # Reset status
        try:
            analysis_status_shared['running'] = True
            analysis_status_shared['progress'] = 'Starting report generation...'
            analysis_status_shared['errors'][:] = []
            analysis_status_shared['warnings'][:] = []
            analysis_status_shared['current_step'] = 'Report Generation'
        except Exception as e:
            return jsonify({'error': f'Failed to reset status: {str(e)}'}), 500
        
        # Update local status
        analysis_status = {
            'running': True,
            'progress': 'Starting report generation...',
            'errors': [],
            'warnings': [],
            'current_step': 'Report Generation',
            'report_path': None
        }
        
        log_queue_dict = manager.dict()
        
        # Run report generation in separate process
        try:
            report_process = multiprocessing.Process(
                target=run_report_generation_worker,
                args=(incident_title, analysis_status_shared, log_queue_dict)
            )
            report_process.daemon = True
            report_process.start()
            
            if not report_process.is_alive():
                return jsonify({'error': 'Failed to start report generation process'}), 500
                
        except Exception as e:
            return jsonify({'error': f'Failed to start report generation process: {str(e)}'}), 500
        
        return jsonify({'success': True, 'message': 'Report generation started'})
        
    except Exception as e:
        error_msg = f'Unexpected error: {str(e)}'
        print(f"❌ Error in generate-report route: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/status')
def status():
    """Get analysis status"""
    global analysis_status, analysis_status_shared, analysis_process, report_process
    
    # Update local status from shared status if available
    if analysis_status_shared is not None:
        # Convert manager dict/list to regular dict/list for JSON serialization
        status_copy = {
            'running': analysis_status_shared.get('running', False),
            'progress': analysis_status_shared.get('progress', ''),
            'errors': list(analysis_status_shared.get('errors', [])),
            'warnings': list(analysis_status_shared.get('warnings', [])),
            'current_step': analysis_status_shared.get('current_step', ''),
            'report_path': analysis_status_shared.get('report_path'),
            'dfir_analysis_ready': analysis_status_shared.get('dfir_analysis_ready', False)
        }
        
        # Check if processes are still alive
        if analysis_process and not analysis_process.is_alive():
            if status_copy['current_step'] == 'DFIR Analysis':
                status_copy['running'] = False
        if report_process and not report_process.is_alive():
            if status_copy['current_step'] == 'Report Generation':
                status_copy['running'] = False
        
        analysis_status = status_copy
    
    return jsonify(analysis_status)

@app.route('/reports')
def list_reports():
    """List available reports"""
    reports_dir = app_root / 'dfir_reports'
    reports = []
    
    if reports_dir.exists():
        for report_file in sorted(
            reports_dir.glob('*.html'),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        ):
            reports.append({
                'name': report_file.name,
                'path': str(report_file),
                'size': report_file.stat().st_size,
                'modified': datetime.fromtimestamp(report_file.stat().st_mtime).isoformat()
            })
    
    return jsonify(reports)

@app.route('/report/<path:filename>')
def view_report(filename):
    """View generated report"""
    report_path = app_root / 'dfir_reports' / filename
    if report_path.exists() and report_path.suffix == '.html':
        return send_file(str(report_path), mimetype='text/html')
    return jsonify({'error': 'Report not found'}), 404

@app.route('/logs')
def get_logs():
    """Get recent log messages"""
    logs = []
    while not log_queue.empty():
        try:
            logs.append(log_queue.get_nowait())
        except queue.Empty:
            break
    return jsonify(logs)

# Set multiprocessing start method (required for some systems)
if __name__ == '__main__':
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        # Start method already set, ignore
        pass
    import os
    import subprocess
    import socket
    
    # Puerto fijo - siempre usar 5000 (mapeado en docker-compose)
    port = int(os.getenv('FLASK_PORT', '5000'))
    
    def is_port_in_use(port):
        """Check if a port is in use"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('0.0.0.0', port)) == 0
    
    def kill_process_using_port(port):
        """Kill the process using the specified port"""
        import os
        import signal
        
        # Method 1: Try using /proc/net/tcp to find PID
        try:
            with open('/proc/net/tcp', 'r') as f:
                lines = f.readlines()[1:]  # Skip header
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        local_addr = parts[1]
                        # Format: 0100007F:1388 (hex IP:hex port)
                        if ':' in local_addr:
                            hex_port = local_addr.split(':')[1]
                            if int(hex_port, 16) == port:
                                # Get inode
                                inode = parts[9] if len(parts) > 9 else None
                                if inode:
                                    # Find process using this inode
                                    for pid_dir in os.listdir('/proc'):
                                        if pid_dir.isdigit():
                                            try:
                                                fd_dir = f'/proc/{pid_dir}/fd'
                                                if os.path.isdir(fd_dir):
                                                    for fd in os.listdir(fd_dir):
                                                        fd_path = os.path.join(fd_dir, fd)
                                                        try:
                                                            if os.readlink(fd_path).endswith(f':{inode}'):
                                                                pid = int(pid_dir)
                                                                print(f"🔍 Process found on port {port}: PID {pid}")
                                                                os.kill(pid, signal.SIGKILL)
                                                                print(f"✅ Process {pid} terminated")
                                                                return True
                                                        except (OSError, ValueError):
                                                            continue
                                            except (OSError, PermissionError):
                                                continue
        except (FileNotFoundError, OSError, ValueError):
            pass
        
        # Method 2: Kill all python processes running app.py (simpler fallback)
        try:
            # Use os.walk to find processes
            for pid_dir in os.listdir('/proc'):
                if pid_dir.isdigit():
                    try:
                        cmdline_path = f'/proc/{pid_dir}/cmdline'
                        if os.path.exists(cmdline_path):
                            with open(cmdline_path, 'r') as f:
                                cmdline = f.read()
                                if 'python' in cmdline and 'app.py' in cmdline:
                                    pid = int(pid_dir)
                                    print(f"🔍 Flask process found: PID {pid}")
                                    os.kill(pid, signal.SIGKILL)
                                    print(f"✅ Flask process {pid} terminated")
                                    return True
                    except (OSError, PermissionError, ValueError):
                        continue
        except (OSError, PermissionError):
            pass
        
        # Method 3: Try common tools if available
        for tool, args in [
            (['lsof', '-ti', f':{port}'], ['kill', '-9']),
            (['fuser', f'{port}/tcp'], ['fuser', '-k', f'{port}/tcp']),
        ]:
            try:
                result = subprocess.run(tool, capture_output=True, text=True, timeout=3)
                if result.returncode == 0 and result.stdout.strip():
                    if 'lsof' in tool[0]:
                        pids = result.stdout.strip().split('\n')
                        for pid in pids:
                            if pid:
                                subprocess.run(['kill', '-9', pid], timeout=3)
                                print(f"✅ Process {pid} terminated")
                    else:
                        subprocess.run(args, timeout=3)
                        print(f"✅ Port {port} freed")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
                continue
        
        return False
    
    # Check if port is in use and free it if needed
    max_attempts = 3
    for attempt in range(max_attempts):
        if is_port_in_use(port):
            if attempt == 0:
                print(f"⚠️  Port {port} is in use. Freeing...")
            else:
                print(f"⚠️  Port {port} is still in use. Retrying ({attempt + 1}/{max_attempts})...")
            
            if kill_process_using_port(port):
                import time
                # Wait progressively longer for port to be released
                wait_time = 1 + (attempt * 0.5)
                time.sleep(wait_time)
                
                # Verify port is actually free
                if not is_port_in_use(port):
                    print(f"✅ Port {port} freed successfully")
                    break
                else:
                    print(f"⏳ Waiting for port {port} to be released...")
            else:
                if attempt == max_attempts - 1:
                    print(f"❌ Could not free port {port} after {max_attempts} attempts")
                    print(f"💡 Try manually: docker exec cai-dfir-container pkill -9 -f 'python.*app.py'")
                    import sys
                    sys.exit(1)
        else:
            break
    
    print(f"🌐 Starting Flask on http://0.0.0.0:{port}")
    print(f"📡 Access from host: http://localhost:{port}")
    print(f"🌍 Access from network: http://172.16.100.5:{port}")
    print(f"💡 CAI agents will only initialize when you click 'Start Analysis'")
    
    # Debug mode disabled to avoid auto-reloads that might trigger imports
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
