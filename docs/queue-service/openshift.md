# Queue Service OpenShift Setup

## Steps

1. Log in to your cluster and project:

    ```sh
    oc login --server=<server> --token=<token>
    oc project <project>
    ```

2. Create the MinIO service for artifact storage:
    
    ```sh
    oc apply -f deploy/harbor-minio.yml
    ```
    
    Note: the default username and password are `(minioadmin, minioadmin)`.
    You can update this in the deployment file if needed.

3. Create the orchestrator and task service accounts:
    
    ```sh
    oc apply -f deploy/harbor-orchestrator-sa.yml
    oc apply -f deploy/harbor-task-sa.yml
    ```

4. Create a secret file named `job-queue-secret` with the queue service's `API_KEY` and any queue or Nebius settings, then apply it:
    
    ```yaml
    apiVersion: v1
    kind: Secret
    metadata:
      name:  job-queue-secret
    stringData:
      API_KEY: <your-api-key>
    type: Opaque
    ```

5. Create the queue service:
    
    ```sh
    oc apply -f deploy/job-queue-service.yml
    ```

6. (Optional) To run jobs against OpenRouter (`server_url: openrouter`), create
   an `openrouter-api-key` secret. Job pods mount it automatically (it is
   optional, so non-OpenRouter jobs are unaffected):
    ```yaml
    apiVersion: v1
    kind: Secret
    metadata:
      name: openrouter-api-key
    stringData:
      OPENROUTER_API_KEY: <your-openrouter-api-key>
    type: Opaque
    ```
    The queue service itself also needs `OPENROUTER_API_KEY` in its environment
    to validate OpenRouter jobs at request time. Add it to `job-queue-secret`
    (which the service already loads) or `envFrom` the `openrouter-api-key`
    secret in `deploy/job-queue-service.yml`.

    The queue listens on HTTPS inside the cluster. OpenShift's service-serving
    certificate operator creates the `job-queue-tls` Secret referenced by the
    Deployment, and the Route uses re-encryption so traffic remains encrypted
    from the router to the queue pod. Wait for that Secret to appear before
    troubleshooting pod startup:
    ```sh
    oc get secret job-queue-tls
    ```

Get the route for the deployed service:

```sh
oc get route job-queue-route --output jsonpath='{.spec.host}'
```

Set `JOB_QUEUE_URL` in `intake-poller-secret` to this HTTPS route before
applying `deploy/intake-cronjob.yml`.

Check that the application is live by visiting the docs:

```sh
export JOB_QUEUE_URL="https://$(oc get route job-queue-route --output jsonpath='{.spec.host}')"
open $JOB_QUEUE_URL/docs
```
