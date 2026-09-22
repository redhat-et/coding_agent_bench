# Queue Service Local Setup [Development]

This setup is primarily for developer testing of the queue service.

The queue service API server runs locally, but all other components still run on OpenShift.

## Steps

1. Clone the repository and install dependencies

    ```sh
    git clone https://github.com/redhat-et/coding_agent_bench.git
    cd coding_agent_bench

    uv venv
    uv sync
    ```

2. Copy the `.env.example` file to `.env` and fill in the `API_KEY` variable

    ```sh
    cp .env.example .env
    ```

    (Optional) If using Nebius, add environment variables for Nebius

3. Log into your OpenShift cluster and project, or create a new project

    ```sh
    oc project coding-agent-leaderboard
    ```

4. Create the MinIO service for artifact storage:

    ```sh
    oc apply -f deploy/harbor-minio.yml
    ```

    Note: the default username and password are `(minioadmin, minioadmin)`.
    You can update this in the deployment file if needed.

5. Apply the service accounts for the orchestrator and task pods

    ```sh
    oc apply -f deploy/harbor-orchestrator-sa.yml
    oc apply -f deploy/harbor-task-sa.yml
    ```

6. Start the queue service locally

    ```sh
    uv run uvicorn coding_agent_bench.api:app --port 8080
    ```

7. Open the UI at [http://localhost:8080](http://localhost:8080) and test your features
