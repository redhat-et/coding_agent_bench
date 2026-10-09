# Queue Service OpenShift Setup

## Steps

1. Log in to your cluster:

    ```sh
    oc login --server=<server> --token=<token>
    ```

2. Copy the Secret templates locally and do not commit the resulting files:

    ```sh
    cp deploy/storage/base/secret.example.yaml deploy/storage/base/secret.yaml
    cp deploy/job-queue/base/secret.example.yaml deploy/job-queue/base/secret.yaml
    ```

    Fill in the secret values, then apply the Secrets separately to the target project before deploying the services:

    ```sh
    oc apply -f deploy/storage/base/secret.yaml -n <project>
    oc apply -f deploy/job-queue/base/secret.yaml -n <project>
    ```

3. Deploy the RustFS service to store job artifacts:

    ```sh
    oc apply -k deploy/storage/overlays/prod -n <project>
    ```

4. Deploy the Job Queue service:

    ```sh
    oc apply -k deploy/job-queue/overlays/prod -n <project>
    ```

5. Get the route for the deployed API service:

    ```sh
    export JOB_QUEUE_URL="https://$(oc get route job-queue-route -n <project> --output jsonpath='{.spec.host}')"
    open $JOB_QUEUE_URL/docs
    ```

## Next Steps

1. [Configure the queue service to use Nebius](./nebius.md).
2. [Configure the intake poller to automatically load jobs from a Google Sheet](./intake_poller.md)
