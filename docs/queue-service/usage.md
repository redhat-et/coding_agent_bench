# Queue Service Usage

Before using the below commands, make sure you have set the `JOB_QUEUE_URL` in your environment.

## Submit A Job

Queue up a new benchmark task:

```sh
# Request
curl -X POST $JOB_QUEUE_URL/jobs \
    -d '{"job_name": "test", "agent": "pi", "dataset": "swe-bench/swe-bench-verified", "model_name": "qwen3.6-27b", "server_url": "<server-url>", "n_tasks": 1}' \
    -H "Content-Type: application/json" \
    -H "X-API-Key: <your-api-key>"

# Response
# {
#     "message":"Job created.",
#     "job_id":"b5ef13c8-8909-4bf1-b5b1-43354e9f395c", 
#     ... 
# }
```

OR

Open the UI and submit a job there:

```sh
open $JOB_QUEUE_URL/ui
```

## View the Queue

View the queued/running/completed tasks:

```sh
open $JOB_QUEUE_URL/ui
```

Or list them from the API:

```sh
curl $JOB_QUEUE_URL/jobs -H "X-API-Key: <your-api-key>"
```

## Cancel Jobs

Cancel a running or queued job:

```sh
curl -X DELETE $JOB_QUEUE_URL/jobs/<job_id> -H "X-API-Key: <your-api-key>"
```
