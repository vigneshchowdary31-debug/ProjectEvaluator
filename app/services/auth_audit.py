"""
Authentication Audit Service — tests login forms, authentication strength,
session management, and crawls pages behind login for audited projects.
"""

import os
import uuid
import logging
import json
import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from playwright.async_api import Browser, BrowserContext, Page

from app.schemas.browser_audit import PageAuditResult
from app.services.google_drive import GoogleDriveService

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCREENSHOT_DIR = os.path.join(BASE_DIR, "screenshots")


class AuthenticationAuditService:
    """Orchestrates authentication checks, session security audits, and authenticated crawling."""

    def __init__(self):
        self.drive_service = GoogleDriveService()
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        os.makedirs(os.path.join(SCREENSHOT_DIR, "Authenticated"), exist_ok=True)

    async def run_auth_audit(
        self,
        browser: Browser,
        target_url: str,
        login_url: Optional[str],
        email: str,
        password: str,
        max_pages: int,
        audit_id: str,
        drive_folder_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        Executes the entire authenticated audit sequence.
        Returns a dict conforming to the AuthAuditResult DB model.
        """
        logger.info("Starting Authenticated Audit sequence for: %s", target_url)

        # Parse base domain
        parsed_target = urlparse(target_url)
        base_domain = parsed_target.netloc

        # 1. Login Discovery
        login_url_used = login_url
        if not login_url_used:
            login_url_used = await self._discover_login_url(browser, target_url)
        logger.info("Resolved login URL for testing: %s", login_url_used)

        # Results status tracking
        login_success = False
        logout_success = False
        session_persisted = False
        invalid_password_rejected = True
        empty_creds_rejected = True
        routes_protected = True
        redirect_after_login = None
        redirect_after_logout = None
        protected_routes_found_list = []
        protected_routes_audited_count = 0
        authenticated_pages: List[PageAuditResult] = []
        findings = []

        # Temp contexts for safety tests
        # A. Empty credentials test
        empty_creds_rejected = await self._test_empty_credentials(browser, login_url_used)
        if not empty_creds_rejected:
            findings.append({
                "category": "AUTH",
                "title": "Empty Credentials Accepted",
                "description": f"The login form at {login_url_used} accepted submission and did not enforce client/server-side validation errors when credentials were empty.",
                "severity": "high",
                "recommendation": "Implement front-end HTML5 'required' field constraints and back-end schema validation to reject blank submissions."
            })

        # B. Invalid password test
        invalid_password_rejected = await self._test_invalid_password(browser, login_url_used, email)
        if not invalid_password_rejected:
            findings.append({
                "category": "AUTH",
                "title": "Invalid Password Accepted",
                "description": f"The login form at {login_url_used} allowed logging in or redirecting to a dashboard session even when a wrong password was provided.",
                "severity": "critical",
                "recommendation": "Enforce strict hash comparison during credential verification on the backend and reject logins with wrong passwords."
            })

        # 2. Main Authenticated Session
        auth_context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        login_success, redirect_after_login, login_page = await self._perform_login(
            auth_context, login_url_used, email, password
        )

        if not login_success:
            logger.warning("Authentication failed using provided credentials at %s", login_url_used)
            findings.append({
                "category": "AUTH",
                "title": "Authentication Form Submission Failure",
                "description": f"The crawler was unable to log in at {login_url_used} with the provided credentials. The system returned validation failures or failed to redirect.",
                "severity": "high",
                "recommendation": "Verify credentials and selector configurations. Check console logs for form handler or API errors."
            })
            await auth_context.close()
            return {
                "status": "FAILED",
                "login_success": False,
                "logout_success": False,
                "session_persisted": False,
                "invalid_password_rejected": invalid_password_rejected,
                "empty_creds_rejected": empty_creds_rejected,
                "routes_protected": False,
                "redirect_after_login": None,
                "redirect_after_logout": None,
                "protected_routes_found": 0,
                "protected_routes_audited": 0,
                "auth_score": 0.0,
                "login_url_used": login_url_used,
                "findings": json.dumps(findings),
                "protected_routes": "[]",
                "authenticated_pages_audited": []
            }

        # C. Session Persistence Test
        session_persisted = await self._test_session_persistence(auth_context, redirect_after_login or target_url)
        if not session_persisted:
            findings.append({
                "category": "SESSION",
                "title": "Session Persistence Failure",
                "description": "The session was lost when opening a new page tab in the same browser context, requiring the user to re-authenticate.",
                "severity": "medium",
                "recommendation": "Ensure authentication tokens are persisted in secure cookies or storage (e.g. SessionStorage) that persist across tabs."
            })

        # D. Discover Protected Routes
        discovered_routes = await self._discover_protected_routes(login_page, redirect_after_login or target_url, base_domain)
        logger.info("Discovered protected routes: %s", discovered_routes)

        # Close the login page reference we used for discovery
        try:
            await login_page.close()
        except Exception:
            pass

        # E. Test Route Protection (broken access control check)
        unprotected_routes = []
        if discovered_routes:
            unprotected_routes = await self._test_routes_protection(browser, discovered_routes)
            if unprotected_routes:
                routes_protected = False
                for route in unprotected_routes:
                    findings.append({
                        "category": "PROTECTED_ROUTE",
                        "title": f"Broken Access Control: Unprotected Route ({route})",
                        "description": f"The page path {route} was successfully accessed with HTTP 200 without active session cookies or authentication tokens.",
                        "severity": "high",
                        "recommendation": "Enforce backend session validation middleware for this route and redirect unauthenticated requests to the login page."
                    })

        # F. Authenticated Crawl
        # Visit up to max_pages of these discovered routes
        routes_to_audit = list(discovered_routes)[:max_pages]
        protected_routes_found_list = []
        
        for idx, route in enumerate(routes_to_audit):
            page_result = await self._audit_authenticated_page(
                auth_context, browser, route, audit_id, idx + 1, base_domain, drive_folder_id
            )
            authenticated_pages.append(page_result)
            protected_routes_audited_count += 1

            status = "ACCESSED"
            if page_result.status_code and page_result.status_code >= 400:
                status = "BLOCKED"
            elif route in unprotected_routes:
                status = "ACCESSED"  # Accessible unauthenticated
            else:
                # If redirected to login, mark as REDIRECTED
                pass

            protected_routes_found_list.append({
                "route": route,
                "status": status,
                "screenshot_url": page_result.desktop_screenshot_url
            })

        # G. Logout Test
        logout_success, redirect_after_logout = await self._test_logout(auth_context, redirect_after_login or target_url)
        if not logout_success:
            findings.append({
                "category": "SESSION",
                "title": "Logout Invalidation Failure",
                "description": "The crawler clicked a logout button, but cookies or session keys were not cleared, leaving the session open.",
                "severity": "medium",
                "recommendation": "When logging out, clear session cookies/localStorage on the client side and invalidate the token on the server side."
            })

        await auth_context.close()

        # Score calculation
        auth_score = 100.0
        if not login_success:
            auth_score = 0.0
        else:
            if not empty_creds_rejected:
                auth_score -= 15.0
            if not invalid_password_rejected:
                auth_score -= 30.0
            if not session_persisted:
                auth_score -= 15.0
            if not logout_success:
                auth_score -= 15.0
            if not routes_protected:
                # Penalty based on number of unprotected routes, capped at 25
                auth_score -= min(25.0, len(unprotected_routes) * 10.0)

        auth_score = max(0.0, min(100.0, auth_score))

        return {
            "status": "SUCCESS" if (login_success and len(findings) == 0) else ("PARTIAL" if login_success else "FAILED"),
            "login_success": login_success,
            "logout_success": logout_success,
            "session_persisted": session_persisted,
            "invalid_password_rejected": invalid_password_rejected,
            "empty_creds_rejected": empty_creds_rejected,
            "routes_protected": routes_protected,
            "redirect_after_login": redirect_after_login,
            "redirect_after_logout": redirect_after_logout,
            "protected_routes_found": len(discovered_routes),
            "protected_routes_audited": protected_routes_audited_count,
            "auth_score": auth_score,
            "login_url_used": login_url_used,
            "findings": json.dumps(findings),
            "protected_routes": json.dumps(protected_routes_found_list),
            "authenticated_pages_audited": authenticated_pages
        }

    async def _discover_login_url(self, browser: Browser, target_url: str) -> str:
        """Attempts to auto-detect a login URL from the target application."""
        login_paths = ["/login", "/signin", "/auth/login", "/auth", "/account/login"]
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            for path in login_paths:
                test_url = urljoin(target_url, path)
                try:
                    res = await client.get(test_url)
                    if res.status_code == 200:
                        return test_url
                except Exception:
                    pass
        return target_url

    async def _perform_login(
        self, context: BrowserContext, login_url: str, email: str, password: str
    ) -> Tuple[bool, Optional[str], Optional[Page]]:
        """Log in to the application and return status + landing page."""
        page = await context.new_page()
        try:
            await page.goto(login_url, wait_until="load", timeout=20000)
            await page.wait_for_timeout(2000)

            email_field = await page.query_selector("input[type='email'], input[name='email'], input[name='username'], input[type='text']")
            password_field = await page.query_selector("input[type='password'], input[name='password']")

            if not email_field or not password_field:
                return False, None, page

            await email_field.fill(email)
            await password_field.fill(password)

            # Try visibility toggle test if button found
            try:
                buttons = await page.query_selector_all("button, svg, i")
                for btn in buttons:
                    aria_label = await btn.get_attribute("aria-label") or ""
                    classes = await btn.get_attribute("class") or ""
                    if any(k in aria_label.lower() or k in classes.lower() for k in ("eye", "toggle", "password", "show", "hide")):
                        await btn.click()
                        break
            except Exception:
                pass

            # Submit
            submit_btn = await page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Login'), button:has-text('Sign In')")
            if submit_btn:
                await submit_btn.click()
            else:
                await password_field.press("Enter")

            await page.wait_for_timeout(4000)
            
            cookies = await context.cookies()
            current_url = page.url

            # Consider login successful if URL changed, cookie count > 0, or dashboard keywords found
            success = len(cookies) > 0 or current_url.lower() != login_url.lower()
            return success, current_url, page

        except Exception as e:
            logger.error("Authentication execution failed: %s", str(e))
            return False, None, page

    async def _test_empty_credentials(self, browser: Browser, login_url: str) -> bool:
        """Verifies if login fails or is rejected with empty credentials."""
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(login_url, wait_until="load", timeout=15000)
            submit_btn = await page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Login'), button:has-text('Sign In')")
            if submit_btn:
                await submit_btn.click()
            else:
                # Trigger enter on password or email field if we find it
                pwd = await page.query_selector("input[type='password']")
                if pwd:
                    await pwd.press("Enter")
            
            await page.wait_for_timeout(2000)
            cookies = await context.cookies()
            current_url = page.url
            
            # If cookies are set or URL changed away from login, empty creds were NOT rejected!
            if len(cookies) > 0 or current_url.lower() != login_url.lower():
                return False
            return True
        except Exception:
            return True
        finally:
            await context.close()

    async def _test_invalid_password(self, browser: Browser, login_url: str, email: str) -> bool:
        """Verifies if login fails or is rejected with incorrect credentials."""
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(login_url, wait_until="load", timeout=15000)
            
            email_field = await page.query_selector("input[type='email'], input[name='email'], input[name='username'], input[type='text']")
            password_field = await page.query_selector("input[type='password'], input[name='password']")

            if email_field and password_field:
                await email_field.fill(email)
                await password_field.fill("WrongPassword999!!!")
                
                submit_btn = await page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Login'), button:has-text('Sign In')")
                if submit_btn:
                    await submit_btn.click()
                else:
                    await password_field.press("Enter")
                
                await page.wait_for_timeout(2000)
                cookies = await context.cookies()
                current_url = page.url
                
                # If cookies set or URL changed, it didn't reject the wrong password!
                if len(cookies) > 0 or current_url.lower() != login_url.lower():
                    return False
            return True
        except Exception:
            return True
        finally:
            await context.close()

    async def _test_session_persistence(self, context: BrowserContext, dashboard_url: str) -> bool:
        """Verifies that the session remains active across multiple pages/tabs."""
        try:
            page2 = await context.new_page()
            await page2.goto(dashboard_url, wait_until="load", timeout=15000)
            await page2.wait_for_timeout(2000)
            cookies = await context.cookies()
            url2 = page2.url
            await page2.close()
            # If no cookies or redirected to login, session persistence failed
            if len(cookies) == 0 or "login" in url2.lower():
                return False
            return True
        except Exception:
            return False

    async def _discover_protected_routes(self, page: Page, current_url: str, base_domain: str) -> Set[str]:
        """Discovers internal links from the authenticated landing page."""
        routes = set()
        try:
            link_elements = await page.query_selector_all("a")
            for element in link_elements:
                href = await element.get_attribute("href")
                if href:
                    full_href = urljoin(current_url, href)
                    clean_href = full_href.split("#")[0].rstrip("/")
                    parsed = urlparse(clean_href)
                    if parsed.netloc == base_domain:
                        # Exclude obvious login/logout paths
                        if not any(k in clean_href.lower() for k in ("login", "logout", "signin", "signout", "register", "signup")):
                            routes.add(clean_href)
        except Exception as e:
            logger.warning("Protected route discovery failed: %s", str(e))
        return routes

    async def _test_routes_protection(self, browser: Browser, routes: Set[str]) -> List[str]:
        """Verifies if unauthenticated users are blocked/redirected from protected routes."""
        unprotected = []
        context = await browser.new_context()
        page = await context.new_page()
        try:
            for route in list(routes)[:5]:  # Test first 5 routes to keep it fast
                try:
                    res = await page.goto(route, wait_until="load", timeout=10000)
                    # If status is successful, check if URL did not redirect to a login/home URL
                    if res and res.status < 400:
                        current_url = page.url
                        if not any(k in current_url.lower() for k in ("login", "signin", "auth", "home")):
                            unprotected.append(route)
                except Exception:
                    pass
        finally:
            await context.close()
        return unprotected

    async def _audit_authenticated_page(
        self,
        context: BrowserContext,
        browser: Browser,
        url: str,
        audit_id: str,
        index: int,
        base_domain: str,
        drive_folder_id: Optional[str],
    ) -> PageAuditResult:
        """Audits an individual protected page, capturing screenshots and records."""
        page_result = PageAuditResult(url=url, role="Authenticated", access_status="allowed")
        page = await context.new_page()

        console_errors: List[str] = []
        page.on("pageerror", lambda err: console_errors.append(f"JS Exception: {err.message}"))
        page.on("console", lambda msg: console_errors.append(f"Console {msg.type.upper()}: {msg.text}") if msg.type in ("error", "warning") else None)

        try:
            response = await page.goto(url, wait_until="load", timeout=20000)
            page_result.status_code = response.status if response else 200
        except Exception as e:
            page_result.status_code = 0
            page_result.console_errors = [f"Navigation Error: {str(e)}"]
            await page.close()
            return page_result

        try:
            await page.wait_for_load_state("networkidle", timeout=2000)
        except Exception:
            pass

        page_result.console_errors = console_errors

        # Save desktop screenshot
        desktop_filename = f"{audit_id}_authenticated_desktop_{index}.png"
        desktop_filepath = os.path.join(SCREENSHOT_DIR, "Authenticated", desktop_filename)
        try:
            await page.screenshot(path=desktop_filepath, full_page=True)
            if drive_folder_id:
                drive_url = self.drive_service.upload_screenshot(
                    desktop_filepath, desktop_filename, drive_folder_id
                )
                page_result.desktop_screenshot_url = drive_url
            else:
                page_result.desktop_screenshot_url = f"/api/v1/screenshots/Authenticated/{desktop_filename}"
        except Exception as e:
            logger.warning("Authenticated desktop screenshot failed for %s: %s", url, str(e))

        # Save mobile screenshot
        mobile_filename = f"{audit_id}_authenticated_mobile_{index}.png"
        mobile_filepath = os.path.join(SCREENSHOT_DIR, "Authenticated", mobile_filename)
        try:
            # Emulate mobile screen
            await page.set_viewport_size({"width": 390, "height": 844})
            await page.screenshot(path=mobile_filepath, full_page=True)
            if drive_folder_id:
                mobile_url = self.drive_service.upload_screenshot(
                    mobile_filepath, mobile_filename, drive_folder_id
                )
                page_result.mobile_screenshot_url = mobile_url
            else:
                page_result.mobile_screenshot_url = f"/api/v1/screenshots/Authenticated/{mobile_filename}"
        except Exception as e:
            logger.warning("Authenticated mobile screenshot failed for %s: %s", url, str(e))

        await page.close()
        return page_result

    async def _test_logout(self, context: BrowserContext, dashboard_url: str) -> Tuple[bool, Optional[str]]:
        """Attempts to find and click a logout button, and verify session termination."""
        page = await context.new_page()
        try:
            await page.goto(dashboard_url, wait_until="load", timeout=15000)
            await page.wait_for_timeout(2000)

            # Look for logout links/buttons
            logout_selectors = [
                "a:has-text('logout')", "a:has-text('log out')", "a:has-text('signout')", "a:has-text('sign out')",
                "button:has-text('logout')", "button:has-text('log out')", "button:has-text('signout')", "button:has-text('sign out')",
                "a[href*='logout']", "a[href*='signout']", "button[id*='logout']", "button[class*='logout']"
            ]

            logout_clicked = False
            for selector in logout_selectors:
                try:
                    el = await page.query_selector(selector)
                    if el and await el.is_visible():
                        await el.click()
                        logout_clicked = True
                        break
                except Exception:
                    pass

            if not logout_clicked:
                # Let's try navigating to a standard logout endpoint if button not clicked
                try:
                    logout_url = urljoin(dashboard_url, "/logout")
                    await page.goto(logout_url, wait_until="load", timeout=10000)
                except Exception:
                    pass

            await page.wait_for_timeout(3000)
            cookies = await context.cookies()
            current_url = page.url

            # Succeeded if cookies cleared or redirected to home/login
            success = len(cookies) == 0 or any(k in current_url.lower() for k in ("login", "signin", "home", "index"))
            return success, current_url
        except Exception:
            return False, None
        finally:
            await page.close()
