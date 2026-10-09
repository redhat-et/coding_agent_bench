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
    advanced_fields = _build_advanced_fields_html()

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

function parseGitHubRepository(value) {{
    try {{
        const input = value.trim();
        let parts;
        if (input.includes('://')) {{
            const url = new URL(input);
            if (url.protocol !== 'https:' || url.hostname.toLowerCase() !== 'github.com' || url.port || url.username || url.password || url.search || url.hash) return null;
            parts = url.pathname.split('/').filter(Boolean);
        }} else {{
            parts = input.split('/');
        }}
        if (parts.length !== 2) return null;
        const repo = parts[1].replace(/\\.git$/i, '');
        if (!/^[A-Za-z0-9_.-]+$/.test(parts[0]) || !/^[A-Za-z0-9_.-]+$/.test(repo)) return null;
        return {{ owner: parts[0], repo }};
    }} catch (_) {{
        return null;
    }}
}}

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
    const githubRepo = document.getElementById('github_repo').value.trim();
    const modelName = document.getElementById('model_name').value;
    const serverUrl = document.getElementById('server_url').value.trim();

    if (!jobName) errors.push('Job name is required');
    if (!agent) errors.push('Agent is required');
    if (!dataset && !githubRepo) errors.push('Enter a Harbor dataset or GitHub repository');
    if (githubRepo && !parseGitHubRepository(githubRepo)) errors.push('GitHub repository must be owner/repo or an HTTPS URL like https://github.com/owner/repo');
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
    const githubTokenInput = document.getElementById('github_token');
    const headers = {{ 'Content-Type': 'application/json' }};

    try {{
        const apiKey = localStorage.getItem('coding_agent_bench_api_key');
        if (!apiKey) throw new Error('Set the queue API key before submitting a job.');
        const githubRepoValue = document.getElementById('github_repo').value.trim();
        const githubRef = document.getElementById('github_ref').value.trim();
        const githubSubdirectory = document.getElementById('github_subdirectory').value.trim();
        const githubRepository = githubRepoValue ? parseGitHubRepository(githubRepoValue) : null;
        const githubRepositoryUrl = githubRepository
            ? `https://github.com/${{githubRepository.owner}}/${{githubRepository.repo}}`
            : null;
        let dataset = document.getElementById('dataset').value.trim();

        if (githubRepository) {{
            dataset = `github.com/${{githubRepository.owner}}/${{githubRepository.repo}}${{githubRef ? `@${{githubRef}}` : ''}}`;
            if (githubTokenInput.value) headers['X-GitHub-Token'] = githubTokenInput.value;
        }}
        githubTokenInput.value = '';
        headers['X-API-Key'] = apiKey;

        const formData = {{
            job_name: document.getElementById('job_name').value.trim(),
            agent: document.getElementById('agent').value,
            dataset,
            model_name: document.getElementById('model_name').value,
            server_url: document.getElementById('server_url').value.trim(),
            n_concurrent: parseInt(document.getElementById('n_concurrent').value) || 1,
        }};
        const skills = document.getElementById('skills').value
            .split(',')
            .map((skill) => skill.trim())
            .filter(Boolean);
        if (skills.length) formData.skills = skills;
        if (githubRepository) {{
            formData.github_dataset = {{
                repository_url: githubRepositoryUrl,
                ref: githubRef,
                subdirectory: githubSubdirectory,
            }};
        }}

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

        const response = await fetch('/jobs', {{
            method: 'POST',
            headers,
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
    }} finally {{
        githubTokenInput.value = '';
        delete headers['X-GitHub-Token'];
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
            <label for="dataset" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Harbor Dataset (optional when using GitHub)</label>
            <input type="text" id="dataset" name="dataset"
                   style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;"
                   placeholder="Harbor dataset name (or leave blank when using GitHub)">
        </div>
        <div style="grid-column: 1 / -1;">
            <label for="github_repo" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">GitHub Repository Dataset (optional)</label>
            <input type="text" id="github_repo" autocomplete="off"
                   style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;"
                   placeholder="owner/repository or https://github.com/owner/repository">
            <small style="display: block; color: #666; margin-top: 0.25rem;">The job pod downloads this repository and runs Harbor on the selected directory. Public repositories need no GitHub token. An optional token is held only in queue memory, passed to the pod through stdin, and discarded after preparation.</small>
        </div>
        <div>
            <label for="github_ref" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">GitHub Branch, Tag, or Commit</label>
            <input type="text" id="github_ref" autocomplete="off"
                   style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;"
                   placeholder="Default branch">
        </div>
        <div>
            <label for="github_subdirectory" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Dataset Directory in Repository</label>
            <input type="text" id="github_subdirectory" autocomplete="off"
                   style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;"
                   value="tasks" placeholder="e.g., benchmarks/my-dataset">
            <small style="display: block; color: #666; margin-top: 0.25rem;">Defaults to tasks/. Set a path relative to the repository root; clear the field to use the repository root.</small>
        </div>
        <div>
            <label for="github_token" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">GitHub Token (private repos only)</label>
            <input type="password" id="github_token" autocomplete="new-password" autocapitalize="off" spellcheck="false"
                   style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;"
                   placeholder="Read-only access to this repository">
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


def _build_advanced_fields_html() -> str:
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
            <label for="skills" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Skills</label>
            <textarea id="skills" name="skills" rows="2"
                      style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-family: monospace;"
                      placeholder="Comma-separated Git sources, e.g. org/repo@main"></textarea>
            <small style="color: #666;">Provide Git sources separated by commas.</small>
        </div>
        <div style="grid-column: 1 / -1;">
            <label for="before_script" style="display: block; font-weight: bold; margin-bottom: 0.25rem;">Before Script</label>
            <textarea id="before_script" name="before_script" rows="3"
                      style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-family: monospace;"
                      placeholder="Commands to run before execution..."></textarea>
        </div>
"""
