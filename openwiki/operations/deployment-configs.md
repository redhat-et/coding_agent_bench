---
type: component
title: Deployment Configurations
description: OpenShift deployment manifests for the queue service, MinIO artifact storage, and vLLM model servers.
tags: [deployment, openshift, kubernetes, manifests]
---

# Deployment Configurations

OpenShift deployment manifests for the queue service, MinIO artifact storage, vLLM model servers, and supporting infrastructure.

## Queue Service

### `deploy/job-queue-service.yml`

Deploys the FastAPI queue service:

```yaml
---
# PVC for SQLite database
kind: PersistentVolumeClaim
metadata:
  name: job-queue-pvc
spec:
  storageClassName: gp3
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi

---
# Deployment
kind: Deployment
metadata:
  name: job-queue
spec:
  template:
    spec:
      serviceAccountName: harbor-orchestrator
      containers:
      - image: ghcr.io/redhat-et/coding_agent_bench:latest
        command: ["/bin/sh", "-c"]
        args:
          - uv run uvicorn coding_agent_bench.api:app --host 0.0.0.0 --port 8000
        env:
        - name: JOB_STORE_PATH
          value: /app/data/jobs.db
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: job-queue-secret
              key: API_KEY
        resources:
          requests: {cpu: "1", memory: "500M"}
          limits: {cpu: "1", memory: "1Gi"}
        volumeMounts:
        - mountPath: /app/data
          name: data

---
# Service
kind: Service
metadata:
  name: job-queue-service
spec:
  type: ClusterIP
  ports:
  - name: http
    port: 80
    targetPort: 8000

---
# Route
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: job-queue-route
spec:
  tls:
    termination: edge
```

## MinIO

### `deploy/harbor-minio.yml`

Deploys MinIO for benchmark result storage:

```yaml
---
kind: PersistentVolumeClaim
metadata:
  name: harbor-minio
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 50Gi

---
kind: Deployment
metadata:
  name: harbor-minio
spec:
  template:
    spec:
      containers:
      - image: minio/minio
        command: ["minio", "server", "/data", "--console-address", ":9001"]
        env:
        - name: MINIO_ROOT_USER
          value: minioadmin
        - name: MINIO_ROOT_PASSWORD
          value: minioadmin
        ports:
        - containerPort: 9000  # API
        - containerPort: 9001  # Console
        volumeMounts:
        - mountPath: /data
          name: data

---
kind: Service
metadata:
  name: harbor-minio
spec:
  ports:
  - name: api
    port: 9000
  - name: console
    port: 9001
```

## Service Accounts

### `deploy/harbor-orchestrator-sa.yml`

Service account for the orchestrator pod (full API access for job management).

### `deploy/harbor-task-sa.yml`

Service account for task pods (anyuid SCC only, no API access).

## Model Deployment Manifests

### `deploy/Qwen3.6_27b_FP8.yml`

Pre-generated manifest for `RedHatAI/Qwen3.6-27B-FP8` on xlarge GPU pool (4x L40S, 192 GB total).

### `deploy/Qwen3.6_35b_NVFP4.yml`

Pre-generated manifest for `RedHatAI/Qwen3.6-35B-NVFP4` on xlarge GPU pool.

### `deploy/qwen-all-in-one.yml`

Combined deployment configuration for Qwen models.

## Setup Steps

1. **Login to OpenShift:**
   ```bash
   oc login --server=<server> --token=<token>
   oc project <project>
   ```

2. **Create MinIO:**
   ```bash
   oc apply -f deploy/harbor-minio.yml
   ```

3. **Create service accounts:**
   ```bash
   oc apply -f deploy/harbor-orchestrator-sa.yml
   oc apply -f deploy/harbor-task-sa.yml
   ```

4. **Create API key secret:**
   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: job-queue-secret
   stringData:
     API_KEY: <your-api-key>
   ```

5. **Deploy queue service:**
   ```bash
   oc apply -f deploy/job-queue-service.yml
   ```

6. **Get route:**
   ```bash
   oc get route job-queue-route --output jsonpath='{.spec.host}'
   ```

## Evidence

- Source: `deploy/*.yml`
- Deployment README: `deploy/README.md`
- Queue service source: `src/coding_agent_bench/api.py`
