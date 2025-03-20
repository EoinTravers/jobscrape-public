import os
import hashlib
from typing import Any
from time import sleep

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from .typedefs import RawPage, PageSaver


class LinkedinScraper:
    def __init__(self) -> None:
        options = webdriver.ChromeOptions()
        self.driver: WebDriver = webdriver.Chrome(options=options)

    def run(self, callback: PageSaver) -> None:
        self.login()
        self.ingest_search_results(callback)

    def login(self) -> None:
        """Log in to LinkedIn using credentials in .env"""
        load_dotenv()
        EMAIL, PASSWORD = os.getenv("LINKEDIN_EMAIL"), os.getenv("LINKEDIN_PASSWORD")
        if not EMAIL or not PASSWORD:
            raise ValueError("LINKEDIN_EMAIL and LINKEDIN_PASSWORD must be set")
        self.driver.get("https://www.linkedin.com/login?fromSignIn=true")
        sleep(2)
        username = self.driver.find_element("id", "username")
        username.send_keys(EMAIL)
        password = self.driver.find_element("id", "password")
        password.send_keys(PASSWORD)
        btn = self.driver.find_element(
            "xpath", "/html/body/div/main/div[3]/div[1]/form/div[4]/button"
        )
        sleep(2)
        btn.click()

    def get_current_page(self, metadata: dict[str, Any] | None = None) -> RawPage:
        """Get contents of currently open page"""
        WebDriverWait(self.driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return RawPage(
            url=self.driver.current_url,
            title=self.driver.title,
            html=self.driver.page_source,
            metadata=metadata,
        )


    def ingest_search_results(self, callback: PageSaver) -> None:
        """
        Click through and save all jobs from a search results page.
        You'll need to enter a label at the terminal before this starts.

        args:
            callback: a function that takes each job page and processes it (e.g. saves it)
        """
        print("""
        # Instructions
              
        1. Navigate to the search results page.
        2. In this terminal, type in a label for your search and hit RETURN.
        3. Sit back and watch.
        """)
        # Note: Using callbacks here, but a generator is probably nicer
        search_label = input("[Enter label]: ")
        n_jobs = 0
        page_nr = 1
        print("Starting...")
        while True:
            links = self.driver.find_elements(By.CSS_SELECTOR, "div.job-card-container")
            for link in links:
                self.click(link)
                sleep(1)
                callback(self.get_current_page(metadata={"search_label": search_label}))
                n_jobs += 1
                if n_jobs % 5 == 0:
                    print(f"Saved {n_jobs} jobs")
            try:
                next_btn = self.driver.find_element(
                    By.CSS_SELECTOR, 'button[aria-label="View next page"]'
                )
                self.click(next_btn)
                sleep(1)
                page_nr += 1
                print(f"Moving to page {page_nr}")
            except NoSuchElementException:
                break
        inp = input("Run again? (y/n)")
        if inp[0].lower() == "y":
            self.ingest_search_results(callback)
        else:
            print("Done.")
            input("Press Enter to exit...")

    def click(self, el, retries=1, delay=2.0) -> None:
        """Click an element, with retries"""
        try:
            el.click()
        except Exception as e:
            if retries > 0:
                sleep(delay)
                self.click(el, retries - 1, delay)
            else:
                raise e

    def watch(self, callback: PageSaver) -> None:
        """After calling this, any pages visited during normal browsing will be saved"""
        last_url = None
        while True:
            try:
                current_url = self.driver.current_url
                if current_url != last_url and self._is_job_page(current_url):
                    print(f"Downloading job description: {current_url}")
                    page = self.get_current_page()
                    callback(page)
                    last_url = current_url
                sleep(0.5)
            except KeyboardInterrupt:
                break

    def _get_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash of content to detect changes"""
        return hashlib.sha256(content.encode()).hexdigest()

    def _is_job_page(self, url: str) -> bool:
        return (
            url.find("https://www.linkedin.com/jobs/") == 0
            and url.find("currentJobId") > 0
        )


def run_scraper():
    from .db import DB
    scraper = LinkedinScraper()
    db = DB()
    db.setup_database()
    scraper.run(callback=db.save_page)


if __name__ == "__main__":
    run_scraper()