"""
Browser Audit Service — orchestrates Playwright headless crawling,
capturing screenshots, detecting broken links, console errors,
testing form submissions, and uploading screenshots to Google Drive.
"""

import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from typing import Any, Dict, List, Optional, Set

import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext

from app.schemas.browser_audit import (
    BrowserAuditRequest,
    BrowserAuditResponse,
    PageAuditResult,
    FormSubmissionResult,
    FormFieldTestResult,
)
from app.services.google_drive import GoogleDriveService

logger = logging.getLogger(__name__)

# Directory inside the workspace to temporarily store screenshots
SCREENSHOT_DIR = "/Users/vigneshchowdary/Desktop/project auditor/screenshots"
HTTP_TIMEOUT = 10.0


class BrowserAuditService:
    """Orchestrates headless browser crawl & analysis using Playwright."""

    def __init__(self):
        self.drive_service = GoogleDriveService()
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    async def audit(self, request: BrowserAuditRequest) -> BrowserAuditResponse:
        target_url = request.url.strip()
        max_pages = request.max_pages
        test_forms = request.test_forms

        audit_id = str(uuid.uuid4())
        logger.info("Starting Browser Audit %s for target: %s", audit_id, target_url)

        # Parse base domain
        parsed_target = urlparse(target_url)
        if not parsed_target.scheme:
            target_url = "https://" + target_url
            parsed_target = urlparse(target_url)

        base_domain = parsed_target.netloc
        domain_name = base_domain.replace("www.", "")

        # State tracking
        visited_urls: Set[str] = set()
        urls_to_visit: List[str] = [target_url]
        pages_audited: List[PageAuditResult] = []
        errors_list: List[str] = []

        # Google Drive setup
        drive_folder_id = None
        if self.drive_service.enabled:
            folder_name = f"Audit - {domain_name} - {datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            drive_folder_id = self.drive_service.create_folder(folder_name)
            if not drive_folder_id:
                errors_list.append("Failed to create Google Drive folder. Screenshots saved locally.")

        # Playwright Execution
        async with async_playwright() as p:
            logger.info("Launching headless Chromium browser")
            browser: Browser = await p.chromium.launch(headless=True)

            try:
                # Desktop Viewport Context
                desktop_context: BrowserContext = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )

                while urls_to_visit and len(visited_urls) < max_pages:
                    current_url = urls_to_visit.pop(0)
                    if current_url in visited_urls:
                        continue

                    logger.info("Auditing page %d/%d: %s", len(visited_urls) + 1, max_pages, current_url)
                    visited_urls.add(current_url)

                    # Initialize result collector
                    page_result = PageAuditResult(url=current_url)

                    # 1. Open Page and Intercept Errors
                    page = await desktop_context.new_page()
                    
                    console_errors: List[str] = []
                    page.on("pageerror", lambda err: console_errors.append(f"JS Exception: {err.message}"))
                    page.on("console", lambda msg: console_errors.append(f"Console {msg.type.upper()}: {msg.text}") if msg.type in ("error", "warning") else None)

                    # Navigate
                    response = None
                    try:
                        response = await page.goto(current_url, wait_until="load", timeout=30000)
                        page_result.status_code = response.status if response else 200
                    except Exception as ne:
                        logger.error("Navigation failed for %s: %s", current_url, str(ne))
                        page_result.status_code = 0
                        page_result.console_errors = [f"Navigation Error: {str(ne)}"]
                        pages_audited.append(page_result)
                        await page.close()
                        continue

                    # Wait for network idle to catch delayed console errors
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass  # Swallow networkidle timeouts

                    page_result.console_errors = console_errors

                    # 2. Capture Desktop Screenshot
                    desktop_filename = f"{audit_id}_desktop_{len(visited_urls)}.png"
                    desktop_filepath = os.path.join(SCREENSHOT_DIR, desktop_filename)
                    try:
                        await page.screenshot(path=desktop_filepath, full_page=True)
                        if drive_folder_id:
                            drive_url = self.drive_service.upload_screenshot(desktop_filepath, desktop_filename, drive_folder_id)
                            page_result.desktop_screenshot_url = drive_url
                        else:
                            page_result.desktop_screenshot_url = f"/screenshots/{desktop_filename}"
                    except Exception as se:
                        logger.error("Failed to capture desktop screenshot: %s", str(se))
                        errors_list.append(f"Desktop screenshot failed on {current_url}: {str(se)}")

                    # 3. Scrape and Check Links (Broken Link Detection)
                    discovered_links: List[str] = []
                    try:
                        link_elements = await page.query_selector_all("a")
                        for element in link_elements:
                            href = await element.get_attribute("href")
                            if href:
                                full_href = urljoin(current_url, href)
                                # Clean trailing slash/hashes
                                clean_href = full_href.split("#")[0].rstrip("/")
                                parsed_href = urlparse(clean_href)
                                
                                # Skip non-http schemes
                                if parsed_href.scheme not in ("http", "https"):
                                    continue
                                    
                                discovered_links.append(clean_href)

                                # If internal link, add to queue
                                if parsed_href.netloc == base_domain and clean_href not in visited_urls and clean_href not in urls_to_visit:
                                    if len(visited_urls) + len(urls_to_visit) < max_pages * 2: # Keep queue size bounded
                                        urls_to_visit.append(clean_href)
                    except Exception as le:
                        logger.warning("Failed to extract links from %s: %s", current_url, str(le))

                    # Perform link status checks
                    broken_links = await self._check_broken_links(discovered_links)
                    page_result.broken_links = broken_links

                    # 4. Form Submission Testing (isolated execution on new page context)
                    if test_forms:
                        form_results = await self._test_forms_on_page(browser, current_url)
                        page_result.form_submission_results = form_results

                    await page.close()

                    # 5. Mobile emulation and screenshot
                    mobile_result_url = await self._capture_mobile_screenshot(
                        browser, current_url, audit_id, len(visited_urls), drive_folder_id
                    )
                    page_result.mobile_screenshot_url = mobile_result_url

                    # Add page findings
                    pages_audited.append(page_result)

                await desktop_context.close()

            except Exception as e:
                logger.error("Audit loop crashed: %s", str(e))
                errors_list.append(f"Audit loop crashed: {str(e)}")
            finally:
                logger.info("Closing browser session")
                await browser.close()

        # Build response
        drive_folder_url = self.drive_service.get_folder_link(drive_folder_id) if drive_folder_id else None
        
        response = BrowserAuditResponse(
            audit_id=audit_id,
            target_url=target_url,
            pages_audited=pages_audited,
            total_pages_visited=len(pages_audited),
            drive_folder_url=drive_folder_url,
            errors=errors_list,
            created_at=datetime.now(timezone.utc).isoformat()
        )

        logger.info("Browser Audit %s complete — %d pages audited", audit_id, len(pages_audited))
        return response

    async def _capture_mobile_screenshot(
        self, browser: Browser, url: str, audit_id: str, index: int, drive_folder_id: Optional[str]
    ) -> Optional[str]:
        """Runs in iPhone emulation context to capture a mobile screenshot."""
        logger.debug("Emulating mobile device for screenshot of: %s", url)
        try:
            mobile_context = await browser.new_context(
                viewport={"width": 390, "height": 844},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
                is_mobile=True,
                has_touch=True
            )
            page = await mobile_context.new_page()
            await page.goto(url, wait_until="load", timeout=20000)
            
            mobile_filename = f"{audit_id}_mobile_{index}.png"
            mobile_filepath = os.path.join(SCREENSHOT_DIR, mobile_filename)
            await page.screenshot(path=mobile_filepath, full_page=True)
            await page.close()
            await mobile_context.close()

            if drive_folder_id:
                return self.drive_service.upload_screenshot(mobile_filepath, mobile_filename, drive_folder_id)
            return f"/screenshots/{mobile_filename}"
        except Exception as e:
            logger.warning("Mobile emulation failed for %s: %s", url, str(e))
            return None

    async def _check_broken_links(self, urls: List[str]) -> List[str]:
        """Perform rapid HTTP status code queries on discovered links to find broken links."""
        broken: List[str] = []
        unique_urls = list(set(urls))[:15]  # Cap link checking to 15 unique links per page to keep it fast
        
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            tasks = [self._check_url_status(client, u) for u in unique_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for u, res in zip(unique_urls, results):
                if isinstance(res, Exception) or res >= 400:
                    broken.append(u)
        return broken

    async def _check_url_status(self, client: httpx.AsyncClient, url: str) -> int:
        try:
            # First try HEAD to save bandwidth
            response = await client.head(url)
            if response.status_code == 405: # Method not allowed, fallback to GET
                response = await client.get(url)
            return response.status_code
        except Exception:
            return 500

    async def _test_forms_on_page(self, browser: Browser, url: str) -> List[FormSubmissionResult]:
        """Detect and fill forms on a separate tab context to test submission behaviors."""
        results: List[FormSubmissionResult] = []
        try:
            # Separate context for form testing
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(url, wait_until="load", timeout=20000)

            # Discover forms
            forms = await page.query_selector_all("form")
            if not forms:
                await page.close()
                await context.close()
                return results

            logger.info("Found %d form(s) to test on %s", len(forms), url)

            # Test each form
            for i, form in enumerate(forms):
                form_id = await form.get_attribute("id")
                form_action = await form.get_attribute("action")
                
                # Check fields
                inputs = await form.query_selector_all("input, textarea, select")
                if not inputs:
                    continue

                test_fields: List[FormFieldTestResult] = []
                
                # Fill fields
                for field in inputs:
                    name = await field.get_attribute("name") or await field.get_attribute("id")
                    if not name:
                        continue
                    
                    type_ = await field.get_attribute("type") or "text"
                    tag_name = await field.evaluate("el => el.tagName.toLowerCase()")
                    
                    val_to_fill = ""
                    if tag_name == "select":
                        # Pick first option
                        options = await field.query_selector_all("option")
                        if options:
                            val_to_fill = await options[0].get_attribute("value") or ""
                            try:
                                await field.select_option(value=val_to_fill)
                            except Exception:
                                pass
                    elif type_ == "email":
                        val_to_fill = "test-audit@example.com"
                        await field.fill(val_to_fill)
                    elif type_ == "password":
                        val_to_fill = "AuditPass123!"
                        await field.fill(val_to_fill)
                    elif type_ == "number":
                        val_to_fill = "1"
                        await field.fill(val_to_fill)
                    elif type_ in ("text", "textarea"):
                        val_to_fill = "Test input data"
                        await field.fill(val_to_fill)

                    test_fields.append(FormFieldTestResult(
                        field_name=name,
                        field_type=type_ if tag_name == "input" else tag_name,
                        value_filled=val_to_fill
                    ))

                # Capture console logs during submission
                submission_errors: List[str] = []
                page.on("pageerror", lambda err: submission_errors.append(f"JS Error on Submit: {err.message}"))

                # Click submit
                success = True
                outcome = "Form filled and submitted successfully."
                try:
                    submit_button = await form.query_selector("button[type='submit'], input[type='submit']")
                    if submit_button:
                        await submit_button.click()
                    else:
                        # Fallback: dispatch submit event
                        await form.evaluate("form => form.submit()")
                        
                    # Wait for navigation or state changes
                    await page.wait_for_timeout(2000)
                except Exception as se:
                    success = False
                    outcome = f"Submission action failed: {str(se)}"

                if submission_errors:
                    success = False
                    outcome += f" Encounted console errors: {'; '.join(submission_errors)}"

                results.append(FormSubmissionResult(
                    form_id=form_id,
                    form_action=form_action,
                    fields_tested=test_fields,
                    success=success,
                    outcome=outcome
                ))

            await page.close()
            await context.close()

        except Exception as e:
            logger.warning("Form testing failed on %s: %s", url, str(e))
            
        return results
