---
layout: page
title: Archives
permalink: /archives/
---

{% assign postsByYear = site.posts | group_by_exp:"post", "post.date | date: '%Y'" %}

{% for year in postsByYear %}
## {{ year.name }}

<ul>
{% for post in year.items %}
  <li>
    <span style="color: #828282; font-size: 0.9em;">{{ post.date | date: "%b %-d" }}</span> —
    <a href="{{ post.url | relative_url }}">{{ post.title }}</a>
  </li>
{% endfor %}
</ul>
{% endfor %}
