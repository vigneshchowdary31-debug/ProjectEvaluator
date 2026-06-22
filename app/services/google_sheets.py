"""
Google Sheets Service — authenticates using Service Account
and reads/writes data to Google Sheets.
"""

import os
import logging
import re
from typing import List, Dict, Any, Optional, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config import get_settings

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Service to handle reading from and writing to Google Sheets."""

    def __init__(self):
        settings = get_settings()
        self.creds_path = settings.GOOGLE_CREDENTIALS_JSON
        self.service = None
        self.enabled = False

        if self.creds_path and os.path.exists(self.creds_path):
            try:
                scopes = [
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive.file",
                    "https://www.googleapis.com/auth/drive",
                ]
                self.creds = service_account.Credentials.from_service_account_file(
                    self.creds_path, scopes=scopes
                )
                self.service = build("sheets", "v4", credentials=self.creds)
                self.enabled = True
                logger.info("Google Sheets API initialized successfully with service account.")
            except Exception as e:
                logger.error("Failed to initialize Google Sheets client: %s", str(e))
        else:
            logger.warning("Google Sheets service disabled (no GOOGLE_CREDENTIALS_JSON path configured or file not found).")

    @staticmethod
    def extract_sheet_id(url: str) -> Optional[str]:
        """Extract Google Sheet ID from URL."""
        if not url:
            return None
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
        if match:
            return match.group(1)
        # Check if URL itself is just an ID
        if re.match(r"^[a-zA-Z0-9-_]+$", url):
            return url
        return None

    def test_connection(self, sheet_id: str) -> Tuple[bool, str]:
        """Test connection and return status and sheet name."""
        if not self.enabled or not self.service:
            return False, "Google Sheets service is disabled or not configured."
        try:
            spreadsheet = self.service.spreadsheets().get(spreadsheetId=sheet_id).execute()
            sheet_name = spreadsheet.get("properties", {}).get("title", "Unnamed Sheet")
            return True, sheet_name
        except Exception as e:
            logger.error("Failed to connect to spreadsheet %s: %s", sheet_id, str(e))
            return False, str(e)

    def get_first_sheet_name(self, sheet_id: str) -> str:
        """Get the title of the first sheet/tab in the spreadsheet."""
        if not self.enabled or not self.service:
            return "Sheet1"
        try:
            spreadsheet = self.service.spreadsheets().get(spreadsheetId=sheet_id).execute()
            sheets = spreadsheet.get("sheets", [])
            if sheets:
                return sheets[0].get("properties", {}).get("title", "Sheet1")
        except Exception as e:
            logger.error("Failed to get sheet name: %s", str(e))
        return "Sheet1"

    def read_all_rows(self, sheet_id: str, sheet_name: Optional[str] = None) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Reads all rows from a spreadsheet and maps them based on headers."""
        if not self.enabled or not self.service:
            raise Exception("Google Sheets service is not enabled")
        
        if not sheet_name:
            sheet_name = self.get_first_sheet_name(sheet_id)
            
        range_name = f"'{sheet_name}'!A1:ZZ"
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=sheet_id, range=range_name
            ).execute()
            rows = result.get("values", [])
            if not rows:
                return [], []
                
            headers = [h.strip() for h in rows[0]]
            data_rows = []
            
            # Map each data row to a dictionary of headers -> value
            for idx, row in enumerate(rows[1:], start=2):  # Row number 2 is index 1 in data
                row_dict = {"_row_number": idx}
                for h_idx, header in enumerate(headers):
                    val = row[h_idx] if h_idx < len(row) else ""
                    row_dict[header] = val.strip() if isinstance(val, str) else val
                data_rows.append(row_dict)
                
            return data_rows, headers
        except Exception as e:
            logger.error("Error reading spreadsheet: %s", str(e))
            raise e

    def write_row_data(self, sheet_id: str, sheet_name: Optional[str], row_number: int, headers: List[str], update_dict: Dict[str, Any]) -> None:
        """Writes data back to specific columns in a sheet row."""
        if not self.enabled or not self.service:
            raise Exception("Google Sheets service is not enabled")
            
        if not sheet_name:
            sheet_name = self.get_first_sheet_name(sheet_id)
            
        # First, ensure we have the headers we need in the spreadsheet. If not, append them.
        missing_headers = [h for h in update_dict.keys() if h not in headers]
        if missing_headers:
            # We need to append these headers to row 1 (A1:ZZ1)
            range_header = f"'{sheet_name}'!A1:ZZ1"
            h_res = self.service.spreadsheets().values().get(
                spreadsheetId=sheet_id, range=range_header
            ).execute()
            current_headers = [h.strip() for h in h_res.get("values", [[]])[0]]
            
            new_headers = current_headers.copy()
            for mh in missing_headers:
                if mh not in new_headers:
                    new_headers.append(mh)
            
            # Write new headers back
            self.service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_header,
                valueInputOption="RAW",
                body={"values": [new_headers]}
            ).execute()
            
            # Update headers list in-place
            headers.clear()
            headers.extend(new_headers)
            
        # Get the current row's values to avoid overwriting unrelated columns.
        range_row = f"'{sheet_name}'!A{row_number}:ZZ{row_number}"
        row_res = self.service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=range_row
        ).execute()
        current_row_values = row_res.get("values", [[]])[0]
        
        # Expand current_row_values to match headers length
        while len(current_row_values) < len(headers):
            current_row_values.append("")
            
        # Update values based on update_dict
        for key, val in update_dict.items():
            if key in headers:
                col_idx = headers.index(key)
                current_row_values[col_idx] = str(val) if val is not None else ""
                
        # Write the updated row back
        self.service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{sheet_name}'!A{row_number}:{self._col_letter(len(headers))}{row_number}",
            valueInputOption="RAW",
            body={"values": [current_row_values]}
        ).execute()

    @staticmethod
    def _col_letter(col_idx: int) -> str:
        """Convert a 1-based column index to Excel-style letters (e.g., 1 -> A, 28 -> AB)."""
        temp = ""
        while col_idx > 0:
            col_idx, remainder = divmod(col_idx - 1, 26)
            temp = chr(65 + remainder) + temp
        return temp
