from unittest.mock import MagicMock

from coding_agent_bench.intake.config import Column
from coding_agent_bench.intake.sheets import SheetsClient


def test_get_all_rows_pads_short_rows():
    mock_sheet = MagicMock()
    mock_sheet.get_all_values.return_value = [
        ["Timestamp", "Agent", "Dataset", "Model", "URL", "Email",
         "Status", "Job ID", "Error", "Notified Queued", "Notified Done"],
        ["2026-08-17", "codex", "swe-bench/swe-bench-verified", "Qwen/Qwen3-32B",
         "https://vllm.example.com", "user@example.com"],
    ]

    client = SheetsClient.__new__(SheetsClient)
    client._sheet = mock_sheet

    rows = client.get_all_rows()

    assert len(rows) == 1
    assert len(rows[0]) == len(Column)
    assert rows[0][Column.AGENT] == "codex"
    assert rows[0][Column.STATUS] == ""


def test_update_cell_calls_gspread():
    mock_sheet = MagicMock()

    client = SheetsClient.__new__(SheetsClient)
    client._sheet = mock_sheet

    client.update_cell(row_index=1, col=Column.STATUS, value="Queued")

    # row_index 1 = data row 1, which is spreadsheet row 2 (header is row 1)
    # Column.STATUS.value is the 0-based column index; gspread uses 1-based
    mock_sheet.update_cell.assert_called_once_with(2, Column.STATUS.value + 1, "Queued")
