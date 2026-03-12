from crewai import Agent
from crewai.llm import LLM
from tools import tavily_recent_job_search, fetch_job_page, send_html_email

llm = LLM(model="ollama/llama3.1")


def usa_ai_job_researcher() -> Agent:
    return Agent(
        role="USA Recent AI Job Researcher",
        goal=(
            "Find highly relevant USA-based AI, LLM, GenAI, and Applied AI jobs posted in the last 7 days. "
            "Read the actual job page before deciding. Reject stale, irrelevant, or high-experience roles."
        ),
        backstory=(
            "You are a strict job researcher. You do not trust search snippets. "
            "You read actual job descriptions, filter by freshness, relevance, and experience, "
            "and only keep strong jobs that a candidate can realistically apply to."
        ),
        tools=[tavily_recent_job_search, fetch_job_page],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def email_report_sender() -> Agent:
    return Agent(
        role="Job Report Email Sender",
        goal="Send the final HTML report exactly as provided.",
        backstory="You send only the final validated report.",
        tools=[send_html_email],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )