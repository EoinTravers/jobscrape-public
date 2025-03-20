import asyncio
from typing import Literal
from pydantic import BaseModel, Field


import json
from src.extract import ExtractedJobPosting, JobPosting, listing_to_text
from src.llm import OpenAIClient


"""
Logic for using AI to review/annotate job postings
"""


def field(description: str):
    """Save a few keystrokes"""
    return Field(description=description)

def load_listings():
    with open("data/listings.json", "r") as f:
        listings = json.load(f)
    listings = [
        JobPosting(**listing)
        for listing in listings
    ]
    return  listings


YNM = Literal["yes", "no", "maybe"]

class JobEvaluation(BaseModel):
    eval_role_type: YNM = field(
        "I'm interested in data science roles, e.g. data scientist, AI engineer, etc., but not data engineer, software engineer, data analyst, etc."
    )
    eval_seniority: YNM = field("I'm interested in senior roles (or higher).")
    eval_location: YNM = field(
        "Is the role either remote or based in Ireland? Say 'no' for roles that require being in London every week"
    )
    eval_positive_industry: YNM = field(
        "I'm particularly interested in roles that have a positive social impact, e.g. mental health, education, climate change, etc. Is this role a match?"
    )
    eval_negative_industry: YNM = field(
        "I'm not interested in industries such as finance, cryptocurrency, marketing, defence etc. Is this role in one of these industries?"
    )
    eval_startup: YNM = field(
        "I prefer startups to large, well-established companies. Is this role with a younger/smaller company?"
    )
    eval_salary: YNM = field("Does this role pay more than £80K (or equivalent)?")


def evaluate_jobs(jobs: list[JobPosting], llm: OpenAIClient) -> JobEvaluation:
    prompt = """
    Read the job posting below and evaluate whether it is a good match for me.
    Provide your response in the format provided.
    """
    job_texts = [listing_to_text(job) for job in jobs]
    return llm.llm_batch(
        prompt, job_texts, response_format=JobEvaluation, progress_bar=True
    )




# We can't easily combine the pydantic classes for 
# JobPosting, and JobEvaluation, so let's manually do it.

# We can't easily combine the pydantic classes for 
# JobPosting, and JobEvaluation, so let's manually do it.

class JobExport(BaseModel):
    """Combines fields from JobPosting and JobEvaluation"""
    # From ExtractedJobPosting
    title: str = Field(alias="job_title", validation_alias="title")
    company_name: str
    industry: str | None
    location: str
    salary: str | None
    contract_type: str
    office_type: str
    # More open-ended stuff
    company_description: str
    company_size: str | None
    job_description: str
    skills: str
    # From JobPosting
    job_id: str
    url: str
    search_label: str
    capture_time: str
    # From JobEvaluation
    eval_role_type: str
    eval_seniority: str
    eval_location: str
    eval_positive_industry: str
    eval_negative_industry: str
    eval_startup: str
    eval_salary: str
    # new field
    evaluation_score: int



# The schema below defines a notion database for storing the `JobExport` instances
# extracted from our data. Any changes to JobExport must be reflected here.
job_posting_notion_schema = {
    "Title": {
        "title": {}  # Required default property
    },
    "Company Name": {"rich_text": {}},
    "Industry": {"rich_text": {}},
    "Location": {"rich_text": {}},
    "Salary": {"rich_text": {}},
    "Contract Type": {"rich_text": {}},
    "Office Type": {"rich_text": {}},
    "Company Description": {"rich_text": {}},
    "Company Size": {"rich_text": {}},
    "Job Description": {"rich_text": {}},
    "Skills": {"rich_text": {}},
    "URL": {"url": {}},
    "Job ID": {"rich_text": {}},
    "Search Label": {"rich_text": {}},
    "Retrieved At": {"date": {}},
    # Evaluation fields
    "Eval Role Type": {"rich_text": {}},
    "Eval Seniority": {"rich_text": {}}, 
    "Eval Location Match": {"rich_text": {}},
    "Eval Positive Industry": {"rich_text": {}},
    "Eval Negative Industry": {"rich_text": {}},
    "Eval Startup": {"rich_text": {}},
    "Eval Salary Match": {"rich_text": {}},
    "Evaluation Score": {"number": {}},
    # The fields below start off blank, and can be updated in Notion
    "Notes": {"rich_text": {}},
    "Status": {
        "select": {
            "options": [
                {"name": "Triage", "color": "yellow"},
                {"name": "Consider", "color": "orange"},
                {"name": "Apply", "color": "green"},
                {"name": "In Progress", "color": "blue"},
                {"name": "Not interested", "color": "red"},
                {"name": "Rejected", "color": "purple"}
            ]
        }
    }
}

job_posting_property_map = {
    "title": "Title",
    "company_name": "Company Name", 
    "industry": "Industry",
    "location": "Location",
    "salary": "Salary",
    "contract_type": "Contract Type",
    "office_type": "Office Type",
    "company_description": "Company Description",
    "company_size": "Company Size",
    "job_description": "Job Description",
    "skills": "Skills",
    "url": "URL",
    "job_id": "Job ID",
    "search_label": "Search Label",
    "capture_time": "Retrieved At",
    # Evaluation fields
    "eval_role_type": "Eval Role Type",
    "eval_seniority": "Eval Seniority",
    "eval_location": "Eval Location Match",
    "eval_positive_industry": "Eval Positive Industry", 
    "eval_negative_industry": "Eval Negative Industry",
    "eval_startup": "Eval Startup",
    "eval_salary": "Eval Salary Match",
    "evaluation_score": "Evaluation Score"
}




def combine_jobs_and_evaluations(listings: list[JobPosting], evaluations: list[JobEvaluation]) -> list[JobExport]:
    export_data = []
    for job, eval in zip(listings, evaluations):
        d = job.model_dump() | eval.model_dump()
        # Equal weight for all fields
        d['evaluation_score'] = (
            int(eval.eval_role_type == "yes")
            + int(eval.eval_seniority == "yes")
            + int(eval.eval_location == "yes")
            + int(eval.eval_positive_industry == "yes")
            - int(eval.eval_negative_industry == "no")
            + int(eval.eval_startup == "yes")
            + int(eval.eval_salary == "yes")
        )
        export_data.append(JobExport(**d))
    return export_data

async def run_ai_review():
    listings = load_listings()
    llm = OpenAIClient(model="gpt-4o-mini", reqs_per_minute=240)
    evaluations = await evaluate_jobs(listings, llm)
    export_data = combine_jobs_and_evaluations(listings, evaluations)
    with open("data/export_data.json", "w") as f:
        json.dump([job.model_dump() for job in export_data], f, indent=2)
    return export_data


if __name__ == "__main__":
    asyncio.run(run_ai_review())

