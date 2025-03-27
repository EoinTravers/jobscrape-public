from typing import Callable, Any, Literal
from pydantic import BaseModel, Field

def field(description: str):
    """Save a few keystrokes"""
    return Field(description=description)



class RawPage(BaseModel):
    url: str
    title: str
    html: str
    metadata: dict[str, Any] | None = None


PageSaver = Callable[[RawPage], Any]


# Extraction
class ExtractedJobPosting(BaseModel):
    job_title: str
    company_name: str
    industry: str | None = field(
        "Industry for the role, e.g. 'Finance', 'Health', 'Education', etc."
    )
    location: str
    salary: str | None = field("e.g. '£100,000 - £120,000'")
    contract_type: Literal["permanent", "fixed contract", "UNKNOWN"]
    office_type: Literal["office", "hybrid", "remote", "UNKNOWN"]
    # More open-ended stuff
    company_description: str = field("What does the company do? One sentence.")
    company_size: str | None
    job_description: str = field("What does the job entail? One sentence.")
    skills: str = field(
        "What skills are required for the job? One sentence, be concise"
    )


class JobPosting(ExtractedJobPosting):
    # Adds additional properties for export
    title: str = Field(alias="job_title")
    job_id: str
    url: str
    search_label: str
    capture_time: str

# Review

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
