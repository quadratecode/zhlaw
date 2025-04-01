# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import os
from datetime import datetime
from urllib.parse import urljoin
import re


class SitemapGenerator:
    def __init__(self, domain, public_dir="public"):
        self.domain = domain.rstrip("/")
        self.public_dir = public_dir
        self.static_priorities = {
            "404.html": "0.1",
            "about.html": "0.5",
            "data.html": "0.8",
            "index.html": "1.0",
        }

    def get_last_modified(self, file_path):
        timestamp = os.path.getmtime(file_path)
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")

    def parse_col_zh_filename(self, filename):
        match = re.match(r"(\d+(?:\.\d+)?)-(\d+)", filename)
        if match:
            prefix = float(match.group(1))
            number = int(match.group(2))
            return prefix, number
        return None, None


    def get_priority(self, root, file):
        """
        Determines the priority of a file based on its location and name.

        Args:
            root: Directory containing the file
            file: Filename

        Returns:
            str: Priority value between 0.0 and 1.0
        """
        # Assign lowest priority (0.1) to diff files
        if "diff" in root:
            return "0.1"

        if "col-zh" in root or "col-ch" in root:
            prefix, number = self.parse_col_zh_filename(file)
            if prefix is not None:
                # Group files by prefix
                same_prefix_files = [
                    f for f in os.listdir(root) if f.startswith(f"{prefix}-")
                ]
                if same_prefix_files:
                    max_number = max(
                        int(self.parse_col_zh_filename(f)[1] or 0)
                        for f in same_prefix_files
                    )
                    return "1.0" if number == max_number else "0.2"
                return "1.0"  # Single file case
            return "0.2"
        return self.static_priorities.get(file, "0.8")

    def generate_sitemap(self):
        urls = []

        for root, dirs, files in os.walk(self.public_dir):
            for file in files:
                if not file.endswith(".html"):
                    continue

                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, self.public_dir)
                url = urljoin(self.domain, relative_path)
                last_mod = self.get_last_modified(file_path)
                priority = self.get_priority(root, file)

                urls.append({"loc": url, "lastmod": last_mod, "priority": priority})

        return self.create_sitemap_xml(urls)

    def create_sitemap_xml(self, urls):
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

        for url in urls:
            xml += "  <url>\n"
            xml += f'    <loc>{url["loc"]}</loc>\n'
            xml += f'    <lastmod>{url["lastmod"]}</lastmod>\n'
            xml += f'    <priority>{url["priority"]}</priority>\n'
            xml += "  </url>\n"

        xml += "</urlset>"
        return xml

    def save_sitemap(self, output_path="public/sitemap.xml"):
        sitemap_content = self.generate_sitemap()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(sitemap_content)


# Usage example
if __name__ == "__main__":
    generator = SitemapGenerator("https://www.zhlaw.ch")
    generator.save_sitemap()
