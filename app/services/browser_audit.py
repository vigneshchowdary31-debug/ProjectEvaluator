"""
Browser Audit Service — orchestrates Playwright headless crawling,
capturing screenshots across separate roles (Guest, User, Admin),
detecting broken links, console errors, testing form submissions,
and checking authorization limits.
"""

import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from typing import Any, Dict, List, Optional, Set

import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

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
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCREENSHOT_DIR = os.path.join(BASE_DIR, "screenshots")
HTTP_TIMEOUT = 10.0


class BrowserAuditService:
    """Orchestrates headless browser crawl & RBAC analysis using Playwright."""

    def __init__(self):
        self.drive_service = GoogleDriveService()
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        for role in ("Guest", "User", "Admin"):
            os.makedirs(os.path.join(SCREENSHOT_DIR, role), exist_ok=True)

    async def audit(self, request: BrowserAuditRequest) -> BrowserAuditResponse:
        target_url = request.url.strip()
        max_pages = request.max_pages
        test_forms = request.test_forms
        rbac_enabled = request.rbac_enabled

        audit_id = str(uuid.uuid4())
        logger.info("Starting Browser Audit %s for target: %s (RBAC=%s)", audit_id, target_url, rbac_enabled)

        # Parse base domain
        parsed_target = urlparse(target_url)
        if not parsed_target.scheme:
            target_url = "https://" + target_url
            parsed_target = urlparse(target_url)

        base_domain = parsed_target.netloc
        domain_name = base_domain.replace("www.", "")

        # State tracking
        pages_audited: List[PageAuditResult] = []
        errors_list: List[str] = []
        discovered_internal_urls: Set[str] = {target_url}

        # Google Drive setup
        drive_folder_id = None
        if self.drive_service.enabled:
            try:
                folder_name = f"Audit - {domain_name} - {datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                drive_folder_id = self.drive_service.create_folder(folder_name)
            except Exception as e:
                errors_list.append(f"Google Drive folder setup failed: {str(e)}")

        async with async_playwright() as p:
            logger.info("Launching headless Chromium browser")
            browser: Browser = await p.chromium.launch(headless=True)
            
            try:
                # ── 1. GUEST AUDIT ───────────────────────────────────────────
                logger.info("Starting Guest crawl session")
                guest_urls = [target_url]
                guest_visited = set()
                
                desktop_context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )

                while guest_urls and len(guest_visited) < max_pages:
                    current_url = guest_urls.pop(0)
                    if current_url in guest_visited:
                        continue
                    guest_visited.add(current_url)

                    page_result = await self._audit_page_url(
                        desktop_context, browser, current_url, "Guest", audit_id, len(guest_visited), 
                        base_domain, guest_urls, discovered_internal_urls, test_forms, drive_folder_id
                    )
                    pages_audited.append(page_result)

                await desktop_context.close()

                # ── 2. RBAC MULTI-ROLE CRAWL ──────────────────────────────────
                if rbac_enabled:
                    # Discover login page url path if not explicitly provided
                    login_url = target_url
                    login_paths = ["/login", "/signin", "/admin/login", "/auth/login"]
                    for path in login_paths:
                        for u in discovered_internal_urls:
                            if path in u.lower():
                                login_url = u
                                break

                    # Regular User Session
                    if request.user_email and request.user_password:
                        logger.info("Starting Regular User crawl session")
                        user_context = await browser.new_context(
                            viewport={"width": 1280, "height": 800},
                            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        )
                        # Perform login
                        login_ok = await self._perform_login_test(
                            user_context, login_url, request.user_email, request.user_password, "User", errors_list
                        )
                        if login_ok:
                            # Crawl internal pages under regular user session context
                            user_pages = list(discovered_internal_urls)[:max_pages]
                            for idx, u in enumerate(user_pages):
                                page_result = await self._audit_page_url(
                                    user_context, browser, u, "User", audit_id, idx + 1,
                                    base_domain, [], discovered_internal_urls, False, drive_folder_id
                                )
                                # Check cross-role access limits (e.g. Regular user attempting to hit admin URL)
                                if request.admin_url and request.admin_url in u.lower():
                                    if page_result.status_code and page_result.status_code < 400:
                                        page_result.access_status = "escalated"
                                    else:
                                        page_result.access_status = "blocked"
                                else:
                                    page_result.access_status = "allowed"
                                pages_audited.append(page_result)
                        await user_context.close()

                    # Admin User Session
                    if request.admin_email and request.admin_password:
                        logger.info("Starting Admin crawl session")
                        admin_context = await browser.new_context(
                            viewport={"width": 1280, "height": 800},
                            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        )
                        # Perform login
                        admin_login_url = request.admin_url if request.admin_url else login_url
                        login_ok = await self._perform_login_test(
                            admin_context, admin_login_url, request.admin_email, request.admin_password, "Admin", errors_list
                        )
                        if login_ok:
                            # Crawl pages under admin session context
                            admin_pages = list(discovered_internal_urls)[:max_pages]
                            for idx, u in enumerate(admin_pages):
                                page_result = await self._audit_page_url(
                                    admin_context, browser, u, "Admin", audit_id, idx + 1,
                                    base_domain, [], discovered_internal_urls, False, drive_folder_id
                                )
                                page_result.access_status = "allowed"
                                pages_audited.append(page_result)
                        await admin_context.close()

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

    async def _audit_page_url(
        self, context: BrowserContext, browser: Browser, url: str, role: str, audit_id: str, index: int,
        base_domain: str, queue_list: List[str], discovered_set: Set[str], test_forms: bool, drive_folder_id: Optional[str]
    ) -> PageAuditResult:
        """Helper to navigate and scan an individual URL under a specific role session context."""
        page_result = PageAuditResult(url=url, role=role, access_status="allowed")
        page = await context.new_page()

        console_errors: List[str] = []
        page.on("pageerror", lambda err: console_errors.append(f"JS Exception: {err.message}"))
        page.on("console", lambda msg: console_errors.append(f"Console {msg.type.upper()}: {msg.text}") if msg.type in ("error", "warning") else None)

        # Navigate
        try:
            response = await page.goto(url, wait_until="load", timeout=20000)
            page_result.status_code = response.status if response else 200
        except Exception as ne:
            logger.debug("Page goto error: %s", str(ne))
            page_result.status_code = 0
            page_result.console_errors = [f"Navigation Error: {str(ne)}"]
            await page.close()
            return page_result

        # Wait for idle network state
        try:
            await page.wait_for_load_state("networkidle", timeout=2000)
        except Exception:
            pass

        page_result.console_errors = console_errors

        # Emulate and capture screenshots (Desktop)
        desktop_filename = f"{audit_id}_{role.lower()}_desktop_{index}.png"
        desktop_filepath = os.path.join(SCREENSHOT_DIR, role, desktop_filename)
        try:
            await page.screenshot(path=desktop_filepath, full_page=True)
            if drive_folder_id:
                drive_url = self.drive_service.upload_screenshot(desktop_filepath, desktop_filename, drive_folder_id)
                page_result.desktop_screenshot_url = drive_url
            else:
                page_result.desktop_screenshot_url = f"/api/v1/screenshots/{role}/{desktop_filename}"
        except Exception as se:
            logger.warning("Desktop screenshot failed for %s: %s", url, str(se))

        # Discover Links (only during Guest crawl to find all pages in application)
        if role == "Guest":
            discovered_links: List[str] = []
            try:
                link_elements = await page.query_selector_all("a")
                for element in link_elements:
                    href = await element.get_attribute("href")
                    if href:
                        full_href = urljoin(url, href)
                        clean_href = full_href.split("#")[0].rstrip("/")
                        parsed_href = urlparse(clean_href)
                        
                        if parsed_href.scheme not in ("http", "https"):
                            continue
                            
                        discovered_links.append(clean_href)

                        if parsed_href.netloc == base_domain and clean_href not in discovered_set:
                            discovered_set.add(clean_href)
                            queue_list.append(clean_href)
            except Exception as le:
                logger.warning("Link extraction failed: %s", str(le))

            # Perform link status checks
            broken_links = await self._check_broken_links(discovered_links)
            page_result.broken_links = broken_links

            # Form submission testing
            if test_forms:
                form_results = await self._test_forms_on_page(browser, url)
                page_result.form_submission_results = form_results

        # Emulate and capture screenshots (Mobile)
        mobile_filename = f"{audit_id}_{role.lower()}_mobile_{index}.png"
        mobile_filepath = os.path.join(SCREENSHOT_DIR, role, mobile_filename)
        try:
            mobile_url = await self._capture_mobile_screenshot(browser, page, mobile_filepath, mobile_filename, drive_folder_id, role)
            page_result.mobile_screenshot_url = mobile_url
        except Exception as se:
            logger.warning("Mobile screenshot failed: %s", str(se))

        await page.close()
        return page_result

    async def _capture_mobile_screenshot(
        self, browser: Browser, page: Page, filepath: str, filename: str, drive_folder_id: Optional[str], role: str
    ) -> Optional[str]:
        """Temporarily scales viewport size to capture mobile screenshots on the page context."""
        try:
            original_viewport = page.viewport_size
            # Switch to mobile emulation sizes
            await page.set_viewport_size({"width": 390, "height": 844})
            await page.screenshot(path=filepath, full_page=True)
            # Restore
            if original_viewport:
                await page.set_viewport_size(original_viewport)

            if drive_folder_id:
                return self.drive_service.upload_screenshot(filepath, filename, drive_folder_id)
            return f"/api/v1/screenshots/{role}/{filename}"
        except Exception as e:
            logger.warning("Mobile emulation screenshot failed: %s", str(e))
            return None

    async def _perform_login_test(
        self, context: BrowserContext, login_url: str, email: str, password: str, role: str, errors: List[str]
    ) -> bool:
        """Handles automated form inputs locating, password eye toggles checks, and login submit triggers."""
        logger.info("Executing login test for role: %s on URL: %s", role, login_url)
        page = await context.new_page()
        
        try:
            await page.goto(login_url, wait_until="load", timeout=20000)
            
            # 1. Fill credentials
            email_field = await page.query_selector("input[type='email'], input[name='email'], input[name='username'], input[type='text']")
            password_field = await page.query_selector("input[type='password'], input[name='password']")
            
            if not email_field or not password_field:
                errors.append(f"Login inputs not found for role {role} at {login_url}.")
                await page.close()
                return False

            await email_field.fill(email)
            await password_field.fill(password)

            # 2. Check for password visibility toggle (eye icon button near input)
            buttons = await page.query_selector_all("button, svg, i")
            for btn in buttons:
                try:
                    aria_label = await btn.get_attribute("aria-label") or ""
                    classes = await btn.get_attribute("class") or ""
                    if any(k in aria_label.lower() or k in classes.lower() for k in ("eye", "toggle", "password", "show", "hide")):
                        await btn.click()
                        # Verify type changed
                        pwd_type = await password_field.get_attribute("type")
                        logger.debug("Password visibility toggle tested: type changed to %s", pwd_type)
                        break
                except Exception:
                    pass

            # 3. Trigger submit
            submit_btn = await page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Login'), button:has-text('Sign In')")
            if submit_btn:
                await submit_btn.click()
            else:
                await password_field.press("Enter")

            # Wait for navigation or redirect
            await page.wait_for_timeout(3000)
            
            # Check if login succeeded (not on login URL anymore, or cookies set)
            current_url = page.url
            cookies = await context.cookies()
            
            logger.info("Login outcome for %s: URL = %s, Cookies count = %d", role, current_url, len(cookies))
            await page.close()
            return len(cookies) > 0 or current_url.lower() != login_url.lower()
        except Exception as e:
            errors.append(f"Login test failed for role {role}: {str(e)}")
            await page.close()
            return False

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

            # Test each form (limit to first 2 forms)
            for form in forms[:2]:
                form_id = await form.get_attribute("id")
                form_action = await form.get_attribute("action")
                
                inputs = await form.query_selector_all("input, textarea, select")
                if not inputs:
                    continue

                test_fields: List[FormFieldTestResult] = []
                
                for field in inputs:
                    name = await field.get_attribute("name") or await field.get_attribute("id")
                    if not name:
                        continue
                    
                    type_ = await field.get_attribute("type") or "text"
                    tag_name = await field.evaluate("el => el.tagName.toLowerCase()")
                    
                    val_to_fill = ""
                    if tag_name == "select":
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

                submission_errors: List[str] = []
                page.on("pageerror", lambda err: submission_errors.append(f"JS Error on Submit: {err.message}"))

                success = True
                outcome = "Form filled and submitted successfully."
                try:
                    submit_button = await form.query_selector("button[type='submit'], input[type='submit']")
                    if submit_button:
                        await submit_button.click()
                    else:
                        await form.evaluate("form => form.submit()")
                    await page.wait_for_timeout(2000)
                except Exception as se:
                    success = False
                    outcome = f"Submission action failed: {str(se)}"

                if submission_errors:
                    success = False
                    outcome += f" Encountered console errors: {'; '.join(submission_errors)}"

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
