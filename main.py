from tools import (
    search_recent_jobs,
    fetch_job_page,
    is_recent_posted,
    is_relevant_job,
    _extract_location,
    _extract_experience,
    _extract_skills,
    _score_job,
    dedupe_jobs,
    build_html_report,
    send_html_email,
)

SEARCH_QUERIES = [
    '"Generative AI Engineer" "remote USA" "3+ years"',
    '"LLM Engineer" USA "3-5 years"',
    '"Applied AI Engineer" "United States" "4+ years"',
    '"AI Engineer" "remote" "RAG" "3 years"',
    '"Machine Learning Engineer" "LLM" "USA" "3+ years"',
]


def collect_jobs() -> list[dict]:
    candidates = []

    for query in SEARCH_QUERIES:
        try:
            results = search_recent_jobs(query, max_results=12)
            candidates.extend(results)
        except Exception as e:
            print(f"Search failed for query {query}: {e}")

    unique_urls = set()
    filtered = []

    for item in candidates:
        url = item["url"]
        if url in unique_urls:
            continue
        unique_urls.add(url)

        page = fetch_job_page(url)
        if "error" in page:
            continue

        text = page.get("text", "")
        title = page.get("page_title") or item.get("title", "")
        company = page.get("company", "Not clearly stated")
        posted_date = page.get("posted_date", "Not clearly stated")

        if not is_recent_posted(text, posted_date):
            continue

        if not is_relevant_job(title, text):
            continue

        score = _score_job(title, text)

        why_match_parts = []
        exp = _extract_experience(text)
        skills = _extract_skills(text)
        location = _extract_location(text)

        if exp != "Not clearly stated":
            why_match_parts.append(f"experience looks like {exp}")
        if skills != "Not clearly stated":
            why_match_parts.append(f"skills include {skills}")
        if "llm" in text.lower() or "generative ai" in text.lower() or "rag" in text.lower():
            why_match_parts.append("JD mentions LLM/GenAI/RAG concepts")

        filtered.append(
            {
                "title": title,
                "company": company,
                "location": location,
                "posted_date": posted_date,
                "experience": exp,
                "key_skills": skills,
                "why_match": "; ".join(why_match_parts) if why_match_parts else "Relevant AI/LLM role",
                "apply_link": url,
                "source": item.get("source", ""),
                "score": score,
            }
        )

    filtered = dedupe_jobs(filtered)
    filtered = sorted(filtered, key=lambda x: x["score"], reverse=True)

    return filtered[:15]


def run():
    jobs = collect_jobs()

    if not jobs:
        print("No strong recent jobs found.")
        return

    html = build_html_report(jobs)
    result = send_html_email(
        subject="Recent USA AI Jobs Shortlist (Last 7 Days)",
        html=html,
    )

    print(result)
    print(f"Total jobs sent: {len(jobs)}")


if __name__ == "__main__":
    run()