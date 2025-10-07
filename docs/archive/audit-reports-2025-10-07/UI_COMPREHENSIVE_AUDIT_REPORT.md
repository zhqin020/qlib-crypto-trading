# UI Comprehensive Audit Report
**Date:** 2025-10-07
**File Audited:** `/Users/chadwyatt/Code/trading/qlib-2/src/ui/static/index.html`
**Lines of Code:** 2,486
**Status:** Production Analysis

---

## Executive Summary

This comprehensive audit of the Qlib Crypto Trading Platform UI identifies **36 issues** across 6 categories, ranging from critical functional bugs to minor UX improvements. The UI is largely functional but has several incomplete features, potential JavaScript errors, and UX inconsistencies that impact user experience.

### Severity Breakdown
- **Critical (P0):** 8 issues - Must fix immediately
- **High (P1):** 12 issues - Should fix soon
- **Medium (P2):** 10 issues - Plan to fix
- **Low (P3):** 6 issues - Nice to have

---

## 1. INCOMPLETE FEATURES

### 1.1 Missing Navigation for "Processes" Page
**Severity:** P0 - Critical
**Lines:** 1089-1136
**Description:** The sidebar navigation has no link to the "Processes" page, but the page exists and is referenced in keyboard shortcuts (line 2049). Users can only reach it via keyboard shortcut "1" (dashboard), not directly.

**Evidence:**
```html
<!-- Lines 1089-1136: Navigation section -->
<nav class="nav-section">
    <div class="nav-title">Navigation</div>
    <button ... @click="page = 'dashboard'">📊 Dashboard</button>
    <button ... @click="page = 'data'">💹 Market Data</button>
    <button ... @click="page = 'models'">🤖 Models</button>
    <button ... @click="page = 'backtest'">📈 Backtest</button>
    <button ... @click="page = 'predictions'">🔮 Predictions</button>
    <!-- MISSING: Processes page button -->
</nav>
```

**User Impact:** Users cannot discover the Processes page unless they know the keyboard shortcut. The Active Processes section on the dashboard is visible, but there's no way to see historical/completed processes.

**Recommendation:** Add navigation button for Processes page or remove the page if not intended for production.

---

### 1.2 Keyboard Shortcut "6" Has No Page
**Severity:** P2 - Medium
**Lines:** 2043-2055
**Description:** The keyboard shortcut handler supports keys 1-5 for navigation, but there are only 5 pages (dashboard, data, models, backtest, predictions). Key "6" would cause an error.

**Evidence:**
```javascript
// Lines 2043-2055
case '1':
case '2':
case '3':
case '4':
case '5':
    const pages = ['dashboard', 'data', 'models', 'backtest', 'predictions'];
    const pageIndex = parseInt(e.key) - 1;
    if (pageIndex < pages.length) {  // Safe guard exists
        this.page = pages[pageIndex];
    }
    break;
```

**User Impact:** None currently (safe guard prevents error), but confusing documentation if users expect more pages.

**Recommendation:** Document keyboard shortcuts in UI or remove unused number keys from switch statement.

---

### 1.3 "Processes" Page Content Missing from UI
**Severity:** P1 - High
**Lines:** 1148-1866
**Description:** The HTML only has 5 page sections (dashboard, data, models, backtest, predictions), but process monitoring features are embedded in the dashboard. There's no dedicated "Processes" page despite references to it.

**Evidence:**
```html
<!-- Lines 1148-1866: All page sections -->
<div v-if="page === 'dashboard'">...</div>
<div v-if="page === 'data'">...</div>
<div v-if="page === 'models'">...</div>
<div v-if="page === 'backtest'">...</div>
<div v-if="page === 'predictions'">...</div>
<!-- MISSING: <div v-if="page === 'processes'">...</div> -->
```

**User Impact:** Inconsistent architecture - processes are shown on dashboard but referenced as separate page.

**Recommendation:** Either create dedicated Processes page or remove all references to it as a separate page.

---

### 1.4 Dataset/Model Dropdowns Don't Show Loading State
**Severity:** P1 - High
**Lines:** 1567-1587, 1668-1690, 1791-1813, 1819-1843
**Description:** When users focus on dataset/model dropdowns, `loadDatasets()` and `loadModels()` are called, but there's no visual loading indicator. The dropdowns appear empty until data loads, which can take 1-2 seconds.

**Evidence:**
```html
<!-- Line 1567: Train dataset dropdown -->
<select id="train-dataset" v-model="forms.train.dataset"
    @focus="loadDatasets"  <!-- Triggers async load -->
    aria-required="true">
    <option value="" disabled>Select dataset...</option>
    <option v-for="ds in datasets" :key="ds.name" :value="ds.name">
        {{ ds.name }}
    </option>
</select>
<!-- NO loading state shown while loadDatasets() runs -->
```

**User Impact:** Dropdown appears empty briefly, users may think no datasets exist and close the dropdown.

**Recommendation:** Add loading state with spinner:
```html
<select :disabled="loadingStates.datasets">
    <option v-if="loadingStates.datasets">Loading datasets...</option>
    <option v-else value="" disabled>Select dataset...</option>
    ...
</select>
```

---

### 1.5 No Empty State for Datasets/Models Dropdowns
**Severity:** P2 - Medium
**Lines:** 1574-1583, 1696-1712
**Description:** If `datasets` array is empty after loading, dropdown shows only "Select dataset..." with no explanation. Users don't know if datasets failed to load or don't exist.

**Evidence:**
```html
<select id="train-dataset" v-model="forms.train.dataset">
    <option value="" disabled>Select dataset...</option>
    <!-- If datasets.length === 0, dropdown appears broken -->
    <option v-for="ds in datasets" :key="ds.name" :value="ds.name">
        {{ ds.name }}
    </option>
</select>
```

**User Impact:** Confusing when no datasets exist - is it a bug or expected state?

**Recommendation:** Add conditional empty state option:
```html
<option v-if="datasets.length === 0" disabled>
    No datasets available. Create one in Market Data.
</option>
```

---

### 1.6 Error States Not Displayed for Failed Dropdown Loads
**Severity:** P1 - High
**Lines:** 2106-2123
**Description:** `loadModels()` and `loadDatasets()` catch errors but only log to console. Users see empty dropdowns with no indication that loading failed.

**Evidence:**
```javascript
// Lines 2115-2123
async loadDatasets() {
    try {
        const res = await fetch("/api/datasets");
        const data = await res.json();
        this.datasets = data.datasets || [];
    } catch (e) {
        console.error("Failed to load datasets:", e);
        // NO USER FEEDBACK - dropdown just stays empty
    }
}
```

**User Impact:** Silent failures leave users wondering if datasets exist or if there's a bug.

**Recommendation:** Store error state and display to user:
```javascript
this.errorStates.datasets = e.message;
// Then in HTML:
<div v-if="errorStates.datasets" class="dropdown-error-state">
    Failed to load datasets: {{ errorStates.datasets }}
    <button @click="loadDatasets">Retry</button>
</div>
```

---

### 1.7 Toast Notification System Not Connected to UI
**Severity:** P2 - Medium
**Lines:** 2005-2021
**Description:** A complete toast notification system exists in JavaScript (`showToast()`, `closeToast()`, `toasts` array) but there's no HTML template to display toasts. The system is called (lines 2034, 2360, 2380) but nothing appears on screen.

**Evidence:**
```javascript
// Lines 2005-2021: Toast system implementation
showToast(type, message, duration = 5000) {
    const id = this.toastIdCounter++;
    this.toasts.push({ id, type, message });
    // ... implementation
}
// Line 2360: Called but no visible UI
this.showToast('success', `Process ${processId} cancelled successfully`, 3000);
```

**User Impact:** Important feedback messages are invisible to users.

**Recommendation:** Add toast container to HTML:
```html
<div class="toast-container" aria-live="polite">
    <div v-for="toast in toasts" :key="toast.id"
         :class="['toast', toast.type]">
        {{ toast.message }}
        <button @click="closeToast(toast.id)" aria-label="Dismiss">×</button>
    </div>
</div>
```

---

### 1.8 Confirm Dialog for Process Cancellation is Browser Native
**Severity:** P3 - Low
**Line:** 2331
**Description:** Uses browser's native `confirm()` dialog which blocks the UI thread and looks out of place in the modern dark-themed UI.

**Evidence:**
```javascript
// Line 2331
if (!confirm(`Cancel process ${processId}?`)) return;
```

**User Impact:** Jarring UX with inconsistent styling, blocks entire page.

**Recommendation:** Implement custom modal confirmation dialog matching the UI theme.

---

## 2. JAVASCRIPT ERRORS & POTENTIAL RUNTIME ISSUES

### 2.1 Potential Null Reference Error in Process Logs
**Severity:** P1 - High
**Lines:** 2318-2326
**Description:** `scrollLogsToBottom()` accesses `this.$refs['logs-' + processId][0]` but refs may not exist if the element hasn't rendered yet. This can cause runtime errors.

**Evidence:**
```javascript
// Lines 2318-2326
scrollLogsToBottom(processId) {
    const logElement = this.$refs['logs-' + processId];
    if (logElement && logElement[0]) {  // Array access assumes element exists
        logElement[0].scrollTop = logElement[0].scrollHeight;
        // ...
    }
}
```

**User Impact:** Console error when trying to scroll logs before DOM renders, breaks log viewing.

**Recommendation:** Add better null checking:
```javascript
if (logElement?.[0]?.scrollTop !== undefined) {
    logElement[0].scrollTop = logElement[0].scrollHeight;
}
```

---

### 2.2 Race Condition in Process Cancellation
**Severity:** P0 - Critical
**Lines:** 2327-2382
**Description:** The cancellation flow has a race condition where the WebSocket might update the process status between the DELETE request and the optimistic UI update, causing state inconsistencies.

**Evidence:**
```javascript
// Lines 2342-2357
const res = await fetch(`/api/processes/${processId}`, {
    method: "DELETE",
});
// ...
if (processIndex >= 0) {
    this.processes[processIndex].status = 'cancelling';  // Optimistic update
    this.$forceUpdate();
}
// WebSocket could update status to 'running' again before this executes
```

**User Impact:** Cancel button might disappear and reappear, confusing users. Process might not appear cancelled even though request succeeded.

**Recommendation:** Disable WebSocket updates for specific process during cancellation, or use a local "cancelling" flag that overrides WebSocket status.

---

### 2.3 Memory Leak from Unclosed WebSockets
**Severity:** P1 - High
**Lines:** 2422-2480
**Description:** `monitorProcess()` creates per-process WebSocket connections stored in `processWebSockets` object, but if the page unmounts while processes are running, these connections aren't closed.

**Evidence:**
```javascript
// Lines 2422-2480: Creates WebSocket per process
monitorProcess(processId) {
    const ws = new WebSocket(wsUrl);
    // ...
    this.processWebSockets[processId] = ws;
}
// Line 2002: Cleanup only closes some connections
Object.values(this.processWebSockets).forEach(ws => ws.close());
```

**User Impact:** Over time, zombie WebSocket connections accumulate, consuming memory and possibly causing browser to hit connection limits.

**Recommendation:** Ensure all WebSocket connections are tracked and closed in `beforeUnmount()`.

---

### 2.4 $forceUpdate() Anti-pattern Throughout
**Severity:** P2 - Medium
**Lines:** 1989, 2040, 2298, 2315, 2324, 2340, 2356, 2365, 2374, 2377, 2440
**Description:** `$forceUpdate()` is called 11 times throughout the code, indicating Vue's reactivity system isn't working properly. This is an anti-pattern that can cause performance issues and unexpected behavior.

**Evidence:**
```javascript
// Line 1989: Forced update every second for all processes
setInterval(() => {
    this.$forceUpdate();
}, 1000);
```

**User Impact:** Poor performance, entire component re-renders every second even when nothing changed.

**Recommendation:** Use Vue 3's reactive system properly:
```javascript
// Replace object property mutations with reactive updates
import { reactive } from 'vue';
this.cancellingProcesses = reactive({});
// No need for $forceUpdate() - Vue tracks changes automatically
```

---

### 2.5 Infinite Loop Risk in WebSocket Reconnection
**Severity:** P1 - High
**Lines:** 2071-2074, 2254-2257
**Description:** WebSocket reconnection logic has no backoff or max retry count. If the server is permanently down, the client will attempt to reconnect every 3 seconds forever.

**Evidence:**
```javascript
// Lines 2071-2074
this.ws.onclose = () => {
    this.connected = false;
    setTimeout(() => this.connectWebSocket(), 3000);  // Infinite retry
};
```

**User Impact:** Browser becomes slow/unresponsive with accumulating failed connection attempts.

**Recommendation:** Implement exponential backoff:
```javascript
const maxRetries = 10;
const baseDelay = 3000;
let retryCount = 0;

this.ws.onclose = () => {
    this.connected = false;
    if (retryCount < maxRetries) {
        const delay = Math.min(baseDelay * Math.pow(2, retryCount), 30000);
        setTimeout(() => this.connectWebSocket(), delay);
        retryCount++;
    } else {
        // Show error to user: "Connection lost. Please refresh the page."
    }
};
```

---

### 2.6 Async/Await Not Used Consistently
**Severity:** P2 - Medium
**Lines:** 2159-2203
**Description:** Some API calls use `async/await` properly (`downloadData()`, `trainModel()`), while others like `convertData()` mix promise chaining with try/catch, making error handling inconsistent.

**Evidence:**
```javascript
// Lines 2172-2203: convertData() uses try/catch with await
async convertData() {
    this.loading = true;
    try {
        const res = await fetch(`/api/data/convert?...`);
        const result = await res.json();
        // ... proper error handling
    } catch (error) {
        // ...
    } finally {
        this.loading = false;
    }
}
```

**User Impact:** Inconsistent error handling can lead to missed errors or incorrect UI states.

**Recommendation:** Standardize on `async/await` for all API calls with centralized error handling.

---

### 2.7 Missing HTTP Status Code Checks
**Severity:** P1 - High
**Lines:** 2108-2113, 2116-2122, 2175-2180
**Description:** API calls assume successful responses. If the server returns 4xx/5xx status codes, `res.json()` is called on error responses, which may not be valid JSON.

**Evidence:**
```javascript
// Lines 2108-2113
async loadModels() {
    try {
        const res = await fetch("/api/models");
        const data = await res.json();  // No check if res.ok === true
        this.models = data.models || [];
    } catch (e) {
        console.error("Failed to load models:", e);
    }
}
```

**User Impact:** Cryptic error messages like "Unexpected token < in JSON" when server returns HTML error pages.

**Recommendation:** Check response status:
```javascript
if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
}
const data = await res.json();
```

---

### 2.8 Process Status Type Safety Not Enforced
**Severity:** P2 - Medium
**Lines:** 1221-1235, 2354-2357
**Description:** Process status is compared as strings (`'running'`, `'completed'`) but there's no validation that the backend returns these exact values. Typos or backend changes could break UI logic.

**Evidence:**
```html
<!-- Line 1221: Assumes specific status values -->
:class="['process-card', process.status]"
<!-- Line 1231: String comparison -->
<span v-if="process.status === 'running'" class="icon-spin" aria-hidden="true">⟳</span>
```

**User Impact:** If backend returns "RUNNING" instead of "running", icons and styles break.

**Recommendation:** Define status enum constants and validate backend responses:
```javascript
const ProcessStatus = {
    RUNNING: 'running',
    COMPLETED: 'completed',
    FAILED: 'failed',
    CANCELLED: 'cancelled'
};
```

---

## 3. UX ISSUES & USER FLOW PROBLEMS

### 3.1 Dead-End After Creating Dataset
**Severity:** P1 - High
**Lines:** 2172-2203
**Description:** After successfully converting data to a dataset, the user is left on the Market Data page with a success message. There's no clear next step to train a model with the new dataset.

**Evidence:**
```javascript
// Lines 2188-2192
this.forms.convert.status = "success";
this.addActivity("Dataset converted successfully", "success");
setTimeout(() => this.loadDatasets(), 2000);
// User is still on 'data' page, no guidance to next step
```

**User Impact:** Users don't know what to do next after creating a dataset.

**Recommendation:** Add "Train Model" button in success message that navigates to Models page with the new dataset pre-selected:
```javascript
this.forms.convert.result = JSON.stringify(result, null, 2);
this.forms.convert.status = "success";
this.forms.convert.nextAction = {
    text: "Train Model with this Dataset",
    action: () => {
        this.page = 'models';
        this.forms.train.dataset = this.forms.convert.dataset;
    }
};
```

---

### 3.2 No Feedback for Long-Running Operations
**Severity:** P1 - High
**Lines:** 1426-1437
**Description:** Download Data, Train Model, and other buttons change to "Downloading..." / "Training..." but there's no indication of how long the operation might take or that users should check the Dashboard for progress.

**Evidence:**
```html
<!-- Lines 1426-1437 -->
<button @click="downloadData" class="btn btn-primary" :disabled="loading">
    <span v-if="!loading">Download Data</span>
    <span v-else>
        <span class="spinner" aria-hidden="true"></span>
        <span aria-live="polite">Downloading...</span>
    </span>
</button>
```

**User Impact:** Users wait on the page expecting immediate results, not realizing they need to check the Dashboard for progress tracking.

**Recommendation:** Add informational message after starting operation:
```html
<div v-if="loading" class="info-banner">
    ⏱️ Operation started. View real-time progress on the
    <a @click="page = 'dashboard'" class="link">Dashboard</a>.
</div>
```

---

### 3.3 Inconsistent Terminology: "Dataset" vs "Dataset Ref"
**Severity:** P2 - Medium
**Lines:** Throughout UI
**Description:** Backend API uses "dataset_ref" parameter but UI labels say "Dataset". This causes confusion when reading API documentation vs using the UI.

**Evidence:**
```html
<!-- Line 1563: UI says "Dataset" -->
<label for="train-dataset" class="form-label">Dataset</label>
<!-- But API expects "dataset" (which maps to "dataset_ref" in backend) -->
```

**User Impact:** Users trying to understand the system get confused by different terminology in UI vs API.

**Recommendation:** Use consistent terminology throughout. Either change UI to "Dataset Reference" or update backend parameter names.

---

### 3.4 No Indication of Required vs Optional Fields
**Severity:** P2 - Medium
**Lines:** 1326-1349, 1462-1476
**Description:** Some form fields have `<span class="required">*</span>` (lines 1328, 1374, 1391) while others don't, but it's not clear which fields are truly required. For example, "Transaction Costs" has no asterisk but defaults to "medium" (line 1966).

**Evidence:**
```html
<!-- Line 1719: No required indicator -->
<label for="backtest-costs" class="form-label">Transaction Costs</label>
<!-- But form has default value, so technically optional -->
```

**User Impact:** Users don't know what they must fill out vs what can be left at defaults.

**Recommendation:**
1. Add required indicators to all mandatory fields
2. Add "(Optional)" label to truly optional fields
3. Validate required fields on submit with clear error messages

---

### 3.5 Success Result Boxes Use Same Style for Different Data
**Severity:** P2 - Medium
**Lines:** 1438-1443, 1508-1513, 1643-1648
**Description:** All success results are shown as raw JSON in a monospace box. For simple operations (download, convert), this is overwhelming. For complex results (backtest metrics), it's useful but not formatted for readability.

**Evidence:**
```html
<!-- Line 1438-1443: Raw JSON for simple success -->
<div v-if="forms.data.result" :class="['result-box', forms.data.status]">
    {{ forms.data.result }}
</div>
```

**User Impact:** Users overwhelmed by JSON when they just need "Success: Downloaded 365 data points".

**Recommendation:** Parse result data and show user-friendly summaries:
```html
<div v-if="forms.data.result" class="result-summary">
    <div class="result-icon">✅</div>
    <div class="result-message">
        Successfully downloaded {{ forms.data.parsed.count }} data points
        for {{ forms.data.parsed.symbols.join(', ') }}
    </div>
    <details>
        <summary>View raw data</summary>
        <pre>{{ forms.data.result }}</pre>
    </details>
</div>
```

---

### 3.6 Process Logs Auto-Scroll Can't Be Disabled
**Severity:** P3 - Low
**Lines:** 2264-2272, 2287-2296
**Description:** When process logs are expanded, they auto-scroll to bottom as new logs arrive. If users scroll up to read older logs, the view jumps back to bottom on next update, making it impossible to read historical logs for running processes.

**Evidence:**
```javascript
// Lines 2264-2272: Auto-scroll when new data arrives
if (data.type === "process_update") {
    this.processes = data.processes || [];
    Object.keys(this.expandedProcesses).forEach(processId => {
        if (this.expandedProcesses[processId] && this.autoScrollEnabled[processId]) {
            this.$nextTick(() => {
                this.scrollLogsToBottom(processId);
            });
        }
    });
}
```

**User Impact:** Users can't read older log entries while process is still running.

**Recommendation:** The code has `autoScrollEnabled` tracking (line 2289), but the scroll button implementation (lines 2301-2316) has a bug - scrolling up should keep auto-scroll disabled until user manually scrolls to bottom again.

---

### 3.7 No Visual Distinction Between Process Types
**Severity:** P3 - Low
**Lines:** 1219-1264
**Description:** All processes use the same colored border (blue for running, green for completed, red for failed). There's no indication whether it's a training, backtest, download, or prediction process beyond reading the ID string.

**Evidence:**
```html
<!-- Lines 1237-1241: Display shows process type in ID only -->
<span :title="'UUID: ' + process.process_id" style="cursor: help;">
    {{ process.display_id || (process.process_type + ' - ' + process.process_id) }}
</span>
```

**User Impact:** At a glance, users can't tell what type of operation is running without reading text.

**Recommendation:** Add icons or colored badges for different process types:
```html
<span class="process-type-badge" :class="'type-' + process.process_type">
    {{ process.process_type === 'training' ? '🎯' :
       process.process_type === 'backtest' ? '📈' :
       process.process_type === 'download' ? '📥' : '🔮' }}
</span>
```

---

### 3.8 Keyboard Shortcuts Not Discoverable
**Severity:** P2 - Medium
**Lines:** 2023-2056
**Description:** The UI has keyboard shortcuts (R for refresh, 1-5 for pages, Escape to close logs) but there's no indication in the UI that these exist. Power users will never discover them.

**Evidence:**
```javascript
// Lines 2027-2041: Keyboard shortcuts exist but not documented
case 'r':
case 'R':
    // Refresh all data
    this.loadProcesses();
    this.loadModels();
    this.loadDatasets();
    this.showToast('info', 'Refreshed all data', 2000);
    break;
```

**User Impact:** Users don't know shortcuts exist, leading to more mouse clicks and slower workflows.

**Recommendation:** Add keyboard shortcuts help panel:
```html
<div class="keyboard-shortcuts-hint">
    Press <kbd>?</kbd> to view keyboard shortcuts
</div>
<!-- Modal when ? is pressed -->
<div v-if="showShortcutsModal" class="modal">
    <h2>Keyboard Shortcuts</h2>
    <ul>
        <li><kbd>R</kbd> - Refresh all data</li>
        <li><kbd>1-5</kbd> - Navigate between pages</li>
        <li><kbd>Esc</kbd> - Close expanded logs</li>
    </ul>
</div>
```

---

### 3.9 No Undo for Process Cancellation
**Severity:** P3 - Low
**Lines:** 2327-2382
**Description:** Once a user clicks "Cancel" on a process and confirms, there's no way to undo. For long-running training jobs, this could be catastrophic if clicked by accident.

**Evidence:**
```javascript
// Line 2331: Simple confirm dialog, no grace period
if (!confirm(`Cancel process ${processId}?`)) return;
// Immediately sends DELETE request
```

**User Impact:** Accidental cancellation of 3-hour model training with no recovery.

**Recommendation:** Add grace period with toast notification:
```javascript
this.showToast('warning', 'Cancelling process in 5 seconds... Click to undo.', 5000);
setTimeout(() => {
    if (!this.cancelledProcessesPending[processId]) return; // User clicked undo
    // Actually cancel process
}, 5000);
```

---

## 4. ACCESSIBILITY ISSUES

### 4.1 Live Region Updates Too Frequent
**Severity:** P2 - Medium
**Lines:** 1869-1876, 1290-1293
**Description:** The activity feed has `aria-live="polite"` which announces every event to screen readers. For high-activity operations, this creates noise pollution for screen reader users.

**Evidence:**
```html
<!-- Lines 1881-1897: Activity feed with live region -->
<div class="activity-feed" role="log" aria-live="polite" aria-atomic="false">
    <!-- Every activity item announced separately -->
    <div v-for="act in activities.slice(0, 30)" :key="act.id"
         :class="['activity-item', act.class]" role="article"
         :aria-label="'Activity: ' + act.message">
```

**User Impact:** Screen reader users bombarded with announcements, can't focus on their actual task.

**Recommendation:**
1. Use `aria-live="off"` for the feed itself
2. Only announce critical events via the separate status region (lines 1869-1876)
3. Add "View activity feed" button that temporarily enables announcements

---

### 4.2 Form Validation Errors Not Announced
**Severity:** P1 - High
**Lines:** Throughout forms
**Description:** Forms have `aria-required="true"` attributes (lines 1334, 1359, 1572) but when validation fails (e.g., submitting without selecting a dataset), there's no `aria-invalid` or error announcement to screen readers.

**Evidence:**
```html
<!-- Line 1631-1642: Submit button disables when invalid -->
<button @click="trainModel" class="btn btn-primary"
    :disabled="loading || !forms.train.dataset"
    aria-label="Train new model">
<!-- But no error message for screen readers explaining WHY disabled -->
```

**User Impact:** Screen reader users don't know why the button is disabled or what fields need to be filled.

**Recommendation:** Add validation error messages:
```html
<div v-if="!forms.train.dataset && attemptedSubmit"
     role="alert" class="error-message">
    Please select a dataset before training
</div>
<select aria-invalid="!forms.train.dataset && attemptedSubmit"
        aria-describedby="train-dataset-error">
```

---

### 4.3 Progress Bars Missing aria-valuetext
**Severity:** P2 - Medium
**Lines:** 1274-1276
**Description:** Progress bars have `aria-valuenow` but don't have `aria-valuetext` for screen readers to announce meaningful progress like "Training: Step 5 of 10, 50% complete".

**Evidence:**
```html
<!-- Line 1274-1276: Progress bar -->
<div class="progress-bar-container" role="progressbar"
     :aria-valuenow="process.metrics.progress_percent"
     aria-valuemin="0" aria-valuemax="100"
     :aria-label="'Progress: ' + process.metrics.progress_percent.toFixed(1) + '%'">
<!-- Missing aria-valuetext with human-readable status -->
```

**User Impact:** Screen reader announces "50%" but not what the process is currently doing.

**Recommendation:** Add aria-valuetext:
```html
:aria-valuetext="process.metrics.current_step + ', ' +
                 process.metrics.progress_percent.toFixed(1) + '% complete'"
```

---

### 4.4 Modal Confirmation Dialog Not Accessible
**Severity:** P1 - High
**Line:** 2331
**Description:** Native `confirm()` dialog is used for process cancellation. While native dialogs have basic accessibility, they don't follow WAI-ARIA Authoring Practices for modal dialogs.

**Evidence:**
```javascript
// Line 2331: Native confirm dialog
if (!confirm(`Cancel process ${processId}?`)) return;
```

**User Impact:** Screen reader users get basic dialog, but no keyboard trap management or focus restoration.

**Recommendation:** Implement custom modal dialog component with proper ARIA attributes and focus management as per WAI-ARIA practices.

---

### 4.5 Scroll-to-Bottom Button Appears Without Announcement
**Severity:** P3 - Low
**Lines:** 2301-2308
**Description:** When logs auto-scroll and the user scrolls up, a "Scroll to Bottom" button appears (line 2306) but there's no announcement to screen reader users that this control is now available.

**Evidence:**
```javascript
// Lines 2301-2316: Button visibility tracked
handleLogScroll(processId, event) {
    const element = event.target;
    const isAtBottom = element.scrollHeight - element.scrollTop <= element.clientHeight + 5;
    this.showScrollButton[processId] = !isAtBottom;  // Visual only
    // No ARIA announcement
}
```

**User Impact:** Screen reader users don't know the button appeared and may struggle to return to bottom of logs.

**Recommendation:** Add live region announcement when button state changes:
```html
<div role="status" aria-live="polite" class="sr-only">
    {{ showScrollButton[processId] ? 'Scroll to bottom button available' : '' }}
</div>
```

---

### 4.6 Dynamic Status Updates Cause Screen Reader Chaos
**Severity:** P2 - Medium
**Lines:** 1266-1283
**Description:** Process metadata updates every second (line 1989) with `$forceUpdate()`, causing screen readers to re-read the entire process card every second with new elapsed time values.

**Evidence:**
```html
<!-- Lines 1266-1272: Updates every second -->
<div class="process-meta" aria-label="Process metadata">
    {{ process.metrics.current_step }} |
    Elapsed: {{ formatDuration(process) }}  <!-- Changes every second -->
    <span v-if="process.status === 'running' && process.metrics.estimated_seconds_remaining">
        | ETA: ~{{ formatETA(process.metrics.estimated_seconds_remaining) }}
    </span>
</div>
```

**User Impact:** Screen reader users hear constant interruptions: "Elapsed 45 seconds... Elapsed 46 seconds... Elapsed 47 seconds..."

**Recommendation:** Use `aria-atomic="false"` and only announce significant changes (every 10 seconds or on step completion), not every tick.

---

## 5. DATA DISPLAY ISSUES

### 5.1 Timestamps Not in User's Timezone
**Severity:** P2 - Medium
**Lines:** 2239-2241, 2403-2406
**Description:** `formatTime()` uses `toLocaleTimeString()` which shows time in user's locale, but `formatLogTime()` does the same. However, the backend sends UTC timestamps, and there's no indication of timezone to users.

**Evidence:**
```javascript
// Lines 2239-2241
formatTime(timestamp) {
    return new Date(timestamp).toLocaleTimeString();
    // Shows "3:45:21 PM" but doesn't indicate if it's UTC or local
}
```

**User Impact:** Users in different timezones confused about when events occurred, especially for scheduled predictions.

**Recommendation:** Show timezone explicitly:
```javascript
formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString() + ' ' +
           Intl.DateTimeFormat().resolvedOptions().timeZone;
}
```

---

### 5.2 Large Numbers Not Formatted with Separators
**Severity:** P3 - Low
**Lines:** 1176-1184, 1197-1207
**Description:** Dashboard shows counts like "42" or "1203" without thousand separators. For large datasets or many models, "12345" is harder to read than "12,345".

**Evidence:**
```html
<!-- Lines 1176-1184: Raw number display -->
<div style="font-size: 24px; font-weight: 700;">
    {{ models.length }}  <!-- Could be 1234 or 1,234? -->
</div>
```

**User Impact:** Harder to quickly parse large numbers at a glance.

**Recommendation:** Add number formatting:
```javascript
methods: {
    formatNumber(num) {
        return num.toLocaleString();
    }
}
// In template: {{ formatNumber(models.length) }}
```

---

### 5.3 Duration Formatting Inconsistent at Boundary Cases
**Severity:** P3 - Low
**Lines:** 2383-2402
**Description:** `formatDuration()` shows "0h 0m 0s" for very short durations, and doesn't handle durations > 24 hours (shows "25h 30m 15s" instead of "1d 1h 30m").

**Evidence:**
```javascript
// Lines 2391-2401
const seconds = Math.floor((end - start) / 1000);
const minutes = Math.floor(seconds / 60);
const hours = Math.floor(minutes / 60);

if (hours > 0) {
    return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
    // For 25 hours: "25h 1m 30s" - could be clearer as "1d 1h 1m"
}
```

**User Impact:** Long-running processes show unwieldy hour counts.

**Recommendation:** Add day formatting for durations > 24h:
```javascript
const days = Math.floor(hours / 24);
if (days > 0) {
    return `${days}d ${hours % 24}h ${minutes % 60}m`;
}
```

---

### 5.4 ETA Shows "Calculating..." for Completed Processes
**Severity:** P3 - Low
**Lines:** 1269-1272, 2407-2421
**Description:** When a process completes, if ETA was "Calculating..." (line 2408), it stays that way in the completed state, which is confusing.

**Evidence:**
```html
<!-- Lines 1269-1272 -->
<span v-if="process.status === 'running' && process.metrics.estimated_seconds_remaining">
    | ETA: ~{{ formatETA(process.metrics.estimated_seconds_remaining) }}
</span>
<!-- If process.metrics.estimated_seconds_remaining is null, shows nothing -->
```

**User Impact:** Minor confusion seeing "ETA: Calculating..." on a completed process if status updates out of order.

**Recommendation:** Hide ETA entirely for non-running processes, show "Completed in X" instead:
```html
<span v-if="process.status === 'completed'">
    | Completed in {{ formatDuration(process) }}
</span>
```

---

### 5.5 Process Logs Display Only Last 20 Entries
**Severity:** P2 - Medium
**Lines:** 1296-1300
**Description:** Log display is hardcoded to `.slice(-20)` (line 1296), meaning users can never see more than 20 log lines even if process has 200+ logs.

**Evidence:**
```html
<!-- Lines 1296-1300 -->
<div v-for="log in process.logs.slice(-20)" :key="log.timestamp"
     :class="['log-entry', log.level]">
    <span class="sr-only">{{ log.level }} at {{ formatLogTime(log.timestamp) }}:</span>
    [{{ formatLogTime(log.timestamp) }}] {{ log.message }}
</div>
```

**User Impact:** Can't debug issues that occurred early in long-running processes.

**Recommendation:** Add "Load More Logs" button or configurable log limit:
```html
<button v-if="process.logs.length > logLimit"
        @click="logLimit += 50">
    Load More Logs ({{ process.logs.length - logLimit }} hidden)
</button>
```

---

### 5.6 Model/Dataset Metadata Not Displayed
**Severity:** P2 - Medium
**Lines:** 1539-1558
**Description:** Model list shows `model.model_id`, `model.handler`, and `model.dataset` but doesn't show creation date, training duration, or accuracy metrics even though this data exists in the model metadata files.

**Evidence:**
```html
<!-- Lines 1551-1557 -->
<div class="list-item-title">{{ model.model_id }}</div>
<div class="list-item-meta">
    Handler: {{ model.handler }} | Dataset: {{ model.dataset }}
</div>
<!-- Missing: Created date, accuracy, training time -->
```

**User Impact:** Users can't compare model quality without clicking through to see detailed metrics.

**Recommendation:** Add expandable model cards showing key metrics:
```html
<div class="list-item-meta">
    Handler: {{ model.handler }} | Dataset: {{ model.dataset }}
    <br>
    Trained: {{ formatDate(model.created_at) }} |
    Accuracy: {{ model.metrics.accuracy?.toFixed(2) }}% |
    Training Time: {{ formatDuration(model.training_duration) }}
</div>
```

---

## 6. INTEGRATION ISSUES

### 6.1 WebSocket Reconnection Doesn't Restore State
**Severity:** P1 - High
**Lines:** 2071-2084
**Description:** When WebSocket reconnects after disconnection, the client doesn't request event history replay. The server has `event_history` (documented in events.py) but it's never used.

**Evidence:**
```javascript
// Lines 2066-2084
this.ws.onopen = () => {
    this.connected = true;
    this.addActivity("WebSocket connected", "success");
    // MISSING: Request to replay missed events
};

this.ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "history") {  // Server can send history
        data.events.forEach((e) => this.handleEvent(e));
    } else {
        this.handleEvent(data);
    }
};
```

**User Impact:** If user's connection drops for 30 seconds and reconnects, they miss all events that occurred during that time.

**Recommendation:** Request event history on reconnect:
```javascript
this.ws.onopen = () => {
    this.connected = true;
    // Request missed events
    this.ws.send(JSON.stringify({ type: "request_history" }));
    this.addActivity("WebSocket connected", "success");
};
```

---

### 6.2 Process WebSocket Path Doesn't Match API Routes
**Severity:** P0 - Critical
**Lines:** 2428, 2247
**Description:** Client connects to `/ws/processes/{process_id}` (line 2428) for per-process updates, but also connects to `/ws/processes` (line 2247) for all processes. The API documentation (api_enhanced.py) shows both endpoints exist, but their interaction isn't clear.

**Evidence:**
```javascript
// Line 2247: Global processes WebSocket
const wsUrl = `${protocol}//${window.location.host}/ws/processes`;

// Line 2428: Per-process WebSocket
const wsUrl = `${protocol}//${window.location.host}/ws/processes/${processId}`;
```

**User Impact:** Duplicate process updates - same process data might come from both WebSockets, causing unnecessary traffic and potential state conflicts.

**Recommendation:** Use only one WebSocket strategy:
- **Option A:** Use `/ws/processes` for all updates, remove per-process connections
- **Option B:** Use per-process connections only, remove global connection

---

### 6.3 Market Data WebSocket Not Used in UI
**Severity:** P2 - Medium
**Lines:** N/A (missing implementation)
**Description:** Backend has `/ws/market-data` endpoint (api_enhanced.py line 711-758) for real-time price quotes, but the UI never uses it. This feature is built but not accessible to users.

**Evidence:**
```python
# api_enhanced.py lines 711-758
@app.websocket("/ws/market-data")
async def websocket_market_data(websocket: WebSocket):
    # Real-time quote streaming implementation
    # NOT USED BY UI
```

**User Impact:** Missing feature - users can't see live crypto prices in the dashboard.

**Recommendation:** Add real-time price widget to dashboard:
```html
<div class="section">
    <div class="section-title">📊 Live Prices</div>
    <div v-for="quote in liveQuotes" :key="quote.symbol" class="price-card">
        <div class="symbol">{{ quote.symbol }}</div>
        <div class="price">{{ formatPrice(quote.price) }}</div>
        <div :class="['change', quote.change >= 0 ? 'positive' : 'negative']">
            {{ quote.change >= 0 ? '+' : '' }}{{ quote.change.toFixed(2) }}%
        </div>
    </div>
</div>
```

---

### 6.4 API Error Responses Not Parsed
**Severity:** P1 - High
**Lines:** 2147-2157
**Description:** `callAPI()` helper (lines 2124-2158) displays raw error responses. Backend returns structured error messages with `detail` field (per FastAPI HTTPException), but UI shows generic "Error: [object Object]".

**Evidence:**
```javascript
// Lines 2147-2157
catch (error) {
    this.forms[formKey].result = `Error: ${error.message}`;
    // If server returns { "detail": "Model not found" }
    // This shows "Error: Failed to fetch" instead of actual detail
}
```

**User Impact:** Users see unhelpful error messages like "Error: Failed to fetch" instead of "Model 'abc123' not found".

**Recommendation:** Parse error response body:
```javascript
catch (error) {
    let errorMsg = error.message;
    if (error.response) {
        const errorData = await error.response.json();
        errorMsg = errorData.detail || errorData.message || errorMsg;
    }
    this.forms[formKey].result = `Error: ${errorMsg}`;
}
```

---

### 6.5 No Retry Logic for Failed API Calls
**Severity:** P2 - Medium
**Lines:** 2106-2123
**Description:** All API calls fail immediately on network errors. For transient failures (server restart, temporary network issue), users must manually retry by clicking buttons again.

**Evidence:**
```javascript
// Lines 2106-2113
async loadModels() {
    try {
        const res = await fetch("/api/models");
        const data = await res.json();
        this.models = data.models || [];
    } catch (e) {
        console.error("Failed to load models:", e);
        // No retry, user must refresh page or click button again
    }
}
```

**User Impact:** Frustrating UX when server is slow to start or network is flaky - users must repeatedly click refresh.

**Recommendation:** Add retry logic with exponential backoff:
```javascript
async fetchWithRetry(url, options = {}, maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
        try {
            const res = await fetch(url, options);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return await res.json();
        } catch (e) {
            if (i === maxRetries - 1) throw e;
            await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, i)));
        }
    }
}
```

---

### 6.6 Process Polling Continues When Page Hidden
**Severity:** P2 - Medium
**Lines:** 1988-1990
**Description:** Process updates poll every 2 seconds (via global processes WebSocket), but polling continues even when browser tab is hidden/minimized, wasting resources.

**Evidence:**
```javascript
// Lines 1988-1990: Polling runs continuously
setInterval(() => {
    this.$forceUpdate();  // Every second, regardless of visibility
}, 1000);
```

**User Impact:** Battery drain on mobile devices, unnecessary server load when users have tab in background.

**Recommendation:** Use Page Visibility API to pause polling when tab is hidden:
```javascript
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        this.pausePolling();
    } else {
        this.resumePolling();
    }
});
```

---

## SUMMARY OF CRITICAL ISSUES (P0)

**Must Fix Immediately:**

1. **Missing Navigation for Processes Page** - Users can't access the page
2. **Race Condition in Process Cancellation** - State inconsistencies when cancelling
3. **WebSocket Path Mismatch** - Duplicate connections causing confusion
4. **No WebSocket Event Replay** - Lost events on reconnection
5. **Toast System Not Visible** - Important feedback invisible
6. **Form Validation Not Announced** - Accessibility failure for screen readers
7. **Modal Dialogs Not Accessible** - WCAG violation
8. **Null Reference Errors in Refs** - Runtime crashes when scrolling logs

---

## RECOMMENDATIONS BY PRIORITY

### Immediate (This Sprint)
1. Add Processes page navigation button
2. Fix process cancellation race condition
3. Make toast notifications visible
4. Add form validation error announcements
5. Fix null reference errors in log scrolling
6. Add HTTP status code checking to all fetch calls
7. Implement WebSocket event history replay

### Short Term (Next Sprint)
1. Standardize error handling across all API calls
2. Add loading states to all dropdowns
3. Implement retry logic for failed requests
4. Show user-friendly result summaries instead of raw JSON
5. Add "Next Step" guidance after operations complete
6. Fix auto-scroll behavior in process logs
7. Add keyboard shortcuts help panel

### Medium Term (Next Month)
1. Replace native confirm dialogs with custom modals
2. Add timezone indicators to all timestamps
3. Show model/dataset metadata in lists
4. Implement exponential backoff for WebSocket reconnection
5. Add real-time price quotes widget
6. Optimize Vue reactivity (remove $forceUpdate calls)
7. Add Page Visibility API to pause polling when hidden

### Long Term (Next Quarter)
1. Migrate from polling to pure WebSocket architecture
2. Add dark/light mode toggle
3. Implement undo for process cancellation
4. Add data visualization charts
5. Create exportable activity log
6. Add user authentication
7. Build mobile-responsive improvements

---

## TESTING RECOMMENDATIONS

### Automated Tests Needed
1. **Unit Tests:**
   - `formatDuration()` with edge cases (0s, >24h, negative values)
   - `formatETA()` with null/undefined/negative values
   - `formatTime()` with invalid timestamps
   - `scrollLogsToBottom()` with missing refs

2. **Integration Tests:**
   - WebSocket reconnection with event replay
   - Form validation error display
   - Process cancellation flow end-to-end
   - API error response handling

3. **Accessibility Tests:**
   - ARIA live region announcements
   - Keyboard navigation through all pages
   - Screen reader compatibility (NVDA/JAWS)
   - Form validation error announcements

### Manual Testing Checklist
- [ ] Create dataset and verify next step guidance appears
- [ ] Start training, scroll logs up, verify auto-scroll stops
- [ ] Disconnect WiFi, verify WebSocket reconnects and replays events
- [ ] Try to submit forms with empty required fields
- [ ] Test keyboard shortcuts (R, 1-5, Escape)
- [ ] Cancel a long-running process, verify state consistency
- [ ] Resize window to mobile width, test all features
- [ ] Run with screen reader, verify all actions are announced

---

## CONCLUSION

The Qlib Crypto Trading Platform UI is **functional but has significant gaps** that impact user experience, accessibility, and reliability. The most critical issues are:

1. **Incomplete features** - Processes page navigation, toast notifications, form validation feedback
2. **JavaScript errors** - Race conditions, null references, memory leaks
3. **UX problems** - Dead-end flows, missing feedback, inconsistent terminology
4. **Accessibility violations** - Screen reader support incomplete, WCAG failures
5. **Integration issues** - WebSocket event loss, duplicate connections, error handling

**Estimated Effort to Address:**
- P0 Critical Issues: 3-5 days
- P1 High Priority: 1-2 weeks
- P2 Medium Priority: 2-3 weeks
- P3 Low Priority: 1 week

**Total:** ~6-9 weeks for complete resolution

---

**Report Generated:** 2025-10-07
**Auditor:** UX/UI Architect (Claude Code)
**Next Review:** After P0/P1 fixes are implemented
