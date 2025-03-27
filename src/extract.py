import json
import os
import sqlite3
from typing import Literal
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import pandas as pd
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from src.llm import OpenAIClient
from src.notion import get_existing_job_ids
from src.typedefs import ExtractedJobPosting, JobPosting
"""
Logic for extracting data from job posting pages
"""


def field(description: str):
    return Field(description=description)


def parse_metadata(x):
    """Only needed temporarily, later data will be valid JSON"""
    if x and x != "None":
        x = x.replace("'", '"')
        return json.loads(x)
    return {}


def read_from_db(
    db_path: str = "data/jobsearch.db", table_name: str = "pages"
) -> pd.DataFrame:
    conn: sqlite3.Connection = sqlite3.connect(db_path)
    data: pd.DataFrame = pd.read_sql_query(
        f"SELECT * FROM {table_name}", conn, parse_dates=["capture_time"]
    )
    data["metadata"] = data["metadata"].map(parse_metadata)
    conn.close()
    return data


def get_listing_text(html: str) -> str:
    """Extract job listing from HTML of a linkedin job page"""
    soup = BeautifulSoup(html, "html.parser")
    if soup.body is None:
        raise ValueError("HTML has no body")
    details = soup.body.find(class_="jobs-search__job-details--wrapper")
    if details is None:
        raise ValueError("No job details element found")
    crap_classes = [
        "job-details-connections-card",
        "jobs-premium-applicant-insights",
        "highcharts-wrapper",
    ]
    for cls in crap_classes:
        instances = details.find_all(class_=cls)  # type: ignore
        for x in instances:
            x.decompose()
    return details.get_text(separator="\n", strip=True)





async def extract_listings(
    data: pd.DataFrame, llm: OpenAIClient
) -> tuple[pd.DataFrame, list[JobPosting]]:
    data["listing_text"] = data["html"].map(get_listing_text)
    prompt = """
    Below, you are provided with a job advert.
    Extract the information from the job advert and return it in the structure specified.

    Be aware that some adverts will be posted by a recruitement agency, and for these roles,
    the "About the company" information will refer to the agency, not the company offering the role.
    If this is the case, ignore the "About the company" information and extract the relevant information
    from the job description.
    """
    results: list[ExtractedJobPosting] = await llm.llm_batch(
        prompt,
        data["listing_text"].tolist(),
        response_format=ExtractedJobPosting,
        progress_bar=True,
    )  # type: ignore
    data["listing_info"] = [listing_to_text(r) for r in results]
    # Attach additional fields from the dataframe to the listings
    listings = []
    for (i, row), listing in zip(data.iterrows(), results):
        x = listing.model_dump() | row.to_dict()
        x["capture_time"] = x["capture_time"].strftime("%Y-%m-%d %H:%M:%S")
        listings.append(JobPosting(**x))
    return data, listings


def pretty_string(s: str) -> str:
    return s.replace("_", " ").title()


def listing_to_text(listing: ExtractedJobPosting) -> str:
    fields = [
        "job_title",
        "company_name",
        "industry",
        "location",
        "salary",
        "contract_type",
        "office_type",
        "company_description",
        "company_size",
        "job_description",
        "skills",
    ]
    return "\n".join([f"{pretty_string(f)}: {getattr(listing, f)}" for f in fields])


def get_url_params(url: str, param: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return params[param][0]


def get_job_id(url: str) -> str:
    return get_url_params(url, "currentJobId")


def get_existing_listings():
    """Get IDs for listings that are already in the Notion database"""


async def run_extraction():
    data = read_from_db("data/jobsearch.db", "pages")
    llm = OpenAIClient(model="gpt-4o-mini")
    if not isinstance(data["metadata"].iloc[-1], dict):
        data["metadata"] = data["metadata"].apply(parse_metadata)
    # Remove duplicates
    existing_job_ids = get_existing_job_ids(os.getenv("NOTION_DB_ID"))
    n = len(data)
    data["job_id"] = data["url"].apply(get_job_id)
    data = data[~data["job_id"].isin(existing_job_ids)]
    data = data[~data["job_id"].duplicated()]
    print(f"Removed {n - len(data)} duplicates -> {len(data)} listings remaining")
    data["search_label"] = data["metadata"].map(lambda x: x["search_label"])
    data, results = await extract_listings(data, llm)
    data.to_csv("data/listings.csv", index=False)
    with open("data/listings.json", "w") as f:
        json.dump([r.model_dump() for r in results], f, indent=2)


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_extraction())
