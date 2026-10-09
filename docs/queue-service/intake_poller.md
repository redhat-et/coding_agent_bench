# Intake Poller

The `intake-poller` CronJob (`deploy/intake-cronjob.yml`) reads benchmark
requests from a Google Sheet and submits approved rows to the job queue.
Job status (Queued, Running, Paused, Completed, Failed, Cancelled) and any
errors are written back to the sheet, which is the single source of truth
for requesters. A Nebius-preempted job shows as Paused while the queue
restarts and resumes it automatically. It runs every 6 hours.

To deploy the intake CronJob, first create its separate poller secret:

```sh
cp deploy/intake-poller/base/secret.example.yaml deploy/intake-poller/base/secret.yaml
```

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: intake-poller-secret
type: Opaque
stringData:
  GOOGLE_SHEET_ID: <google-sheet-id>
  JOB_QUEUE_URL: https://job-queue-service
  AUTO_APPROVE: "false"
  ALLOW_INSECURE_QUEUE_HTTP: "false"
  service-account.json: |-
    <service-account-content>
```

```sh
oc apply -f deploy/intake-poller/base/secret.yaml
```

See the sections below for more information on these secret values.

Then deploy with kustomize:

```sh
oc apply -k deploy/intake-poller/prod
```

## Google Sheet

The poller reads from a tab named `Queue` (not the raw `Form Responses 1` tab),
laid out in the exact order of `coding_agent_bench.intake.config.Column`. A
scheduled Apps Script macro (`scripts/manual/intake_queue_sync.gs`) copies new
form responses into that tab, mapping columns by header name so the form's
question order can change without breaking the poller. Install the macro via
Extensions > Apps Script and add a form-submit or time-driven trigger for
`syncFormResponsesToQueue`.

## Secrets

**`job-queue-secret`** — shared with the job-queue Deployment. Keep `API_KEY`
and queue-service settings here. Poller-only settings belong in the
separate `intake-poller-secret` described below.

| Key | Description |
|-----|-------------|
| `API_KEY` | API key for the job-queue service |

The intake payload intentionally leaves concurrency and model context length
unset. The queue service applies its configured defaults and model-specific
`ModelConfig` values. Do not add plaintext `http://` endpoints to the
poller secret; `ALLOW_INSECURE_QUEUE_HTTP=true` is supported only for local
development.

**`intake-poller-secret`** — read only by the intake CronJob. Create it with:

| Key | Description |
|-----|-------------|
| `GOOGLE_SHEET_ID` | ID of the intake Google Sheet (the value between `/d/` and `/edit` in its URL) |
| `JOB_QUEUE_URL` | HTTPS URL for the queue API. Use the cluster's TLS/mTLS endpoint; the poller fails closed instead of using plaintext HTTP. |
| `AUTO_APPROVE` | `"true"` to auto-submit rows with a blank status, otherwise `"false"` |
| `ALLOW_INSECURE_QUEUE_HTTP` | Set to `"true"` when the queue is served over HTTP (e.g. locally), otherwise `"false"` |
| `service-account.json` | Content of a GCP service account that has read access to the Google Sheet. |

## Queue TLS

`deploy/job-queue/deployment.yaml` enables OpenShift's service-serving certificate
operator with the `service.beta.openshift.io/serving-cert-secret-name`
annotation. The operator creates `job-queue-tls` with `tls.crt`, `tls.key`, and
the service CA; the queue mounts that Secret and Uvicorn serves HTTPS on port
1.    The Service exposes it as port 443 and the Route uses `reencrypt`
termination, keeping router-to-pod traffic encrypted as well. Apply the
manifest before starting the poller and wait for `job-queue-tls` to be created.

The URL check runs before a job is queued and again immediately before its
worker pod is created, covering DNS changes and private or link-local targets.
Managed Nebius endpoints are checked as public provider-generated addresses.

For managed Nebius capacity, an approver can set `SERVER_URL` to an explicit
resource token such as `nebius-h200` (or `nebius-b200x8`). The queue service
validates that token, provisions the instance, and supplies its endpoint after
approval; the requester never needs to know that endpoint.

Each submitted Queue row carries a deterministic idempotency key. If the
CronJob is retried after a network timeout, the queue API returns the original
job instead of creating a duplicate.
