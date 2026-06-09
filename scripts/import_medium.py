#!/usr/bin/env python3
import os
import sys
import re
import urllib.parse
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: Missing required libraries.")
    print("Please install them using: pip3 install requests beautifulsoup4")
    sys.exit(1)

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text)
    return text.strip('-')

def extract_gist_code(iframe_url):
    """
    Fetches the medium media iframe, finds the Gist link, 
    and fetches code contents from GitHub API.
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        response = requests.get(iframe_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Look for script tag pointing to gist.github.com
        script_tag = soup.find('script', src=re.compile(r'gist\.github\.com'))
        if not script_tag:
            # Maybe a direct link to gist in anchor tag
            a_tag = soup.find('a', href=re.compile(r'gist\.github\.com'))
            gist_url = a_tag['href'] if a_tag else None
        else:
            gist_url = script_tag['src']
            
        if not gist_url:
            return None
            
        # Extract Gist ID
        match = re.search(r'gist\.github\.com/([^/]+)/([a-f0-9]+)', gist_url)
        if not match:
            return None
            
        username, gist_id = match.groups()
        
        # Call GitHub Gists API
        api_url = f"https://api.github.com/gists/{gist_id}"
        api_response = requests.get(api_url, headers=headers, timeout=10)
        if api_response.status_code != 200:
            # Fallback to direct raw download if API fails
            raw_fallback_url = f"https://gist.githubusercontent.com/{username}/{gist_id}/raw/"
            raw_response = requests.get(raw_fallback_url, timeout=10)
            if raw_response.status_code == 200:
                return [("code", "kotlin", raw_response.text)]
            return None
            
        gist_data = api_response.json()
        files = gist_data.get('files', {})
        code_snippets = []
        for filename, file_info in files.items():
            content = file_info.get('content', '')
            language = file_info.get('language', 'kotlin').lower()
            code_snippets.append((filename, language, content))
            
        return code_snippets
    except Exception as e:
        print(f"  Warning: failed to extract gist from {iframe_url}: {e}")
        return None

def import_medium_post(url_or_path):
    html_content = ""
    source_url = ""
    
    # Check if input is a local file
    if os.path.exists(url_or_path) and os.path.isfile(url_or_path):
        print(f"Reading local HTML file: {url_or_path}...")
        with open(url_or_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    else:
        # Check if it's a URL
        if not (url_or_path.startswith('http://') or url_or_path.startswith('https://')):
            print(f"Error: Path '{url_or_path}' does not exist, and is not a valid URL.")
            sys.exit(1)
            
        source_url = url_or_path
        print(f"Fetching Medium article from: {source_url}...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        try:
            response = requests.get(source_url, headers=headers, timeout=15)
            if response.status_code == 403:
                print("\n" + "!"*60)
                print("Error: Cloudflare blocked the automated request (403 Forbidden).")
                print("To bypass this security check:")
                print("  1. Open the article in your web browser.")
                print("  2. Save the page as HTML (e.g. 'article.html').")
                print(f"  3. Run: python3 scripts/import_medium.py article.html")
                print("!"*60 + "\n")
                sys.exit(1)
            elif response.status_code != 200:
                print(f"Error: Failed to fetch page (status code {response.status_code})")
                sys.exit(1)
            html_content = response.text
        except Exception as e:
            print(f"Error making request: {e}")
            sys.exit(1)
            
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Extract metadata
    title_tag = soup.find('h1') or soup.find(meta={'property': 'og:title'})
    title = title_tag.text.strip() if title_tag else "Untitled Post"
    if title.endswith(" - Medium"):
        title = title[:-9]
        
    # Date
    date_meta = soup.find('meta', property='article:published_time')
    if date_meta:
        date_str = date_meta['content'][:10] # YYYY-MM-DD
    else:
        # Try finding date in standard elements or default to today
        date_str = datetime.today().strftime('%Y-%m-%d')
        
    # Description
    desc_meta = soup.find('meta', property='og:description') or soup.find('meta', name='description')
    description = desc_meta['content'].strip() if desc_meta else ""
    
    # Tags
    tags = []
    keywords_meta = soup.find('meta', name='keywords')
    if keywords_meta:
        tags = [t.strip().lower() for t in keywords_meta['content'].split(',') if t.strip()]
    
    slug = slugify(title)
    print(f"Found Title: '{title}'")
    print(f"Date: {date_str}")
    print(f"Slug: {slug}")
    
    # Ensure images folder exists
    image_dir_relative = f"assets/img/posts/{slug}"
    image_dir_absolute = os.path.join(os.getcwd(), image_dir_relative)
    os.makedirs(image_dir_absolute, exist_ok=True)
    
    # Find article container
    article_container = soup.find('article')
    if not article_container:
        print("Warning: Could not find <article> element. Scraped page structure might be different.")
        article_container = soup.body
        
    markdown_content = []
    img_counter = 0
    
    elements = article_container.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'blockquote', 'figure', 'pre'])
    parsed_ids = set()
    
    for el in elements:
        el_id = id(el)
        if el_id in parsed_ids:
            continue
            
        for child in el.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'blockquote', 'figure', 'pre']):
            parsed_ids.add(id(child))
            
        tag_name = el.name
        
        def get_clean_text(node):
            # Duplicate code block to work on clean copy
            import copy
            node_copy = copy.copy(node)
            
            for a in node_copy.find_all('a'):
                href = a.get('href', '')
                if href.startswith('https://resolve.medium.com') or href.startswith('https://medium.com/r/?url='):
                    parsed_url = urllib.parse.urlparse(href)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    if 'url' in query_params:
                        href = query_params['url'][0]
                a.replace_with(f"[{a.text}]({href})")
            
            for code_tag in node_copy.find_all('code'):
                code_tag.replace_with(f"`{code_tag.text}`")
                
            for strong in node_copy.find_all(['strong', 'b']):
                strong.replace_with(f"**{strong.text}**")
                
            for em in node_copy.find_all(['em', 'i']):
                em.replace_with(f"*{em.text}*")
                
            return node_copy.text.strip()

        if tag_name == 'h1' and el.text.strip() == title:
            continue
            
        elif tag_name in ['h1', 'h2', 'h3', 'h4']:
            level = {'h1': '##', 'h2': '##', 'h3': '###', 'h4': '####'}[tag_name]
            clean_text = get_clean_text(el)
            if clean_text:
                markdown_content.append(f"{level} {clean_text}\n")
                
        elif tag_name == 'p':
            clean_text = get_clean_text(el)
            if clean_text:
                markdown_content.append(f"{clean_text}\n")
                
        elif tag_name == 'blockquote':
            clean_text = get_clean_text(el)
            if clean_text:
                markdown_content.append(f"> {clean_text}\n")
                
        elif tag_name in ['ul', 'ol']:
            bullet = '-' if tag_name == 'ul' else '1.'
            list_items = []
            for li in el.find_all('li', recursive=False):
                clean_text = get_clean_text(li)
                if clean_text:
                    list_items.append(f"{bullet} {clean_text}")
            if list_items:
                markdown_content.append("\n".join(list_items) + "\n")
                
        elif tag_name == 'pre':
            code_text = el.text
            markdown_content.append(f"```kotlin\n{code_text}\n```\n")
            
        elif tag_name == 'figure':
            iframe = el.find('iframe')
            img = el.find('img')
            figcaption = el.find('figcaption')
            caption_text = figcaption.text.strip() if figcaption else ""
            
            if iframe:
                iframe_src = iframe.get('src', '')
                if iframe_src.startswith('//'):
                    iframe_src = 'https:' + iframe_src
                if 'medium.com/media/' in iframe_src or 'gist.github.com' in iframe_src:
                    print(f"  Detected embedded gist/media frame: {iframe_src}")
                    gist_snippets = extract_gist_code(iframe_src)
                    if gist_snippets:
                        for filename, lang, code_content in gist_snippets:
                            print(f"    Extracted code snippet: {filename} ({lang})")
                            code_block_text = ""
                            if filename and not filename.startswith('gistfile'):
                                code_block_text += f"// {filename}\n"
                            code_block_text += code_content.strip()
                            markdown_content.append(f"```{lang}\n{code_block_text}\n```\n")
                    else:
                        markdown_content.append(f"*[Embedded content: view in original article]({source_url or iframe_src})*\n")
            elif img:
                img_src = img.get('src', '')
                # Medium often stores higher resolution urls in srcset or data-src
                if img.get('data-src'):
                    img_src = img.get('data-src')
                elif img.get('srcset'):
                    # Get the largest image in srcset
                    srcset_parts = img.get('srcset').split(',')
                    if srcset_parts:
                        last_part = srcset_parts[-1].strip().split(' ')
                        if last_part:
                            img_src = last_part[0]
                            
                if img_src and not img_src.startswith('data:'):
                    img_counter += 1
                    ext = '.png'
                    parsed_img_url = urllib.parse.urlparse(img_src)
                    path = parsed_img_url.path
                    if '.' in path.split('/')[-1]:
                        potential_ext = '.' + path.split('/')[-1].split('.')[-1]
                        if potential_ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
                            ext = potential_ext
                            
                    local_img_name = f"image_{img_counter}{ext}"
                    local_img_path = os.path.join(image_dir_absolute, local_img_name)
                    local_img_url = f"/{image_dir_relative}/{local_img_name}"
                    
                    try:
                        print(f"  Downloading image: {img_src} -> {local_img_name}...")
                        img_headers = {
                            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                        }
                        img_response = requests.get(img_src, headers=img_headers, timeout=15)
                        if img_response.status_code == 200:
                            with open(local_img_path, 'wb') as f:
                                f.write(img_response.content)
                            
                            alt_text = caption_text or f"Image {img_counter}"
                            markdown_content.append(f"![{alt_text}]({local_img_url})\n")
                            if caption_text:
                                markdown_content.append(f"*{caption_text}*\n")
                        else:
                            markdown_content.append(f"![{caption_text or 'Image'}]({img_src})\n")
                    except Exception as e:
                        print(f"  Warning: failed to download image: {e}")
                        markdown_content.append(f"![{caption_text or 'Image'}]({img_src})\n")

    full_body = "\n".join(markdown_content)
    full_body = re.sub(r'\n{3,}', '\n\n', full_body)
    
    front_matter = [
        "---",
        "layout: post",
        f'title: "{title}"',
        f"date: {date_str}",
    ]
    if description:
        escaped_desc = description.replace('"', '\\"')
        front_matter.append(f'description: "{escaped_desc}"')
        
    front_matter.append(f"categories: [android]")
    
    if tags:
        clean_tags = [re.sub(r'[^a-z0-9]', '', t) for t in tags]
        clean_tags = [t for t in clean_tags if t][:6]
        front_matter.append(f"tags: [{', '.join(clean_tags)}]")
        
    front_matter.append("---")
    front_matter.append("")
    front_matter.append(full_body)
    
    output_filename = f"{date_str}-{slug}.md"
    output_path = os.path.join(os.getcwd(), "_posts", output_filename)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(front_matter))
        
    print("\n" + "="*50)
    print(f"Success! Imported Medium article as Jekyll post:")
    print(f"File: _posts/{output_filename}")
    print(f"Images downloaded to: {image_dir_relative}/")
    print("="*50 + "\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/import_medium.py <medium-post-url-or-local-html>")
        sys.exit(1)
        
    import_medium_post(sys.argv[1])
