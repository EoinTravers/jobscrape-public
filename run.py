import asyncio
from src.scraper import run_scraper
from src.extract import run_extraction
from src.ai_review import run_ai_review
from src.notion import export_to_notion


async def main():
    input("Press Enter to start the scraper...")
    run_scraper()
    input("Press Enter to start the extractor...")
    await run_extraction()
    input("Press Enter to start the AI review...")
    await run_ai_review()
    input("Press Enter to start the Notion export...")
    export_to_notion()

if __name__ == "__main__":
    asyncio.run(main())
