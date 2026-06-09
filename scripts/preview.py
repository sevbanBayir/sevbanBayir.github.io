#!/usr/bin/env python3
import os
import sys
import re

try:
    import markdown
except ImportError:
    print("Error: Missing 'markdown' library. Installing it...")
    os.system("pip3 install markdown")
    import markdown

def generate_preview(post_path):
    if not os.path.exists(post_path):
        print(f"Error: Post file '{post_path}' not found.")
        sys.exit(1)

    # 1. Read post content and front matter
    with open(post_path, 'r', encoding='utf-8') as f:
        post_text = f.read()

    front_matter = {}
    content_markdown = post_text
    
    if post_text.startswith('---'):
        parts = post_text.split('---', 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            content_markdown = parts[2]
            for line in fm_text.split('\n'):
                line = line.strip()
                if ':' in line:
                    k, v = line.split(':', 1)
                    front_matter[k.strip()] = v.strip().strip('"').strip("'")

    # Convert markdown content to HTML (with fenced code blocks)
    post_html = markdown.markdown(content_markdown, extensions=['fenced_code', 'nl2br'])

    # 2. Read layout template
    layout_path = os.path.join(os.getcwd(), '_layouts', 'default.html')
    if not os.path.exists(layout_path):
        print("Error: _layouts/default.html not found.")
        sys.exit(1)

    with open(layout_path, 'r', encoding='utf-8') as f:
        template = f.read()

    # 3. Replace Liquid tags and relative URLs
    title = front_matter.get('title', 'Post Preview')
    
    # Simple replacement of layout variables
    html = template
    html = html.replace('{{ content }}', post_html)
    html = html.replace('{{ page.title | escape }}', title)
    html = html.replace('{{ page.title }}', title)
    
    # Replace Jeykll SEO tag if any (strip it or replace it)
    html = re.sub(r'\{%-\s*seo\s*-\%\}', f'<title>{title}</title>', html)
    html = re.sub(r'\{%-\s*feed_meta\s*-\%\}', '', html)
    
    # Replace relative_url filters
    # format: {{ '/assets/main.css' | relative_url }}
    # We want to replace it with actual relative paths from scratch/ directory, i.e., '../assets/main.css'
    def relative_url_replacer(match):
        path = match.group(1).strip().strip("'").strip('"')
        # Since we write preview to scratch/preview.html, relative paths need to go up one folder
        if path.startswith('/'):
            path = path[1:]
        return '../' + path

    html = re.sub(r'\{\{\s*([^\}]+)\s*\|\s*relative_url\s*\}\}', relative_url_replacer, html)

    # Ensure scratch directory exists
    scratch_dir = os.path.join(os.getcwd(), 'scratch')
    os.makedirs(scratch_dir, exist_ok=True)

    preview_path = os.path.join(scratch_dir, 'preview.html')
    with open(preview_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print("\n" + "="*70)
    print("Preview HTML generated successfully!")
    print(f"File Path: {preview_path}")
    print("\nTo preview it, paste the following URL into your web browser (Safari/Chrome):")
    print(f"file://{preview_path}")
    print("="*70 + "\n")

if __name__ == "__main__":
    post_file = ""
    # Find the first markdown file in _posts to preview by default if none specified
    if len(sys.argv) < 2:
        posts_dir = os.path.join(os.getcwd(), '_posts')
        if os.path.exists(posts_dir):
            files = sorted([f for f in os.listdir(posts_dir) if f.endswith('.md')])
            if files:
                post_file = os.path.join('_posts', files[-1])
        
        if not post_file:
            print("Usage: python3 scripts/preview.py <path-to-jekyll-post.md>")
            sys.exit(1)
    else:
        post_file = sys.argv[1]

    print(f"Generating preview for: {post_file}")
    generate_preview(post_file)
