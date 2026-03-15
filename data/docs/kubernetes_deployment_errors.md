# Kubernetes & Deployment Errors in CI/CD

## CrashLoopBackOff

**Root Cause**: The container starts, crashes, and Kubernetes keeps restarting it with exponential backoff delays. Common causes:
- Application crashes on startup (missing config, bad env var, segfault)
- Liveness probe failing immediately
- Missing dependencies (database not ready, service unreachable)
- Wrong command or entrypoint in the Pod spec

**Fix**:
1. Check container logs: `kubectl logs <pod-name> --previous` (shows logs from the crashed container).
2. Describe the pod for events: `kubectl describe pod <pod-name>`.
3. Run the container locally with the same env vars to reproduce.
4. Add an `initContainer` to wait for dependencies:
```yaml
initContainers:
  - name: wait-for-db
    image: busybox
    command: ['sh', '-c', 'until nc -z db-service 5432; do sleep 2; done']
```
5. Increase liveness probe `initialDelaySeconds` to give the app time to start.

---

## ImagePullBackOff / ErrImagePull

**Root Cause**: Kubernetes can't pull the container image. Causes:
- Image doesn't exist or tag is wrong
- Private registry without credentials
- Network issues preventing access to the registry

**Fix**:
1. Verify the image exists: `docker pull <image>` locally.
2. For private registries, create an `imagePullSecret`:
```bash
kubectl create secret docker-registry regcred \
  --docker-server=ghcr.io \
  --docker-username=<user> \
  --docker-password=<token>
```
3. Reference it in the Pod spec:
```yaml
imagePullSecrets:
  - name: regcred
```
4. Check that the image tag matches what was pushed — typos are the #1 cause.

---

## OOMKilled (exit code 137)

**Root Cause**: The container exceeded its memory limit and was killed by the kernel's OOM killer.

**Fix**:
1. Increase the memory limit in the deployment:
```yaml
resources:
  limits:
    memory: "1Gi"
  requests:
    memory: "512Mi"
```
2. Profile the application's memory usage and fix leaks.
3. For Java: set `-Xmx` to ~75% of the container memory limit.
4. For Node.js: set `--max-old-space-size` accordingly.
5. Always set both `requests` and `limits` — without limits, a single pod can starve the node.

---

## Pod stuck in Pending state

**Root Cause**: Kubernetes can't schedule the pod onto any node. Causes:
- Insufficient CPU/memory resources on all nodes
- Node selector or affinity rules can't be satisfied
- PersistentVolumeClaim not bound
- Taints on nodes without matching tolerations

**Fix**:
1. Check why: `kubectl describe pod <pod-name>` → look at the Events section.
2. Check node resources: `kubectl describe nodes | grep -A 5 "Allocated resources"`.
3. For PVC issues: `kubectl get pvc` — ensure the PVC is `Bound`.
4. For taint issues: add tolerations or remove the taint.
5. Scale up the cluster if resources are genuinely exhausted.

---

## Service not reachable / DNS resolution failure

**Root Cause**: Pods can't reach other services via their DNS names. Causes:
- Service name typo
- Service and pod in different namespaces (need `service.namespace.svc.cluster.local`)
- CoreDNS not running or misconfigured
- Network policy blocking traffic

**Fix**:
1. Verify the service exists: `kubectl get svc -A | grep <name>`.
2. Use the full DNS: `<service>.<namespace>.svc.cluster.local`.
3. Test DNS from inside a pod: `kubectl exec -it <pod> -- nslookup <service>`.
4. Check CoreDNS: `kubectl get pods -n kube-system | grep coredns`.
5. Check NetworkPolicies: `kubectl get networkpolicies -A`.

---

## Liveness/Readiness probe failures

**Root Cause**: Kubernetes kills or stops routing traffic to pods whose probes fail. Common when:
- App takes longer to start than `initialDelaySeconds`
- Probe endpoint returns non-200 status
- Probe timeout is too short for slow responses

**Fix**:
1. Increase the startup grace period:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10
  failureThreshold: 5
```
2. Use a separate `startupProbe` for slow-starting apps (K8s 1.18+):
```yaml
startupProbe:
  httpGet:
    path: /health
    port: 8080
  failureThreshold: 30
  periodSeconds: 10
```
3. Ensure the health endpoint doesn't depend on external services (database, cache) — it should check if the app process is alive, not if all dependencies are up.

---

## ConfigMap / Secret not mounted or empty

**Root Cause**: The ConfigMap or Secret referenced in the Pod spec doesn't exist, or the volume mount path is incorrect.

**Fix**:
1. Verify it exists: `kubectl get configmap <name>` or `kubectl get secret <name>`.
2. Ensure the names match exactly (case-sensitive).
3. Check the mount path doesn't conflict with existing directories in the image.
4. For env vars from ConfigMaps, use:
```yaml
envFrom:
  - configMapRef:
      name: app-config
```
5. For file mounts, use `subPath` if mounting a single file:
```yaml
volumeMounts:
  - name: config-volume
    mountPath: /app/config.yaml
    subPath: config.yaml
```
