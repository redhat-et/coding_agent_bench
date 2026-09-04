import gspread
from google.oauth2.service_account import Credentials

from coding_agent_bench.intake.config import Column, QUEUE_TAB

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


class SheetsClient:
    def __init__(self, credentials_path: str, sheet_id: str):
        """Open the configured Queue worksheet with a Google service account."""
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        gc = gspread.authorize(creds)
        self._sheet = gc.open_by_key(sheet_id).worksheet(QUEUE_TAB)

    def get_all_rows(self) -> list[list[str]]:
        """Return data rows padded to the intake schema width."""
        all_values = self._sheet.get_all_values()
        if len(all_values) <= 1:
            return []
        data_rows = all_values[1:]
        num_cols = len(Column)
        return [row + [""] * (num_cols - len(row)) for row in data_rows]

    def update_cell(self, row_index: int, col: Column, value: str) -> None:
        """Update one data-row cell, accounting for the header row and one-based APIs."""
        self._sheet.update_cell(row_index + 1, col.value + 1, value)
