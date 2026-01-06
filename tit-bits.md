---
layout: page
title: Tit-Bits
permalink: /tit-bits/
---

Here are some minimal notes and code snippets.

<ul class="post-list">
  {% for note in site.tit_bits %}
    <li>
      <span class="post-meta">{{ note.date | date: "%b %-d, %Y" }}</span>
      <h3>
        <a class="post-link" href="{{ note.url | relative_url }}">
          {{ note.title | escape }}
        </a>
      </h3>
      {% if note.description %}
        <p>{{ note.description }}</p>
      {% endif %}
    </li>
  {% endfor %}
</ul>
