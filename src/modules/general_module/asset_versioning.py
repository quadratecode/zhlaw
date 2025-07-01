"""
Asset versioning system for zhlaw static site generator.
Generates versioned filenames and manages cache headers.
"""

import hashlib
import os
import json
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

from src.utils.logging_utils import get_module_logger
logger = get_module_logger(__name__)

class AssetVersionManager:
    """Manages versioned assets for optimal caching."""
    
    def __init__(self, source_dir: str, output_dir: str, minify_assets: bool = True):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.minify_assets = minify_assets
        self.version_map = {}
        self.version_file = self.output_dir / 'asset-versions.json'
        
    def generate_file_hash(self, file_path: Path) -> str:
        """Generate MD5 hash of file content for versioning."""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()[:8]  # Use first 8 characters
    
    def generate_content_hash(self, content: str) -> str:
        """Generate MD5 hash of string content for versioning."""
        hasher = hashlib.md5()
        hasher.update(content.encode('utf-8'))
        return hasher.hexdigest()[:8]  # Use first 8 characters
    
    def get_versioned_filename(self, original_path: str, file_hash: str) -> str:
        """Generate versioned filename (e.g., styles.css -> styles.v12345678.css)."""
        path = Path(original_path)
        name = path.stem
        suffix = path.suffix
        return f"{name}.v{file_hash}{suffix}"
    
    def process_versionable_assets(self) -> Dict[str, str]:
        """
        Process CSS and JS files, creating versioned copies.
        Returns mapping of original filename -> versioned filename.
        Fixed: Calculate hashes from processed content (after import resolution).
        """
        versionable_patterns = ['*.css', '*.js']
        
        # Step 1: Create initial version map for files without @import dependencies
        initial_version_map = {}
        processed_content = {}
        
        # First, handle JS files and CSS files without imports (leaf nodes)
        for pattern in versionable_patterns:
            for file_path in self.source_dir.rglob(pattern):
                if file_path.is_file():
                    relative_path = file_path.relative_to(self.source_dir)
                    original_name = str(relative_path)
                    
                    if file_path.suffix == '.js':
                        # JS files don't have imports, process directly
                        file_hash = self.generate_file_hash(file_path)
                        versioned_name = self.get_versioned_filename(relative_path.name, file_hash)
                        versioned_path = str(relative_path.parent / versioned_name)
                        initial_version_map[original_name] = versioned_path
                    else:
                        # CSS files - check if they have @import statements
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        import_pattern = r"@import\s+(?:url\()?['\"]([^'\"]+\.css)['\"](?:\))?"
                        imports = re.findall(import_pattern, content)
                        
                        if not imports:
                            # No imports, process directly
                            file_hash = self.generate_file_hash(file_path)
                            versioned_name = self.get_versioned_filename(relative_path.name, file_hash)
                            versioned_path = str(relative_path.parent / versioned_name)
                            initial_version_map[original_name] = versioned_path
                            processed_content[original_name] = content
        
        # Step 2: Iteratively process CSS files with imports
        max_iterations = 10  # Prevent infinite loops
        for iteration in range(max_iterations):
            progress_made = False
            
            for pattern in ['*.css']:  # Only CSS files have imports
                for file_path in self.source_dir.rglob(pattern):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(self.source_dir)
                        original_name = str(relative_path)
                        
                        # Skip if already processed
                        if original_name in initial_version_map:
                            continue
                        
                        # Try to process imports with current version map
                        try:
                            content = self.update_css_imports(file_path, initial_version_map)
                            
                            # Calculate hash from processed content
                            content_hash = self.generate_content_hash(content)
                            versioned_name = self.get_versioned_filename(relative_path.name, content_hash)
                            versioned_path = str(relative_path.parent / versioned_name)
                            
                            initial_version_map[original_name] = versioned_path
                            processed_content[original_name] = content
                            progress_made = True
                            
                        except Exception as e:
                            # Dependencies not ready yet, try next iteration
                            continue
            
            # If no progress made, we're done or have circular dependencies
            if not progress_made:
                break
        
        # Step 3: Handle any remaining files (fallback to source hash)
        for pattern in versionable_patterns:
            for file_path in self.source_dir.rglob(pattern):
                if file_path.is_file():
                    relative_path = file_path.relative_to(self.source_dir)
                    original_name = str(relative_path)
                    
                    if original_name not in initial_version_map:
                        logger.warning(f"Could not resolve imports for {original_name}, using source hash")
                        file_hash = self.generate_file_hash(file_path)
                        versioned_name = self.get_versioned_filename(relative_path.name, file_hash)
                        versioned_path = str(relative_path.parent / versioned_name)
                        initial_version_map[original_name] = versioned_path
                        
                        # Store original content for CSS files
                        if file_path.suffix == '.css':
                            with open(file_path, 'r', encoding='utf-8') as f:
                                processed_content[original_name] = f.read()
        
        # Step 4: Create versioned files
        for pattern in versionable_patterns:
            for file_path in self.source_dir.rglob(pattern):
                if file_path.is_file():
                    relative_path = file_path.relative_to(self.source_dir)
                    original_name = str(relative_path)
                    versioned_path = initial_version_map[original_name]
                    versioned_name = Path(versioned_path).name
                    
                    # Create versioned file in output directory
                    output_file = self.output_dir / relative_path.parent / versioned_name
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Write processed content with optional minification
                    if file_path.suffix == '.css' and original_name in processed_content:
                        content = processed_content[original_name]
                        if self.minify_assets:
                            from src.utils.minification_utils import minify_css_content
                            content = minify_css_content(content)
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(content)
                    elif file_path.suffix == '.js':
                        # Handle JS files with optional minification
                        if self.minify_assets:
                            from src.utils.minification_utils import minify_js_content
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    js_content = f.read()
                                minified_content = minify_js_content(js_content, fallback_on_error=True)
                                with open(output_file, 'w', encoding='utf-8') as f:
                                    f.write(minified_content)
                            except Exception as e:
                                logger.warning(f"JS minification failed for {file_path}: {type(e).__name__}: {e}, copying original")
                                shutil.copy2(file_path, output_file)
                        else:
                            # Just copy as-is if not minifying
                            shutil.copy2(file_path, output_file)
                    else:
                        # Other file types, copy as-is
                        shutil.copy2(file_path, output_file)
                    
                    logger.info(f"Versioned asset: {original_name} -> {versioned_path}")
        
        self.version_map = initial_version_map
        return initial_version_map
    
    def update_css_imports(self, file_path: Path, version_map: Dict[str, str]) -> str:
        """
        Update @import statements in CSS files to use versioned URLs.
        Raises an exception if any import cannot be resolved (for iterative processing).
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match @import statements
        # Matches: @import url('path/to/file.css'); or @import 'path/to/file.css';
        import_pattern = r"@import\s+(?:url\()?['\"]([^'\"]+\.css)['\"](?:\))?"
        
        missing_imports = []
        
        def replace_import(match):
            original_path = match.group(1)
            
            # Convert relative path to match our version map format
            # Remove leading './' if present
            clean_path = original_path.lstrip('./')
            
            # Check if we have a versioned version
            if clean_path in version_map:
                versioned_path = version_map[clean_path]
                # Preserve the original import format but update the path
                if 'url(' in match.group(0):
                    return f"@import url('{versioned_path}')"
                else:
                    return f"@import '{versioned_path}'"
            else:
                # Track missing imports for error reporting
                missing_imports.append(clean_path)
                return match.group(0)  # Keep original for now
        
        # Replace all @import statements
        updated_content = re.sub(import_pattern, replace_import, content)
        
        # If any imports are missing, raise an exception for iterative processing
        if missing_imports:
            raise ValueError(f"Missing imports in {file_path}: {missing_imports}")
        
        return updated_content
    
    def process_non_versionable_assets(self) -> List[str]:
        """
        Copy non-versionable assets (images, fonts, etc.) without versioning.
        Returns list of non-versionable asset paths.
        """
        non_versionable = []
        skip_patterns = ['*.css', '*.js', '*.html']  # Already handled elsewhere
        
        for file_path in self.source_dir.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(self.source_dir)
                
                # Skip if it's a versionable asset
                if any(file_path.match(pattern) for pattern in skip_patterns):
                    continue
                
                # Skip .htaccess files - they will be handled separately
                if file_path.name == '.htaccess':
                    continue
                
                # Copy non-versionable asset
                output_file = self.output_dir / relative_path
                output_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, output_file)
                
                non_versionable.append(str(relative_path))
        
        return non_versionable
    
    def save_version_map(self):
        """Save version mapping to JSON file for template processing."""
        with open(self.version_file, 'w') as f:
            json.dump(self.version_map, f, indent=2)
        logger.info(f"Saved asset version map to {self.version_file}")
    
    def load_version_map(self) -> Dict[str, str]:
        """Load version mapping from JSON file."""
        if self.version_file.exists():
            with open(self.version_file, 'r') as f:
                return json.load(f)
        return {}
    
    def get_versioned_url(self, original_url: str) -> str:
        """Convert original asset URL to versioned URL."""
        # Remove leading slash if present
        clean_url = original_url.lstrip('/')
        
        # Check if we have a versioned version
        if clean_url in self.version_map:
            return '/' + self.version_map[clean_url]
        
        # Return original URL if no versioned version exists
        return original_url
    
    def generate_etag(self, file_path: Path) -> str:
        """Generate ETag for non-versionable assets."""
        if not file_path.exists():
            return ""
        
        # Use file modification time and size for ETag
        stat = file_path.stat()
        etag_data = f"{stat.st_mtime}-{stat.st_size}"
        return f'"{hashlib.md5(etag_data.encode()).hexdigest()}"'


def create_htaccess_rules(output_dir: str, version_map: Dict[str, str], non_versionable: List[str], source_dir: str = "src/static_files/markup"):
    """Create .htaccess file with appropriate caching rules."""
    htaccess_content = """# Asset Caching Configuration for zhlaw
# Generated automatically - do not modify manually

<IfModule mod_expires.c>
    ExpiresActive On
    
    # Versioned assets (CSS, JS) - 1 year cache with immutable flag
    <FilesMatch "\.v[a-f0-9]{8}\.(css|js)$">
        ExpiresDefault "access plus 1 year"
        Header set Cache-Control "max-age=31536000, immutable"
        Header unset ETag
        Header unset Last-Modified
    </FilesMatch>
    
    # Non-versioned static assets - 1 week cache with revalidation
    <FilesMatch "\.(png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot)$">
        ExpiresDefault "access plus 1 week"
        Header set Cache-Control "max-age=604800, stale-while-revalidate=86400"
        FileETag MTime Size
    </FilesMatch>
    
    # HTML files - 5 minutes cache, private
    <FilesMatch "\.html?$">
        ExpiresDefault "access plus 5 minutes"
        Header set Cache-Control "max-age=300, private"
        Header unset ETag
        Header unset Last-Modified
    </FilesMatch>
    
    # JSON metadata files - 1 hour cache with revalidation
    <FilesMatch "\.json$">
        ExpiresDefault "access plus 1 hour"
        Header set Cache-Control "max-age=3600, stale-while-revalidate=600"
        FileETag MTime Size
    </FilesMatch>
</IfModule>

<IfModule mod_headers.c>
    # Remove server signature headers for security
    Header unset Server
    Header unset X-Powered-By
    
    # Add security headers
    Header always set X-Content-Type-Options nosniff
    Header always set X-Frame-Options DENY
    Header always set X-XSS-Protection "1; mode=block"
</IfModule>

# Existing URL rewrite rules preserved below
"""
    
    # Write new .htaccess file
    htaccess_path = Path(output_dir) / '.htaccess'
    
    # Preserve existing rewrite rules from source file
    existing_rules = ""
    source_htaccess = Path(source_dir) / '.htaccess'
    if source_htaccess.exists():
        with open(source_htaccess, 'r') as f:
            content = f.read()
            existing_rules = "\n" + content
    
    with open(htaccess_path, 'w') as f:
        f.write(htaccess_content + existing_rules)
    
    logger.info(f"Created .htaccess with caching rules at {htaccess_path}")