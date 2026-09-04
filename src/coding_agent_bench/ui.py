"""UI module for job submission and viewing."""

import json
import html

NEBIUS_PREFIX = "nebius-"


def build_submit_form_html(
    models: list[str],
    agents: list[str],
    nebius_configs: list[str],
    nebius_enabled: bool,
) -> str:
    """Build the HTML for the job submission form."""

    # Define basic fields (always visible)
    basic_fields = _build_basic_fields_html(models, agents, nebius_enabled)

    # Define optional/advanced fields
    advanced_fields = _build_advanced_fields_html(nebius_configs, nebius_enabled)

    return f"""
<div id="submit-job-section" style="margin-bottom: 2rem; padding: 1rem; border: 1px solid #ddd; border-radius: 8px; background: #fafafa;">
    <h2 style="margin-top: 0;">Submit New Job</h2>
    <form id="job-form" onsubmit="return submitJob(event)">
        <!-- Basic Fields (always visible) -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            {basic_fields}
        </div>

        <!-- Advanced Options Toggle -->
        <div style="margin-top: 1rem;">
            <button type="button" id="advanced-toggle" onclick="toggleAdvanced()" style="background: none; border: none; color: #0066cc; cursor: pointer; text-decoration: underline; padding: 0;">
                Show Advanced Options ▾
            </button>
        </div>

        <!-- Advanced Fields (hidden by default) -->
        <div id="advanced-fields" style="display: none; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #eee;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                {advanced_fields}
            </div>
        </div>

        <!-- Submit Button -->
        <div style="margin-top: 1.5rem;">
            <button type="submit" id="submit-btn" style="background: #0066cc; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 4px; cursor: pointer; font-size: 1rem;">
                Submit Job
            </button>
            <span id="submit-status" style="margin-left: 1rem; font-style: italic;"></span>
        </div>
    </form>
</div>

<script>
const MODEL_OPTIONS = {json.dumps(models)};
const AGENT_OPTIONS = {json.dumps(agents)};
const NEBIUS_CONFIGS = {json.dumps(nebius_configs)};
const NEBIUS_ENABLED = {json.dumps(nebius_enabled)};
const NEBIUS_PREFIX = '{NEBIUS_PREFIX}';

function toggleAdvanced() {{
    const adv = document.getElementById('advanced-fields');
    const btn = document.getElementById('advanced-toggle');
    if (adv.style.display === 'none') {{
        adv.style.display = 'block';
        btn.textContent = 'Hide Advanced Options ▴';
    }} else {{
        adv.style.display = 'none';
        btn.textContent = 'Show Advanced Options ▾';
    }}
}}

function validateForm() {{
    const errors = [];
    const jobName = document.getElementById('job_name').value.trim();
    const agent = document.getElementById('agent').value;
    const dataset = document.getElementById('dataset').value.trim();
    const modelName = document.getElementById('model_name').value;
    const serverUrl = document.getElementById('server_url').value.trim();

    if (!jobName) errors.push('Job name is required');
    if (!agent) errors.push('Agent is required');
    if (!dataset) errors.push('Dataset is required');
    if (!modelName) errors.push('Model name is required');
    if (!serverUrl) errors.push('Server URL is required');

    // Validate server_url format
    if (serverUrl) {{
        if (!serverUrl.startsWith(NEBIUS_PREFIX) && !serverUrl.match(/^https?:\\/\\/[^\\s]+$/)) {{
            errors.push('Server URL must be a valid URL (http:// or https://)');
        }}
        if (serverUrl.startsWith(NEBIUS_PREFIX)) {{
            const config = serverUrl.substring(NEBIUS_PREFIX.length);
            if (NEBIUS_ENABLED && NEBIUS_CONFIGS.length > 0 && !NEBIUS_CONFIGS.includes(config)) {{
                errors.push('Unknown nebius resource config. Choose from: ' + NEBIUS_CONFIGS.join(', '));
            }}
            if (!NEBIUS_ENABLED) {{
                errors.push('Nebius is not enabled on this server');
            }}
        }}
    }}

    // Validate numeric fields
    const nConcurrent = document.getElementById('n_concurrent').value;
    if (nConcurrent && (isNaN(nConcurrent) || parseInt(nConcurrent) < 1)) {{
        errors.push('n_concurrent must be a positive integer');
    }}
    const nTasks = document.getElementById('n_tasks').value;
    if (nTasks && (isNaN(nTasks) || parseInt(nTasks) < 1)) {{
        errors.push('n_tasks must be a positive integer');
    }}
    const modelMaxLen = document.getElementById('model_max_len').value;
    if (modelMaxLen && (isNaN(modelMaxLen) || parseInt(modelMaxLen) < 1)) {{
        errors.push('model_max_len must be a positive integer');
    }}

    if (errors.length > 0) {{
        alert('Validation errors:\\n' + errors.join('\\n'));
        return false;
    }}
    return true;
}}

async function submitJob(event) {{
    event.preventDefault();
    if (!validateForm()) return false;

    const btn = document.getElementById('submit-btn');
    const status = document.getElementById('submit-status');
    btn.disabled = true;
    btn.textContent = 'Submitting...';
    status.textContent = '';
    status.style.color = '#666';

    const formData = {{
        job_name: document.getElementById('job_name').value.trim(),
        agent: document.getElementById('agent').value,
        dataset: document.getElementById('dataset').value.trim(),
        model_name: document.getElementById('model_name').value,
        server_url: document.getElementById('server_url').value.trim(),
        n_concurrent: parseInt(document.getElementById('n_concurrent').value) || 1,
    }};

    // Advanced fields
    const datasetPattern = document.getElementById('dataset_pattern').value.trim();
    if (datasetPattern) formData.dataset_pattern = datasetPattern;

    const nTasks = document.getElementById('n_tasks').value.trim();
    if (nTasks) formData.n_tasks = parseInt(nTasks);

    const modelMaxLen = document.getElementById('model_max_len').value.trim();
    if (modelMaxLen) formData.model_max_len = parseInt(modelMaxLen);

    const beforeScript = document.getElementById('before_script').value.trim();
    if (beforeScript) formData.before_script = beforeScript;

    const agentVersion = document.getElementById('agent_version').value.trim();
    if (agentVersion) formData.agent_version = agentVersion;

    try {{
        const apiKey = localStorage.getItem('coding_agent_bench_api_key');
        const response = await fetch('/jobs', {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
                'X-API-Key': apiKey || '',
            }},
            body: JSON.stringify(formData),
        }});

        const data = await response.json();

        if (!response.ok) {{
            throw new Error(data.detail || `HTTP ${{response.status}}`);
        }}

        status.textContent = `Job created: ${{data.job_id}}`;
        status.style.color = 'green';
        document.getElementById('job-form').reset();

        // Refresh job list after a short delay
        setTimeout(() => location.reload(), 1500);
    }} catch (err) {{
        status.textContent = `Error: ${{err.message}}`;
        status.style.color = 'red';
        btn.disabled = false;
        btn.textContent = 'Submit Job';
    }}
}}

function checkApiKey() {{
    const apiKey = localStorage.getItem('coding_agent_bench_api_key');
    const status = document.getElementById('submit-status');
    if (!apiKey) {{
        status.textContent = '⚠ API key not set. Set it in the header above first.';
        status.style.color = '#cc6600';
    }}
}}

checkApiKey();
</script>
"""


def _build_basic_fields_html(models: list[str], agents: list[str], nebius_enabled: bool) -> str:
    """Build HTML for the basic (always visible) form fields."""
    model_options = "".join(
        f'<option value="{html.escape(m)}">{html.escape(m)}</option>' for m in models
    )
    agent_options = "".join(
        f'<option value="{html.escape(a)}">{html.escape(a)}</option>' for a in agents
    )

    nebius_help = ""
    if nebius_enabled:
        nebius_help = '<br><small style="color: #666;">Or use nebius-&lt;config&gt; (e.g., nebius-h200)</small>'
    else:
        nebius_help = '<br><small style="color: #999;">Nebius instances not enabled</small>'

    return f"""
        <div>
            <label for="job_name" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Job Name *</label>
            <input type="text" id="job_name" name="job_name" required
                   style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;"
                   placeholder="my-benchmark-job">
        </div>
        <div>
            <label for="agent" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Agent *</label>
            <select id="agent" name="agent" required
                    style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;">
                {agent_options}
            </select>
        </div>
        <div>
            <label for="dataset" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Dataset *</label>
            <input type="text" id="dataset" name="dataset" required
                   style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;"
                   placeholder="e.g., humaneval">
        </div>
        <div>
            <label for="model_name" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Model *</label>
            <select id="model_name" name="model_name" required
                    style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;">
                {model_options}
            </select>
        </div>
        <div>
            <label for="server_url" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Server URL *</label>
            <input type="text" id="server_url" name="server_url" required
                   style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;"
                   placeholder="http://localhost:8000">
            {nebius_help}
        </div>
        <div>
            <label for="n_concurrent" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Concurrent Tasks</label>
            <input type="number" id="n_concurrent" name="n_concurrent" value="1" min="1"
                   style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;">
        </div>
"""


def _build_advanced_fields_html(nebius_configs: list[str], nebius_enabled: bool) -> str:
    """Build HTML for the optional/advanced form fields."""
    return """
        <div>
            <label for="dataset_pattern" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Dataset Pattern</label>
            <input type="text" id="dataset_pattern" name="dataset_pattern"
                   style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;"
                   placeholder="e.g., *hard*">
        </div>
        <div>
            <label for="n_tasks" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Total Tasks</label>
            <input type="number" id="n_tasks" name="n_tasks" min="1"
                   style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;"
                   placeholder="Leave empty for all">
        </div>
        <div>
            <label for="model_max_len" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Max Context Length</label>
            <input type="number" id="model_max_len" name="model_max_len" min="1"
                   style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;"
                   placeholder="Leave empty for default">
        </div>
        <div>
            <label for="agent_version" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Agent Version</label>
            <input type="text" id="agent_version" name="agent_version"
                   style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;"
                   placeholder="Leave empty for default">
        </div>
        <div style="grid-column: 1 / -1;">
            <label for="before_script" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Before Script</label>
            <textarea id="before_script" name="before_script" rows="3"
                      style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-family: monospace;"
                      placeholder="Commands to run before execution..."></textarea>
        </div>
"""
