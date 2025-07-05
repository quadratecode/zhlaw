"""
Editor Interface Module

Handles integration with the modified table_editor for manual review.
"""

import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import threading
import webbrowser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging


class TableEditorInterface:
    """Interface for launching and managing the table editor."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.editor_path = Path(__file__).parent
        self.force_simulation = False
        
    def launch_editor_for_law_with_progression(self, law_id: str, unique_tables: Dict[str, Any], 
                                              base_path: str = None, progression_info: Dict[str, Any] = None,
                                              review_mode: str = 'folder') -> Dict[str, Any]:
        """
        Launch table editor with auto-progression support for folder review.
        
        Args:
            law_id: The law identifier
            unique_tables: Dictionary of unique tables for the law
            base_path: Base path to the law files
            progression_info: Info about next law and progression state
            review_mode: 'single' or 'folder' to indicate review mode
            
        Returns:
            Dictionary of corrections from the editor
        """
        # Add progression info to the data
        if not unique_tables:
            self.logger.warning(f"No tables to review for law {law_id}")
            return {}
            
        # Prepare data file for table_editor
        # Extract folder name from progression_info or base_path
        folder_name = "zhlex_files_test"  # default
        if progression_info and 'folder_name' in progression_info:
            folder_name = progression_info['folder_name']
        elif base_path:
            # Extract folder name from base_path (e.g., "data/zhlex/zhlex_files_test" -> "zhlex_files_test")
            folder_name = Path(base_path).name
        
        editor_data = self.prepare_editor_data(law_id, unique_tables, review_mode, base_path, folder_name)
        
        # Add progression info if provided
        if progression_info:
            editor_data['progression'] = progression_info
        
        # Create temporary data file and launch
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            json.dump(editor_data, tmp_file, indent=2, ensure_ascii=False)
            data_file = tmp_file.name
        
        try:
            # Launch table_editor
            self.logger.info(f"Launching table editor for law {law_id} with {len(unique_tables)} tables (folder mode)")
            corrections = self._launch_editor(data_file, law_id, base_path)
            
            return corrections
            
        except Exception as e:
            self.logger.error(f"Error launching table editor for law {law_id}: {e}")
            return {}
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(data_file)
            except Exception as e:
                self.logger.warning(f"Could not delete temporary file {data_file}: {e}")
    
    def launch_editor_for_law(self, law_id: str, unique_tables: Dict[str, Any], base_path: str = None, review_mode: str = 'single') -> Dict[str, Any]:
        """
        Launch modified table_editor with law's unique tables.
        
        Args:
            law_id: The law identifier
            unique_tables: Dictionary of unique tables for the law
            base_path: Base path to the law files (e.g., "data/zhlex/zhlex_files_test")
            review_mode: 'single' or 'folder' to indicate review mode
            
        Returns:
            Dictionary of corrections from the editor
        """
        if not unique_tables:
            self.logger.warning(f"No tables to review for law {law_id}")
            return {}
            
        # Prepare data file for table_editor
        # Extract folder name from base_path
        folder_name = "zhlex_files_test"  # default
        if base_path:
            folder_name = Path(base_path).name
        
        editor_data = self.prepare_editor_data(law_id, unique_tables, review_mode, base_path, folder_name)
        
        # Create temporary data file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            json.dump(editor_data, tmp_file, indent=2, ensure_ascii=False)
            data_file = tmp_file.name
        
        try:
            # Launch table_editor
            self.logger.info(f"Launching table editor for law {law_id} with {len(unique_tables)} tables")
            corrections = self._launch_editor(data_file, law_id, base_path)
            
            return corrections
            
        except Exception as e:
            self.logger.error(f"Error launching table editor for law {law_id}: {e}")
            return {}
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(data_file)
            except Exception as e:
                self.logger.warning(f"Could not delete temporary file {data_file}: {e}")
    
    def prepare_editor_data(self, law_id: str, unique_tables: Dict[str, Any], review_mode: str = 'single', 
                           base_path: str = None, folder_name: str = "zhlex_files_test") -> Dict[str, Any]:
        """
        Prepare data structure for table_editor.
        
        Args:
            law_id: The law identifier
            unique_tables: Dictionary of unique tables
            review_mode: 'single' or 'folder' to indicate review mode
            base_path: Base path to the law files
            folder_name: Name of the folder for corrections
            
        Returns:
            Data structure for the table editor
        """
        from src.modules.manual_review_module.correction_manager import CorrectionManager
        
        # Load existing corrections if they exist
        # CorrectionManager expects just the base data path, not including the folder
        if base_path and base_path.endswith(folder_name):
            # If base_path includes the folder name, remove it
            correction_base_path = base_path.rsplit('/' + folder_name, 1)[0]
        else:
            correction_base_path = base_path or "data/zhlex"
        
        correction_manager = CorrectionManager(correction_base_path)
        existing_corrections = correction_manager.get_corrections(law_id, folder_name)
        existing_tables = existing_corrections.get('tables', {}) if existing_corrections else {}
        
        
        tables_list = []
        reviewed_tables = []
        
        # Check if this is a specific law review (allow re-review) vs folder review (incremental)
        allow_re_review = review_mode == 'single'
        
        for table_hash, table_data in unique_tables.items():
            # Check if this table has already been reviewed
            existing_review = existing_tables.get(table_hash, {})
            existing_status = existing_review.get('status', 'undefined')
            
            # Define completed statuses that should not be re-reviewed in incremental mode
            completed_statuses = [
                'confirmed_without_changes', 
                'confirmed_with_changes', 
                'rejected'
            ]
            
            # Check if status is a merge status
            is_merged = existing_status.startswith('merged')
            
            # Determine if this table should be included for review
            should_review = False
            
            if allow_re_review:
                # Single law review mode: show all tables (allows re-review)
                should_review = True
            else:
                # Folder/incremental review mode: only show unreviewed tables
                if existing_status == 'undefined' or existing_status not in completed_statuses and not is_merged:
                    should_review = True
            
            if should_review:
                # Determine the correct status and operation for the editor
                if not existing_review or existing_status == 'undefined':
                    # New or undefined table
                    status = 'pending'
                    operation = 'confirm'
                else:
                    # Table has some existing review - load the existing state
                    status = existing_status
                    if existing_status == 'confirmed_without_changes':
                        operation = 'confirm'
                    elif existing_status == 'confirmed_with_changes':
                        operation = 'edit'
                    elif existing_status == 'rejected':
                        operation = 'reject'
                    elif is_merged:
                        operation = 'merge'
                    else:
                        operation = 'confirm'  # fallback
                
                table_entry = {
                    'hash': table_hash,
                    'found_in_versions': table_data['found_in_versions'],
                    'pages': table_data['pages'],
                    'pdf_paths': table_data['pdf_paths'],
                    'source_links': table_data.get('source_links', {}),
                    'structure': table_data['original_structure'],
                    'status': status,
                    'operation': operation
                }
                
                # Include corrected structure if it exists
                if existing_review.get('corrected_structure'):
                    table_entry['corrected_structure'] = existing_review['corrected_structure']
                
                tables_list.append(table_entry)
            else:
                # Track reviewed tables that are not shown
                reviewed_tables.append({
                    'hash': table_hash,
                    'status': existing_status,
                    'found_in_versions': table_data['found_in_versions']
                })
        
        editor_data = {
            'law_id': law_id,
            'review_mode': review_mode,
            'tables': tables_list,
            'metadata': {
                'total_tables': len(unique_tables),
                'tables_to_review': len(tables_list),
                'already_reviewed': len(reviewed_tables),
                'created_at': json.dumps(None),  # Will be set by editor
                'version': '2.0'  # Updated version to indicate new features
            }
        }
        
        # Include existing corrections if they exist
        if existing_tables:
            editor_data['existing_corrections'] = existing_tables
            if allow_re_review:
                self.logger.info(f"Loading {len(existing_tables)} existing corrections for law {law_id} (re-review mode)")
            else:
                self.logger.info(f"Found {len(existing_tables)} existing corrections for law {law_id}, showing {len(tables_list)} tables for review")
        
        # Include information about already reviewed tables
        if reviewed_tables:
            editor_data['already_reviewed_tables'] = reviewed_tables
            self.logger.info(f"Skipping {len(reviewed_tables)} already reviewed tables for law {law_id}")
        
        return editor_data
    
    def _launch_editor(self, data_file: str, law_id: str, base_path: str = None) -> Dict[str, Any]:
        """
        Launch the table editor subprocess.
        
        Args:
            data_file: Path to the temporary data file
            law_id: The law identifier
            base_path: Base path to the law files
            
        Returns:
            Dictionary of corrections
        """
        # Check if the editor directory exists
        if not self.editor_path.exists():
            raise Exception(f"Editor directory not found at {self.editor_path}")
        
        # Check if custom_table_review.html exists
        custom_review_html = self.editor_path / "custom_table_review.html"
        if not custom_review_html.exists():
            raise Exception(f"Custom table review HTML not found at {custom_review_html}")
        
        # Check if simulation is forced
        if self.force_simulation:
            self.logger.info("Using simulation mode (forced)")
            corrections = self._simulate_editor_response(data_file, law_id)
            return corrections
        
        try:
            # Try to launch the actual editor
            corrections = self._launch_real_editor(data_file, law_id, custom_review_html, base_path)
            return corrections
        except Exception as e:
            self.logger.warning(f"Could not launch real editor: {e}")
            self.logger.info("Falling back to simulation mode")
            
            # Fallback to simulation
            corrections = self._simulate_editor_response(data_file, law_id)
            return corrections
    
    def _simulate_editor_response(self, data_file: str, law_id: str) -> Dict[str, Any]:
        """
        Simulate editor response for testing purposes.
        
        Args:
            data_file: Path to the data file
            law_id: The law identifier
            
        Returns:
            Simulated corrections
        """
        # Read the original data
        with open(data_file, 'r', encoding='utf-8') as f:
            editor_data = json.load(f)
        
        # Simulate user corrections
        corrections = {}
        
        for table in editor_data['tables']:
            table_hash = table['hash']
            
            # Simulate different correction actions
            if len(table['structure']) > 0:
                # Simulate confirming most tables
                corrections[table_hash] = {
                    'hash': table_hash,
                    'status': 'confirmed',
                    'found_in_versions': table['found_in_versions'],
                    'pages': table['pages'],
                    'pdf_paths': table['pdf_paths'],
                    'original_structure': table['structure'],
                    'corrected_structure': table['structure']  # No changes
                }
            else:
                # Simulate rejecting empty tables
                corrections[table_hash] = {
                    'hash': table_hash,
                    'status': 'rejected',
                    'found_in_versions': table['found_in_versions'],
                    'pages': table['pages'],
                    'reason': 'Empty table structure'
                }
        
        self.logger.info(f"Simulated {len(corrections)} corrections for law {law_id}")
        return corrections
    
    def _launch_real_editor(self, data_file: str, law_id: str, custom_review_html: Path, base_path: str = None) -> Dict[str, Any]:
        """
        Launch the real table editor interface.
        
        Args:
            data_file: Path to the temporary data file
            law_id: The law identifier
            custom_review_html: Path to the custom review HTML file
            base_path: Base path to the law files
            
        Returns:
            Dictionary of corrections from user input
        """
        import webbrowser
        import urllib.parse
        import time
        from http.server import HTTPServer, SimpleHTTPRequestHandler
        import threading
        import os
        
        # Read the data to pass to the editor
        with open(data_file, 'r', encoding='utf-8') as f:
            editor_data = json.load(f)
        
        # Create a simple HTTP server to serve the editor
        editor_dir = self.editor_path
        
        # Determine results file path
        if base_path:
            # Save in data folder at law level
            results_path = Path(base_path) / law_id
            results_path.mkdir(parents=True, exist_ok=True)
            results_file = results_path / f"{law_id}-corrections.json"
        else:
            # Fallback to editor path
            results_file = self.editor_path / f"{law_id}-results.json"
        
        # Remove any existing results file
        if results_file.exists():
            results_file.unlink()
        
        # Create a custom handler that serves the editor with data
        class EditorHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(editor_dir), **kwargs)
            
            def do_GET(self):
                if self.path == '/data.json':
                    # Serve the law data
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps(editor_data).encode('utf-8'))
                    return
                elif self.path == '/save-corrections':
                    # Handle POST request to save corrections
                    return
                else:
                    super().do_GET()
            
            def do_POST(self):
                if self.path == '/save-corrections':
                    # Read the request data
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    
                    try:
                        request_data = json.loads(post_data.decode('utf-8'))
                        
                        # Extract corrections and action
                        corrections = request_data.get('corrections', {})
                        action = request_data.get('action', 'complete')
                        law_id = request_data.get('law_id', '')
                        
                        # Prepare response data
                        response_data = {
                            "status": "success",
                            "action": action,
                            "law_id": law_id
                        }
                        
                        # Save corrections to file with action info (but don't save corrections if cancelled)
                        result_data = {
                            'action': action,
                            'law_id': law_id,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        if action != 'cancel':
                            # Only save corrections if not cancelled
                            result_data['corrections'] = corrections
                        else:
                            # For cancel action, indicate no corrections saved
                            result_data['corrections'] = {}
                            result_data['cancelled'] = True
                        
                        with open(results_file, 'w', encoding='utf-8') as f:
                            json.dump(result_data, f, indent=2)
                        
                        # Signal that review is complete and action should be taken
                        if action in ['next', 'quit', 'cancel', 'cancel_next', 'cancel_quit']:
                            # This will signal the server to stop and take action
                            response_data["review_complete"] = True
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps(response_data).encode('utf-8'))
                        
                        # If action requires server shutdown, shut down the server after response
                        if action in ['next', 'quit', 'cancel', 'cancel_next', 'cancel_quit']:
                            # Give client time to receive response before shutting down
                            def delayed_shutdown():
                                time.sleep(1)
                                self.server.shutdown()
                            
                            shutdown_thread = threading.Thread(target=delayed_shutdown)
                            shutdown_thread.daemon = True
                            shutdown_thread.start()
                        
                    except Exception as e:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                else:
                    self.send_response(404)
                    self.end_headers()
        
        # Start the HTTP server with dynamic port
        port = 8765
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                server = HTTPServer(('localhost', port), EditorHandler)
                break
            except OSError as e:
                if e.errno == 98:  # Address already in use
                    port += 1
                    if attempt == max_attempts - 1:
                        raise Exception(f"Could not find available port after {max_attempts} attempts")
                else:
                    raise
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        try:
            # Open the browser with the editor
            editor_url = f"http://localhost:{port}/custom_table_review.html"
            self.logger.info(f"Opening browser with editor: {editor_url}")
            
            # Try to open browser with WSL support
            try:
                browser_opened = self._open_browser_wsl_aware(editor_url)
                if browser_opened:
                    self.logger.info("Browser opened successfully")
                else:
                    raise Exception("No suitable browser opening method found")
            except Exception as e:
                self.logger.warning(f"Could not open browser automatically: {e}")
                print(f"\nPlease open the following URL in your browser:")
                print(f"{editor_url}")
            
            # Wait for user to complete the review
            print(f"\n🔧 Table Editor for Law {law_id}")
            print("=" * 50)
            print(f"Editor URL: {editor_url}")
            print(f"Tables to review: {len(editor_data.get('tables', []))}")
            print("\nInstructions:")
            print("1. Review each table in the browser")
            print("2. Choose operations: Confirm, Reject, Edit, or Merge")
            print("3. Click 'Save Corrections' when done")
            print("4. Return here and press Enter to continue")
            
            # For folder mode with auto-progression, we wait for the server to shut down
            # instead of waiting for user input
            if editor_data.get('review_mode') == 'folder':
                print("\nReview in progress. The browser will automatically handle progression.")
                # Wait for server to shut down (which happens when review is complete)
                server_thread.join()
            else:
                # Original behavior for single law review
                input("\nPress Enter when you have completed the review and saved corrections...")
            
            # Check if results file was created
            max_wait_time = 10  # seconds
            wait_interval = 0.5
            waited_time = 0
            
            # For folder mode, results should already exist
            if editor_data.get('review_mode') != 'folder':
                while not results_file.exists() and waited_time < max_wait_time:
                    time.sleep(wait_interval)
                    waited_time += wait_interval
            
            if results_file.exists():
                # Read the results
                with open(results_file, 'r', encoding='utf-8') as f:
                    result_data = json.load(f)
                
                # Clean up results file
                results_file.unlink()
                
                # Extract corrections from the new format
                if 'corrections' in result_data:
                    corrections = result_data['corrections']
                    action = result_data.get('action', 'complete')
                    self.logger.info(f"Received {len(corrections)} corrections from editor with action: {action}")
                    # Return the full result with action
                    return {
                        'corrections': corrections,
                        'action': action
                    }
                else:
                    # Legacy format fallback
                    corrections = result_data
                    self.logger.info(f"Received {len(corrections)} corrections from editor (legacy format)")
                    return corrections
            else:
                self.logger.warning("No corrections file found, using empty corrections")
                return {}
        
        finally:
            # Stop the server
            server.shutdown()
            server.server_close()
    
    def _create_editor_with_data_url(self, custom_review_html: Path, editor_data: Dict[str, Any]) -> str:
        """
        Create a data URL for the editor with embedded data.
        
        Args:
            custom_review_html: Path to the HTML file
            editor_data: Data to embed
            
        Returns:
            Data URL with embedded data
        """
        import base64
        
        # Read the HTML file
        with open(custom_review_html, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Inject the data into the HTML
        data_script = f"""
        <script>
        window.lawReviewData = {json.dumps(editor_data)};
        </script>
        """
        
        # Insert before closing head tag
        html_content = html_content.replace('</head>', data_script + '</head>')
        
        # Create data URL
        encoded_html = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
        return f"data:text/html;base64,{encoded_html}"
    
    def _open_browser_wsl_aware(self, url: str) -> bool:
        """
        Open browser with WSL awareness - tries to open in Windows browser if running in WSL.
        
        Args:
            url: URL to open
            
        Returns:
            True if browser was opened successfully, False otherwise
        """
        # Check if we're running in WSL
        try:
            with open('/proc/version', 'r') as f:
                proc_version = f.read().lower()
                is_wsl = 'microsoft' in proc_version or 'wsl' in proc_version
        except:
            is_wsl = False
        
        if is_wsl:
            self.logger.info("Detected WSL environment, attempting to open Windows browser")
            
            # Try different methods to open browser in Windows from WSL
            methods = [
                # Method 1: Use cmd.exe to start the default browser
                ['cmd.exe', '/c', 'start', url],
                # Method 2: Use powershell to start
                ['powershell.exe', '-Command', f'Start-Process "{url}"'],
                # Method 3: Try wslview if available
                ['wslview', url],
                # Method 4: Try explorer.exe
                ['explorer.exe', url]
            ]
            
            for method in methods:
                try:
                    self.logger.info(f"Trying method: {' '.join(method)}")
                    result = subprocess.run(method, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        self.logger.info(f"Successfully opened browser using: {method[0]}")
                        return True
                    else:
                        self.logger.debug(f"Method {method[0]} failed with return code {result.returncode}")
                except subprocess.TimeoutExpired:
                    self.logger.debug(f"Method {method[0]} timed out")
                except FileNotFoundError:
                    self.logger.debug(f"Method {method[0]} not found")
                except Exception as e:
                    self.logger.debug(f"Method {method[0]} failed: {e}")
            
            # If all WSL methods failed, fall back to regular webbrowser
            self.logger.warning("All WSL browser methods failed, falling back to regular webbrowser")
        
        # Regular method (non-WSL or WSL fallback)
        try:
            webbrowser.open(url)
            return True
        except Exception as e:
            self.logger.error(f"Regular webbrowser.open failed: {e}")
            return False
    
    def check_editor_availability(self) -> bool:
        """
        Check if the table editor is available and ready to use.
        
        Returns:
            True if editor is available, False otherwise
        """
        try:
            # Check Node.js
            result = subprocess.run(['node', '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error("Node.js is not available")
                return False
            
            # Check editor directory
            if not self.editor_path.exists():
                self.logger.error(f"Table editor not found at {self.editor_path}")
                return False
            
            # Check for required editor files
            required_files = ['index.html', 'package.json']
            for file_name in required_files:
                file_path = self.editor_path / file_name
                if not file_path.exists():
                    self.logger.error(f"Required editor file not found: {file_path}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking editor availability: {e}")
            return False
    
    def get_editor_info(self) -> Dict[str, Any]:
        """
        Get information about the table editor.
        
        Returns:
            Dictionary with editor information
        """
        info = {
            'editor_path': str(self.editor_path),
            'available': self.check_editor_availability(),
            'version': None,
            'features': [
                'Table structure editing',
                'Confirm/Reject/Merge operations',
                'PDF context display',
                'Version tracking'
            ]
        }
        
        # Try to get version from package.json
        try:
            package_json = self.editor_path / 'package.json'
            if package_json.exists():
                with open(package_json, 'r', encoding='utf-8') as f:
                    package_data = json.load(f)
                    info['version'] = package_data.get('version', 'unknown')
        except Exception as e:
            self.logger.warning(f"Could not read editor version: {e}")
        
        return info
    
    def parse_editor_results(self, results_file: str) -> Dict[str, Any]:
        """
        Parse results from the table editor.
        
        Args:
            results_file: Path to the results file
            
        Returns:
            Dictionary of parsed corrections
        """
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            # Parse and validate the results
            corrections = {}
            
            for table_hash, correction_data in results.items():
                if isinstance(correction_data, dict) and 'status' in correction_data:
                    corrections[table_hash] = correction_data
                else:
                    self.logger.warning(f"Invalid correction data for table {table_hash}")
            
            return corrections
            
        except Exception as e:
            self.logger.error(f"Error parsing editor results: {e}")
            return {}