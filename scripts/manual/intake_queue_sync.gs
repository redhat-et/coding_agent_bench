/**
 * Copies new Form Responses rows into the "Queue" tab in the column order the
 * intake poller expects (see coding_agent_bench.intake.config.Column).
 *
 * Install one of:
 *   - Form-submit trigger: Extensions > Apps Script > Triggers > Add Trigger,
 *     choose syncFormResponsesToQueue, event source "From spreadsheet",
 *     event type "On form submit".
 *   - Time-driven trigger: same, event source "Time-driven".
 *
 * Columns are mapped by header NAME, so reordering the form questions later
 * won't break the sync. Adjust FORM_HEADER_MAP values to match the exact header
 * text in your Form Responses tab.
 */

// Queue tab columns, in the exact order the poller's Column enum expects.
var QUEUE_HEADERS = [
  "Timestamp",
  "Agent",
  "Dataset",
  "Model Name",
  "Server URL",
  "Email",
  "Status",
  "Job ID",
  "Error",
  "Notified Queued",
  "Notified Done",
];

// Queue column -> matching header text in the Form Responses tab. Only the
// columns the form supplies are listed; the rest are filled by the poller.
var FORM_HEADER_MAP = {
  "Timestamp": "Timestamp",
  "Agent": "Agent",
  "Dataset": "Dataset",
  "Model Name": "Model Name",
  "Server URL": "Server URL",
  "Email": "Email Address",
};

// The form uses a follow-up question when the requester selects "Other".
// Resolve those answers into the single Queue column consumed by the poller.
var OTHER_MODEL_HEADER = "If Other, what model?";
var OTHER_AGENT_HEADER = "If Other, what agent?";

var FORM_RESPONSES_SHEET = "Form Responses 1";
var QUEUE_SHEET = "Queue";

function getSourceValue(srcRow, headerIndex, headerName) {
  var index = headerIndex[headerName];
  return index === undefined ? "" : srcRow[index];
}

function resolveOtherValue(srcRow, headerIndex, primaryHeader, otherHeader) {
  var primaryValue = getSourceValue(srcRow, headerIndex, primaryHeader);
  if (String(primaryValue).trim().toLowerCase() !== "other") {
    return primaryValue;
  }

  var otherValue = getSourceValue(srcRow, headerIndex, otherHeader);
  return String(otherValue).trim() ? otherValue : primaryValue;
}

function syncFormResponsesToQueue() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var src = ss.getSheetByName(FORM_RESPONSES_SHEET);
  var queue = ss.getSheetByName(QUEUE_SHEET);
  if (!src || !queue) {
    throw new Error("Missing sheet: " + FORM_RESPONSES_SHEET + " or " + QUEUE_SHEET);
  }

  // Seed the Queue header row if the tab is empty.
  if (queue.getLastRow() === 0) {
    queue.appendRow(QUEUE_HEADERS);
  }

  var srcValues = src.getDataRange().getValues();
  if (srcValues.length <= 1) return;  // header only, no responses

  var srcHeaders = srcValues[0];
  var headerIndex = {};
  for (var i = 0; i < srcHeaders.length; i++) {
    headerIndex[String(srcHeaders[i]).trim()] = i;
  }

  // Dedupe on Timestamp so re-runs don't append rows already in the Queue.
  var queueValues = queue.getDataRange().getValues();
  var tsCol = QUEUE_HEADERS.indexOf("Timestamp");
  var seen = {};
  for (var r = 1; r < queueValues.length; r++) {
    seen[String(queueValues[r][tsCol])] = true;
  }

  var newRows = [];
  for (var i = 1; i < srcValues.length; i++) {
    var srcRow = srcValues[i];
    var ts = String(srcRow[headerIndex["Timestamp"]]);
    if (seen[ts]) continue;

    var outRow = QUEUE_HEADERS.map(function (col) {
      if (col === "Agent") {
        return resolveOtherValue(srcRow, headerIndex, "Agent", OTHER_AGENT_HEADER);
      }
      if (col === "Model Name") {
        return resolveOtherValue(srcRow, headerIndex, "Model Name", OTHER_MODEL_HEADER);
      }

      var srcHeader = FORM_HEADER_MAP[col];
      if (srcHeader && headerIndex[srcHeader] !== undefined) {
        return getSourceValue(srcRow, headerIndex, srcHeader);
      }
      return "";  // Status / Job ID / Error / Notified* are managed by the poller
    });
    newRows.push(outRow);
  }

  if (newRows.length) {
    queue
      .getRange(queue.getLastRow() + 1, 1, newRows.length, QUEUE_HEADERS.length)
      .setValues(newRows);
  }
}
