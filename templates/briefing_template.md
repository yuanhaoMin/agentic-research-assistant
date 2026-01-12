# Company Briefing: {{ company_name }}

## 1. Overview
- Industry: {{ industry }}
- Headquarters: {{ headquarters }}
- Website: {{ website }}

## 2. Core Products/Services
{% for p in products %}
- {{ p }}
{% endfor %}

## 3. Partners & Ecosystem (Public Information)
{% for item in partnerships %}
- {{ item }}
{% endfor %}

## 4. Recent Highlights (From Web Crawling/Search)
{{ web_summary }}

## 5. Internal Materials Summary (Translated)
{{ internal_doc_summary }}

## 6. Risk Notice (For Internal Use Only)
- Risk Level: {{ risk_category }}
- Note: The final external version must pass security filtering (sensitive project names/codenames must not be disclosed)