from crewai import Task


def research_jobs_task(agent):
    return Task(
        description=(
            "Find real USA-based jobs for these role families:\n"
            "- Generative AI Engineer\n"
            "- LLM Engineer\n"
            "- Applied AI Engineer\n"
            "- AI Engineer\n"
            "- Machine Learning Engineer with LLM, RAG, or Agents focus\n\n"

            "Search only recent jobs from the last 7 days.\n"
            "Prefer jobs from the last 3 to 4 days when available.\n\n"

            "Use multiple searches such as:\n"
            '- "Generative AI Engineer" "remote USA" "3+ years"\n'
            '- "LLM Engineer" USA "3-5 years"\n'
            '- "Applied AI Engineer" "United States" "4+ years"\n'
            '- "AI Engineer" "remote" "RAG" "3 years"\n'
            '- "Machine Learning Engineer" "LLM" "USA" "3+ years"\n\n'

            "Process rules:\n"
            "1. Use the recent job search tool to get candidate links.\n"
            "2. For every promising result, fetch the actual job page.\n"
            "3. Judge the job using the full job description, not just the search snippet.\n"
            "4. Reject jobs older than 7 days when the page clearly indicates it is older.\n"
            "5. Reject jobs that do not have a real job posting page.\n"
            "6. Reject jobs that clearly ask for 6+ years or 7+ years or 10+ years.\n"
            "7. Reject jobs that are mostly unrelated to LLM, GenAI, Applied AI, RAG, or Agents.\n"
            "8. Reject low-confidence results.\n"
            "9. Prefer official company careers pages and high-quality direct posting URLs.\n"
            "10. Do not include generic search pages.\n"
            "11. Do not invent fields.\n\n"

            "Only keep strong matches.\n"
            "Try to return at least 10 strong jobs if available.\n\n"

            "For each final job, include:\n"
            "- Job Title\n"
            "- Company\n"
            "- Location\n"
            "- Posted Date\n"
            "- Experience\n"
            "- Key Skills\n"
            "- Why it matches\n"
            "- Apply Link\n"
            "- Source\n\n"

            "The final output must be a complete HTML document with a clean table."
        ),
        expected_output="A complete HTML document containing only high-confidence recent AI jobs.",
        agent=agent,
    )


def email_jobs_task(agent, research_task):
    return Task(
        description=(
            "Take the HTML output from the previous task and email it.\n\n"
            "Use this exact format:\n"
            "SUBJECT: Recent USA AI Jobs Shortlist (Last 7 Days)\n"
            "HTML:\n"
            "<html>...</html>"
        ),
        expected_output="Confirmation that the email was sent successfully.",
        agent=agent,
        context=[research_task],
    )