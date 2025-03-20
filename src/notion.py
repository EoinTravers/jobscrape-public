import json
import os
from datetime import datetime
from typing import Any

from notion_client import Client as NotionClient
from notion_client import APIResponseError

from .ai_review import JobExport


# Generic resources
def create_notion_database(
    notion_client: NotionClient,
    parent_page_id: str,
    database_schema: dict,
    title: str = "New Database",
):
    """
    Create a new Notion database with a given schema

    Args:
        notion_client: Initialized Notion client
        parent_page_id (str): ID of the parent page where database will be created
    """

    database = notion_client.databases.create(
        parent={"page_id": parent_page_id},
        is_inline=True,  # Create as a board
        title=[{"type": "text", "text": {"content": title}}],
        properties=database_schema,
    )
    # Would be nice to create a nice view here, but not possible with API.
    return database["id"]


def ensure_notion_database(
    notion_client: NotionClient,
    parent_page_id: str,
    database_schema: dict,
    title: str = "New Database",
    database_id: str | None = None,
):
    """
    Ensure the Notion database exists, create if it doesn't

    Args:
        notion_client: Initialized Notion client
        parent_page_id (str): ID of the parent page
        database_id (str, optional): Existing database ID

    Returns:
        str: Database ID
    """
    if database_id:
        try:
            # Check if database exists
            notion_client.databases.retrieve(database_id)
            return database_id
        except APIResponseError:
            print("Database not found, creating new one...")
            return create_notion_database(
                notion_client, parent_page_id, database_schema, title
            )


def value_to_notion(key: str, value: Any) -> dict:
    """Convert a Python value to Notion property format based on type.
    NB: There is special behaviour hard-coded for keys in ["title", "url"]
    """
    if key == "title":
        return {"title": [{"text": {"content": str(value)}}]}
    elif key == "url":
        return {"url": value}
    elif isinstance(value, datetime):
        return {"date": {"start": value.isoformat()}}
    elif isinstance(value, (int, float)):
        return {"number": value}
    elif isinstance(value, str):
        return {"rich_text": split_long_rich_text(value)}
    if value is None:
        return {"rich_text": [{"text": {"content": ""}}]}
    else:
        raise ValueError(f"Unsupported type for key {key}: {type(value)}")


def split_long_rich_text(content: str):
    """Split text of >2,000 chars into multiple elements.
    This is necessary because of how Notion handles long text internally.
    """
    if len(content) < 2000:
        return [{"text": {"content": content}}]
    else:
        chunks = content.split("\n")
        # If any chunk is still too long, split it on sentences
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > 2000:
                # Split on periods followed by spaces
                sentences = chunk.split(". ")
                current_chunk = ""
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 2 <= 2000:  # +2 for '. '
                        current_chunk += sentence + ". "
                    else:
                        if current_chunk:
                            final_chunks.append(current_chunk.rstrip())
                        current_chunk = sentence + ". "
                if current_chunk:
                    final_chunks.append(current_chunk.rstrip())
            else:
                final_chunks.append(chunk)
        return [{"text": {"content": chunk}} for chunk in final_chunks if chunk.strip()]


# Specific to this use-case
def load_export_data(fp: str = "data/export_data.json"):
    with open(fp, "r") as f:
        export_data = json.load(f)
    export_data = [JobExport(**d) for d in export_data]
    return export_data


def job_posting_to_notion_page(
    property_label_map: dict, job_posting: JobExport, default_status: str | None = None
) -> dict:
    """Generate an appropriately-structured dictionary given a JobExport instance.
    
    Args:
        property_label_map (dict): A dictionary mapping property keys to their labels
        job_posting (JobExport): A JobExport instance
        default_status (str, optional): The default status to set for the job posting

    Returns:
        dict: A dictionary of properties to be added to the Notion page
    """
    # Convert the price to Notion currency format
    record = job_posting.model_dump()
    record["capture_time"] = datetime.strptime(
        record["capture_time"], "%Y-%m-%d %H:%M:%S"
    )
    properties = {
        property_label_map[k]: value_to_notion(k, v)
        for k, v in record.items()
        if k in property_label_map
    }

    # Add default status
    if default_status:
        properties["Status"] = {"select": {"name": default_status}}
    return properties


def add_job_posting_to_notion(
    notion_client: NotionClient,
    database_id: str,
    job_posting: JobExport,
    job_posting_property_map: dict,
    default_status: str | None = None,
):  
    """Takes a JobExport, adds it to Notion database.
    
    Args:
        notion_client: The Notion client
        database_id: The ID of the database to add the job posting to
        job_posting: The job posting to add
        job_posting_property_map: A dictionary mapping property keys to their labels
        default_status: The default status to set for the job posting (this might not work)
    """
    properties = job_posting_to_notion_page(
        job_posting_property_map, job_posting, default_status
    )
    # Add the record to Notion
    try:
        notion_client.pages.create(
            parent={"database_id": database_id},
            properties=properties,
        )
        return True
    except Exception as e:
        raise e
        # print(f"Error adding record to Notion: {e}")
        # return False


def export_to_notion():
    from .ai_review import job_posting_property_map
    from dotenv import load_dotenv
    load_dotenv()

    notion_api_key, notion_page_id, notion_db_id = [
        os.getenv(k) for k in ["NOTION_API_KEY", "NOTION_PAGE_ID", "NOTION_DB_ID"]
    ]
    notion_client = NotionClient(auth=notion_api_key)
    if notion_page_id is None:
        print("""
              No NOTION_PAGE_ID found in environment variables.
              Please create a page to export your data to, make sure your integration has access to it,
              and paste the page ID below.
              The page ID is the long string of characters at the end of the page URL, e.g. 1b8aae00fd368066b3f1e6285a318bb7
              You should also add this variable to the .env file.
              """)
        notion_page_id = input("Enter the page ID: ")
    if notion_db_id is None:
        print("""
              No NOTION_PAGE_ID found in environment variables.
              Creating a new database in the page specified.""")
        notion_db_id = create_notion_database(
            notion_client,
            parent_page_id=notion_page_id,
            database_schema=job_posting_property_map,
            title="Jobs"
        )
    print(f"Notion database created with id: {notion_db_id}.")
    print(f"Please add NOTION_DB_ID={notion_db_id} to your .env file.")
    print("Starting Export")
    export_data = load_export_data()
    for listing in export_data:
        print(listing.title)
        add_job_posting_to_notion(
            job_posting_property_map=job_posting_property_map,
            notion_client=notion_client,
            database_id=notion_db_id,
            job_posting=listing
        )

if __name__ == "__main__":
    export_to_notion()
