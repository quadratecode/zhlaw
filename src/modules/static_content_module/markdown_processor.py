"""
Markdown-to-HTML processor for static content pages.
"""

import markdown
import yaml
from pathlib import Path
from typing import Dict, Any, Tuple


class MarkdownProcessor:
    """Processes markdown files to HTML with frontmatter support."""
    
    def __init__(self):
        """Initialize the markdown processor with extensions."""
        self.md = markdown.Markdown(
            extensions=[
                'extra',  # Includes tables, fenced code blocks, etc.
                'codehilite',  # Syntax highlighting
                'toc',  # Table of contents
                'meta'  # Metadata support
            ],
            extension_configs={
                'codehilite': {
                    'css_class': 'highlight',
                    'use_pygments': False  # Use CSS classes instead of inline styles
                }
            }
        )
    
    def parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """
        Parse YAML frontmatter from markdown content.
        
        Args:
            content: Raw markdown content with optional frontmatter
            
        Returns:
            Tuple of (metadata_dict, markdown_content)
        """
        if not content.startswith('---'):
            return {}, content
        
        try:
            # Split on the closing ---
            parts = content.split('---', 2)
            if len(parts) < 3:
                return {}, content
            
            # Parse YAML frontmatter
            frontmatter_yaml = parts[1].strip()
            markdown_content = parts[2].strip()
            
            metadata = yaml.safe_load(frontmatter_yaml) or {}
            return metadata, markdown_content
            
        except yaml.YAMLError:
            # If YAML parsing fails, treat as regular markdown
            return {}, content
    
    def process_markdown_file(self, file_path: str) -> Dict[str, Any]:
        """
        Process a single markdown file to HTML.
        
        Args:
            file_path: Path to the markdown file
            
        Returns:
            Dictionary containing:
            - html_content: Processed HTML content
            - metadata: Parsed frontmatter metadata
            - filename: Original filename without extension
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse frontmatter and markdown content
        metadata, markdown_content = self.parse_frontmatter(content)
        
        # Convert markdown to HTML
        html_content = self.md.convert(markdown_content)
        
        # Reset the markdown processor for next use
        self.md.reset()
        
        # Get filename without extension
        filename = Path(file_path).stem
        
        return {
            'html_content': html_content,
            'metadata': metadata,
            'filename': filename
        }
    
    def generate_html_page(self, processed_data: Dict[str, Any]) -> str:
        """
        Generate a complete HTML page from processed markdown data.
        
        Args:
            processed_data: Dictionary from process_markdown_file()
            
        Returns:
            Complete HTML page as string
        """
        metadata = processed_data['metadata']
        html_content = processed_data['html_content']
        filename = processed_data['filename']
        
        # Get title from metadata or use filename
        title = metadata.get('title', filename.replace('_', ' ').title())
        
        # Get description from metadata
        description = metadata.get('description', title)
        
        # Generate HTML template with enhanced meta tags
        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <link href="styles.css" rel="stylesheet">
    <link href="/favicon.ico" rel="shortcut icon" type="image/x-icon">
    <link href="/favicon.ico" rel="icon" type="image/x-icon">
    <meta charset="UTF-8">
    <meta content="width=device-width, initial-scale=1.0" name="viewport">
    <meta name="language" content="de-CH">
    <meta name="description" content="{description}">
    <title>{title}</title>
</head>
<body>
    <div class="main-container">
        <div class="content">
            {html_content}
        </div>
    </div>
</body>
</html>"""
        
        return html_template
    
    def process_content_directory(self, content_dir: str, output_dir: str) -> None:
        """
        Process all markdown files in content directory and save as HTML.
        
        Args:
            content_dir: Path to directory containing markdown files
            output_dir: Path to directory where HTML files should be saved
        """
        content_path = Path(content_dir)
        output_path = Path(output_dir)
        
        # Ensure output directory exists
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Process each markdown file
        for md_file in content_path.glob('*.md'):
            processed = self.process_markdown_file(str(md_file))
            html_content = self.generate_html_page(processed)
            
            # Save HTML file with pretty-printing
            from bs4 import BeautifulSoup
            from src.utils.html_utils import write_pretty_html
            
            output_file = output_path / f"{processed['filename']}.html"
            
            # Parse the HTML string and then write it with pretty-printing
            soup = BeautifulSoup(html_content, "html.parser")
            write_pretty_html(soup, str(output_file), encoding="utf-8", add_doctype=False)
            
            print(f"Processed: {md_file.name} -> {output_file.name}")


def main():
    """CLI entry point for testing the markdown processor."""
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python markdown_processor.py <content_dir> <output_dir>")
        sys.exit(1)
    
    content_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    processor = MarkdownProcessor()
    processor.process_content_directory(content_dir, output_dir)


if __name__ == '__main__':
    main()