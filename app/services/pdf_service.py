"""
PDF Generation Service
Uses Jinja2 and Playwright to render an HTML template into a PDF.
"""
import os
import logging
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

class PdfService:
    def __init__(self):
        self.env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        self.template_name = "report_template.html"

    async def generate_pdf(self, report_data: dict, output_path: str) -> Optional[str]:
        """
        Generates a PDF from the report data and saves it to output_path.
        Returns the output_path if successful, None otherwise.
        """
        try:
            # 1. Render HTML
            template = self.env.get_template(self.template_name)
            html_content = template.render(report=report_data)

            # 2. Convert to PDF using Playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Load the HTML content directly
                await page.set_content(html_content, wait_until="networkidle")
                
                # Generate PDF
                await page.pdf(
                    path=output_path,
                    format="A4",
                    print_background=True,
                    margin={"top": "20px", "right": "20px", "bottom": "20px", "left": "20px"}
                )
                
                await browser.close()
                
            logger.info(f"Successfully generated PDF report at {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")
            return None
