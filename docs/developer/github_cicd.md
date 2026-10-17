# GitHub CICD

`.github/workflows/deploy.yml` deploys both Kustomize applications with
`oc`:

- A merged pull request targeting `stage` deploys to `STAGE_NAMESPACE`.
- A version tag such as `v0.3.0` deploys to `PROD_NAMESPACE`.

The workflow expects the Secrets to already exist in the target namespace. It
only verifies them and applies the two Kustomizations. The files below are safe
templates for local reference only; fill them in locally and do not commit them:

- `deploy/storage/base/secret.example.yaml`
- `deploy/job-queue/base/secret.example.yaml`
- `deploy/job-queue/base/nebius-secret.example.yaml`
- `deploy/intake-poller/base/secret.example.yaml`

Before the first CI deployment, apply the filled-in templates to each target
namespace:

```sh
oc project <project>
oc apply -f deploy/storage/base/secret.yaml
oc apply -f deploy/job-queue/base/secret.yaml
oc apply -f deploy/job-queue/base/nebius-secret.yaml
oc apply -f deploy/intake-poller/base/secret.yaml
```

Repeat these commands for both stage and production. The CI workflow checks for
`job-queue-secret` before applying anything. It also checks for `intake-poller-secret` 
before applying the intake poller. `nebius-secret` is optional.

## OpenShift setup

Create one namespace for stage and one for production. In each namespace, create a
deployer ServiceAccount and grant it namespace-admin permissions. The `admin` role
is used here because the Kustomizations create Roles and RoleBindings. It does **not**
grant permission to use the OpenShift `anyuid` SCC, however. The deployer must be
granted that SCC separately so it can apply the two `anyuid` RoleBindings in
`deploy/job-queue/base`.

Run the following once for each namespace (as a namespace administrator):

```sh
for namespace in <stage-namespace> <production-namespace>; do
  oc create serviceaccount github-deployer -n "$namespace"
  oc adm policy add-role-to-user admin -z github-deployer -n "$namespace"
  oc adm policy add-scc-to-user anyuid -z github-deployer -n "$namespace"
done
```

The last command is required even when the ServiceAccount has the `admin` role.
It gives the deployer `use` on the `anyuid` SCC, which is required by Kubernetes
RBAC's escalation check when applying these RoleBindings:

- `harbor-orchestrator-anyuid` for the `harbor-orchestrator` ServiceAccount
- `harbor-task-anyuid` for the `harbor-task` ServiceAccount

Run the SCC command as a cluster administrator. If the cluster policy does not
allow a namespace-scoped SCC grant, a cluster administrator must create the
equivalent RoleBinding for `system:openshift:scc:anyuid` in each namespace.

The deployment workflow reads `harbor-storage`, `job-queue-secret`, and optionally
`intake-poller-secret` before applying the Kustomizations. The `admin` role normally
includes Secret read access. If a cluster uses a narrower custom deployer role, it
must grant `get` on Secrets (and no Secret write access is needed just for this
workflow). Create and bind a dedicated read role in each namespace:

```sh
for namespace in <stage-namespace> <production-namespace>; do
  oc create role github-deployer-secret-reader \
    --verb=get --resource=secrets \
    -n "$namespace" --dry-run=client -o yaml | oc apply -f -
  oc adm policy add-role-to-user github-deployer-secret-reader \
    -z github-deployer -n "$namespace"
done
```

If using a custom role instead of `admin`, the deployer needs these namespaced
permissions for the resources in `deploy/`:

| API group                   | Resources                                                             | Required verbs                     |
| --------------------------- | --------------------------------------------------------------------- | ---------------------------------- |
| `""`                        | `persistentvolumeclaims`, `services`, `serviceaccounts`, `configmaps` | `get`, `create`, `patch`, `update` |
| `""`                        | `secrets`                                                             | `get`                              |
| `apps`                      | `deployments`                                                         | `get`, `create`, `patch`, `update` |
| `batch`                     | `cronjobs`                                                            | `get`, `create`, `patch`, `update` |
| `route.openshift.io`        | `routes`                                                              | `get`, `create`, `patch`, `update` |
| `rbac.authorization.k8s.io` | `roles`, `rolebindings`                                               | `get`, `create`, `patch`, `update` |

The workflow also needs `get`, `list`, and `watch` on `pods` and `replicasets` for
rollout status, and `patch` on `deployments` for the stage rollout restart. The
deployer must be allowed to bind the `harbor-orchestrator` Role and use the
`system:openshift:scc:anyuid` ClusterRole. Granting `use` on the SCC to the
deployer, as shown above, satisfies the latter escalation check. For a custom
deployer role, either grant it every permission contained in the Role it creates
or grant the narrowly scoped `escalate` permission on that Role; it also needs
the corresponding `bind` permission when binding a Role or ClusterRole whose
permissions it does not already hold. A custom role must not grant arbitrary
cluster-admin permissions just to make RoleBinding creation work.

Verify the permission with the same identity used by CI:

```sh
oc auth can-i get secret/job-queue-secret \
  --as=system:serviceaccount:<namespace>:github-deployer -n <namespace>
```

Create a token for each ServiceAccount. The duration is subject to the cluster's
token policy; omit `--duration` if the cluster rejects the requested duration:

```sh
oc create token github-deployer -n <stage-namespace> --duration=8760h
oc create token github-deployer -n <production-namespace> --duration=8760h
```

Store the two outputs separately as the `OPENSHIFT_TOKEN` secret in the GitHub
`stage` and `production` environments. Do not use one token for both environments.

The OpenShift service CA and service-serving certificate operators must be
available. They create `intake-poller-ca` and `job-queue-tls` when the manifests
are applied. The cluster must also be able to pull the image from GHCR.

Verify each token locally:

```sh
oc login --server=<server> --token=<token>
oc project <namespace>
oc auth can-i create deployments
oc auth can-i create rolebindings
oc auth can-i use scc/anyuid \
  --as=system:serviceaccount:<namespace>:github-deployer \
  -n <namespace>
```

## GitHub setup

Create GitHub repository variables:

| Variable          | Value                          |
| ----------------- | ------------------------------ |
| `STAGE_NAMESPACE` | OpenShift stage namespace      |
| `PROD_NAMESPACE`  | OpenShift production namespace |

Create GitHub Environments named `stage` and `production`. Add the OpenShift
connection secrets to both environments, using environment-specific values.
Production can also require an approval reviewer:

| Secret             | Purpose                                         |
| ------------------ | ----------------------------------------------- |
| `OPENSHIFT_SERVER` | OpenShift API URL                               |
| `OPENSHIFT_TOKEN`  | Token for the namespace deployer ServiceAccount |

The application secrets listed in the example files are not GitHub secrets. They
are applied directly to OpenShift before deployment.

The workflow uses the `stage` environment for merged `STAGE` pull requests and
the `production` environment for `v*` tags. It does not run for an unmerged pull
request or for ordinary branch pushes.
