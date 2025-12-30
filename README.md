# Sevban Bayir's Blog

Personal blog about software engineering, mobile development, and architectural patterns.

## 🚀 Quick Start

This blog is built with [Jekyll](https://jekyllrb.com/) and hosted on [GitHub Pages](https://pages.github.com/).

### Local Development

```bash
# Install dependencies
bundle install

# Run locally
bundle exec jekyll serve

# Visit http://localhost:4000
```

### Writing New Posts

1. Create a new file in `_posts/` with format: `YYYY-MM-DD-title.md`
2. Add front matter:
   ```yaml
   ---
   layout: post
   title: "Your Post Title"
   date: YYYY-MM-DD
   categories: [Category1, Category2]
   tags: [tag1, tag2]
   ---
   ```
3. Write your content in Markdown
4. Commit and push to deploy

### Drafts

Work on posts in `_drafts/` (without date prefix). Preview with:
```bash
bundle exec jekyll serve --drafts
```

## 📁 Structure

```
├── _config.yml      # Site configuration
├── _posts/          # Published blog posts
├── _drafts/         # Draft posts (not published)
├── _tabs/           # Navigation pages
├── assets/          # Images, CSS, JS
└── index.md         # Home page
```

## 📝 License

Content © Sevban Bayir. Code under MIT License.

