# Queue Service Local Setup [Development]

This setup is primarily for developer testing of the queue service.

The queue service API server runs locally, but all other components still run on OpenShift.

## Steps

1. Clone the repository and install dependencies:

    ```sh
    git clone https://github.com/redhat-et/coding_agent_bench.git
    cd coding_agent_bench

    uv venv
    uv sync
    ```

2. Log into your OpenShift cluster and project, or create a new project:

    ```sh
    oc login --server=<server> --token=<token>
    oc project <project>
    ```

3. Copy the storage secret template locally:

    ```sh
    cp deploy/storage/base/secret.example.yaml deploy/storage/base/secret.yaml
    ```

    Fill in the values, then apply the secret:

    ```sh
    oc apply -f deploy/storage/base/secret.yaml
    ```

4. Create the RustFS service for artifact storage:

    ```sh
    oc apply -k deploy/storage/overlays/prod
    ```

5. Apply the service accounts for the orchestrator and task pods:

    ```sh
    oc kustomize deploy/job-queue | yq '. | select(.metadata.name == "harbor-orchestrator*")' | oc apply -f -
    oc kustomize deploy/job-queue | yq '. | select(.metadata.name == "harbor-task*")' | oc apply -f -
    ```

6. Copy the `.env.example` file to `.env`:

    ```sh
    cp .env.example .env
    ```

    Ensure the following environment variables are set:

    ```
    API_KEY=<api_key>
    JOB_STORE_PATH=jobs.db
    STORAGE_ENDPOINT_URL=http://harbor-storage:9000
    ```

    If using Nebius, add [environment variables for Nebius](./nebius.md#local)

7. Start the queue service locally:

    ```sh
    uv run uvicorn coding_agent_bench.api:app --port 8080
    ```

8. Open the UI at [http://localhost:8080](http://localhost:8080) and test your features. Submitted jobs will run on the logged in OpenShift cluster.
