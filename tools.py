import os
import re
import json
import smtplib
import requests
from urllib.parse import urlparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

ALLOWED_JOB_DOMAINS = [
    "greenhouse.io",
    "lever.co",
    "workdayjobs.com",
    "myworkdayjobs.com",
    "ashbyhq.com",
    "jobs.ashbyhq.com",
    "boards.greenhouse.io",
    "jobs.lever.co",
    "smartrecruiters.com",
    "linkedin.com",
    "careers.google.com",
]

BLOCKED_PATTERNS = [
    "/jobs/search",
    "/q-",
    "indeed.com/jobs",
    "monster.com/jobs/search",
    "linkedin.com/jobs/search",
]

TARGET_ROLE_PATTERNS = [
    r"\bgenerative ai engineer\b",
    r"\bllm engineer\b",
    r"\bapplied ai engineer\b",
    r"\bai engineer\b",
    r"\bmachine learning engineer\b",
    r"\bml engineer\b",
]

AI_KEYWORDS = [
    "llm",
    "large language model",
    "generative ai",
    "genai",
    "rag",
    "agentic",
    "agents",
    "langchain",
    "transformers",
    "huggingface",
    "prompt engineering",
]

GOOD_SKILLS = [
    "python",
    "llm",
    "langchain",
    "rag",
    "vector database",
    "pinecone",
    "faiss",
    "chromadb",
    "aws",
    "azure",
    "gcp",
    "pytorch",
    "tensorflow",
    "transformers",
    "huggingface",
    "machine learning",
    "generative ai",
    "prompt engineering",
    "agents",
    "agentic ai",
    "mlops",
    "docker",
    "kubernetes",
    "api",
    "fastapi",
]

TARGET_EXPERIENCE_PATTERNS = [
    r"\b2\s*-\s*5\s+years?\b",
    r"\b2\s*to\s*5\s+years?\b",
    r"\b3\s*-\s*5\s+years?\b",
    r"\b3\s*to\s*5\s+years?\b",
    r"\b3\+\s+years?\b",
    r"\b4\+\s+years?\b",
    r"\bminimum\s+3\s+years?\b",
    r"\b3\s+years?\b",
    r"\b4\s+years?\b",
    r"\b5\s+years?\b",
]

EXCLUDE_EXPERIENCE_PATTERNS = [
    r"\b6\+?\s+years?\b",
    r"\b7\+?\s+years?\b",
    r"\b8\+?\s+years?\b",
    r"\b9\+?\s+years?\b",
    r"\b10\+?\s+years?\b",
    r"\b11\+?\s+years?\b",
    r"\b12\+?\s+years?\b",
    r"\b15\+?\s+years?\b",
    r"\b8\s*-\s*10\s+years?\b",
    r"\b10\s*-\s*15\s+years?\b",
]

EXCLUDE_TITLE_PATTERNS = [
    r"\bstaff\b",
    r"\bprincipal\b",
    r"\bdirector\b",
    r"\barchitect\b",
    r"\bmanager\b",
    r"\bsenior staff\b",
]

US_KEYWORDS = [
    "united states",
    "usa",
    "u.s.",
    "us-based",
    "remote us",
    "remote usa",
    "remote united states",
    "new york",
    "new jersey",
    "california",
    "texas",
    "washington",
    "virginia",
    "massachusetts",
    "illinois",
    "florida",
    "pennsylvania",
]

HEADERS = {"User-Agent": "Mozilla/5.0"}


def _safe_get_env(name: str) -> str:
    value = os.getenv(name)
    return value.strip() if value else ""


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _is_allowed_domain(url: str) -> bool:
    d = _domain(url)
    return any(x in d for x in ALLOWED_JOB_DOMAINS)


def _is_blocked_url(url: str) -> bool:
    u = (url or "").lower()
    return any(x in u for x in BLOCKED_PATTERNS)


def _looks_like_real_job_url(url: str) -> bool:
    u = (url or "").lower()
    good = any(x in u for x in ["/jobs/", "/job/", "/careers/", "/positions/", "/view/", "/results/"])
    return good and not _is_blocked_url(url)


def _regex_any(text: str, patterns: list[str]) -> bool:
    t = (text or "").lower()
    return any(re.search(p, t) for p in patterns)


def _extract_skills(text: str) -> str:
    t = (text or "").lower()
    found = [s for s in GOOD_SKILLS if s in t]
    return ", ".join(sorted(set(found))[:8]) if found else "Not clearly stated"


def _extract_experience(text: str) -> str:
    t = (text or "").lower()
    for p in TARGET_EXPERIENCE_PATTERNS:
        m = re.search(p, t)
        if m:
            return m.group(0)
    for p in EXCLUDE_EXPERIENCE_PATTERNS:
        m = re.search(p, t)
        if m:
            return m.group(0)
    return "Not clearly stated"


def _extract_location(text: str) -> str:
    t = _normalize_text(text)
    remote_match = re.search(r"(remote[^.,;\n]*)", t, re.IGNORECASE)
    if remote_match:
        return remote_match.group(1).strip()

    for kw in [
        "United States", "USA", "New York", "New Jersey", "California", "Texas",
        "Washington", "Virginia", "Massachusetts", "Illinois", "Florida", "Pennsylvania"
    ]:
        if kw.lower() in t.lower():
            return kw

    return "Not clearly stated"


def _extract_company_from_domain(url: str) -> str:
    d = _domain(url).replace("www.", "")
    if not d:
        return "Not clearly stated"
    return d.split(".")[0].title()


def _score_job(title: str, text: str) -> int:
    score = 0
    full = f"{title} {text}".lower()

    if _regex_any(title, TARGET_ROLE_PATTERNS):
        score += 8

    for kw in AI_KEYWORDS:
        if kw in full:
            score += 2

    for skill in GOOD_SKILLS:
        if skill in full:
            score += 1

    if _regex_any(full, TARGET_EXPERIENCE_PATTERNS):
        score += 5

    if _regex_any(full, EXCLUDE_EXPERIENCE_PATTERNS):
        score -= 10

    if _regex_any(title, EXCLUDE_TITLE_PATTERNS):
        score -= 8

    if any(x in full for x in ["remote", "united states", "usa"]):
        score += 2

    return score


def search_recent_jobs(query: str, max_results: int = 10) -> list[dict]:
    api_key = _safe_get_env("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("Missing TAVILY_API_KEY")

    client = TavilyClient(api_key=api_key)
    response = client.search(
        query=query,
        topic="general",
        max_results=max_results,
        search_depth="advanced",
        days=7,
    )

    results = []
    for r in response.get("results", []):
        title = _normalize_text(r.get("title", ""))
        url = _normalize_text(r.get("url", ""))
        snippet = _normalize_text(r.get("content", ""))

        if not url:
            continue
        if not _is_allowed_domain(url):
            continue
        if not _looks_like_real_job_url(url):
            continue

        results.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
                "source": _domain(url),
            }
        )
    return results


def fetch_job_page(url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        return {"error": f"Failed to fetch page: {str(e)}", "url": url}

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = _normalize_text(soup.get_text(" ", strip=True))
    page_title = _normalize_text(soup.title.get_text()) if soup.title else "Not clearly stated"

    posted_date = "Not clearly stated"
    company = "Not clearly stated"

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = script.string
            if not raw:
                continue
            data = json.loads(raw)

            if isinstance(data, dict):
                if data.get("datePosted"):
                    posted_date = str(data.get("datePosted"))
                hiring_org = data.get("hiringOrganization")
                if isinstance(hiring_org, dict) and hiring_org.get("name"):
                    company = hiring_org["name"]

            elif isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    if item.get("datePosted") and posted_date == "Not clearly stated":
                        posted_date = str(item.get("datePosted"))
                    hiring_org = item.get("hiringOrganization")
                    if isinstance(hiring_org, dict) and hiring_org.get("name") and company == "Not clearly stated":
                        company = hiring_org["name"]
        except Exception:
            continue

    if company == "Not clearly stated":
        company = _extract_company_from_domain(url)

    return {
        "url": url,
        "page_title": page_title,
        "company": company,
        "posted_date": posted_date,
        "text": text[:30000],
    }


def is_recent_posted(text: str, posted_date: str) -> bool:
    t = (text or "").lower()

    if posted_date and posted_date != "Not clearly stated":
        # Keep if a structured date exists; Tavily already searched recent 7 days.
        return True

    if "today" in t or "just posted" in t or "yesterday" in t:
        return True

    m = re.search(r"(\d+)\s+day[s]?\s+ago", t)
    if m:
        return int(m.group(1)) <= 7

    if "week ago" in t or "weeks ago" in t:
        return False

    # If date is unclear, allow it but rely on score and Tavily days=7.
    return True


def is_relevant_job(title: str, text: str) -> bool:
    full = f"{title} {text}".lower()

    has_target_role = _regex_any(title, TARGET_ROLE_PATTERNS) or any(k in full for k in AI_KEYWORDS)
    us_match = any(k in full for k in US_KEYWORDS) or "remote" in full
    bad_experience = _regex_any(full, EXCLUDE_EXPERIENCE_PATTERNS)
    bad_title = _regex_any(title, EXCLUDE_TITLE_PATTERNS)
    good_exp = _regex_any(full, TARGET_EXPERIENCE_PATTERNS)

    if bad_experience or bad_title:
        return False
    if not has_target_role:
        return False
    if not us_match:
        return False
    if not good_exp:
        return False

    return _score_job(title, text) >= 10


def dedupe_jobs(items: list[dict]) -> list[dict]:
    seen = set()
    output = []

    for item in items:
        key = (
            item.get("title", "").strip().lower(),
            item.get("company", "").strip().lower(),
            item.get("location", "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(item)

    return output


def build_html_report(jobs: list[dict]) -> str:
    rows = []

    for job in jobs:
        rows.append(f"""
        <tr>
            <td>{job['title']}</td>
            <td>{job['company']}</td>
            <td>{job['location']}</td>
            <td>{job['posted_date']}</td>
            <td>{job['experience']}</td>
            <td>{job['key_skills']}</td>
            <td>{job['why_match']}</td>
            <td><a href="{job['apply_link']}">Apply</a></td>
            <td>{job['source']}</td>
        </tr>
        """)

    return f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Recent USA AI Jobs Shortlist</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            h1 {{ color: #222; }}
            table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
            th, td {{ border: 1px solid #ccc; padding: 10px; vertical-align: top; text-align: left; }}
            th {{ background: #f5f5f5; }}
            a {{ color: #0b57d0; }}
        </style>
    </head>
    <body>
        <h1>Recent USA AI Jobs Shortlist (Last 7 Days)</h1>
        <p><b>Total Shortlisted Jobs:</b> {len(jobs)}</p>
        <table>
            <thead>
                <tr>
                    <th>Job Title</th>
                    <th>Company</th>
                    <th>Location</th>
                    <th>Posted Date</th>
                    <th>Experience</th>
                    <th>Key Skills</th>
                    <th>Why it matches</th>
                    <th>Apply Link</th>
                    <th>Source</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </body>
    </html>
    """


def send_html_email(subject: str, html: str) -> str:
    smtp_host = _safe_get_env("SMTP_HOST")
    smtp_port = int(_safe_get_env("SMTP_PORT") or "587")
    smtp_user = _safe_get_env("SMTP_USER")
    smtp_pass = _safe_get_env("SMTP_PASS")
    to_email = _safe_get_env("TO_EMAIL")

    missing = []
    for name, value in {
        "SMTP_HOST": smtp_host,
        "SMTP_USER": smtp_user,
        "SMTP_PASS": smtp_pass,
        "TO_EMAIL": to_email,
    }.items():
        if not value:
            missing.append(name)

    if missing:
        raise ValueError(f"Missing env vars: {', '.join(missing)}")

    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_email], msg.as_string())

    return f"Email sent to {to_email}"