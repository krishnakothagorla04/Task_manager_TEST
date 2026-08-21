# Release Management Plan (RMP) — Task Manager

## 1. Introduction
This document presents the Release Management Plan for a microservices-based Task Manager application, designed and deployed following enterprise DevOps best practices. The system demonstrates Infrastructure as Code, fully automated CI/CD, and cloud-native deployment strategies.

## 2. System Architecture

### 2.1 Microservices Overview
The application is decomposed into two independently deployable services:

- **user-service:** Manages user accounts (CRUD). Exposes a REST API consumed by the task-service for user validation.
- **task-service:** Manages tasks (CRUD). Before creating a task, it validates the assigned user by making an HTTP request to the user-service — demonstrating true inter-service communication.
- **MongoDB:** A single database instance with separate collections (`users`, `tasks`).

### 2.2 Architecture Diagram
*(Insert the architecture diagram from the README or create a visual in your presentation)*

### 2.3 Justification of Architecture Decisions

| Decision | Justification |
|----------|---------------|
| **Microservices over Monolith** | Each service can be developed, deployed, and scaled independently. If user-service fails, task-service remains partially available (graceful degradation). |
| **Node.js (Express)** | Lightweight, non-blocking I/O model ideal for REST microservices. Large ecosystem and fast development cycle. |
| **MongoDB** | Schema-flexible NoSQL database suited for rapid prototyping and JSON-native data. Aligns naturally with Node.js. |
| **REST for inter-service communication** | Simple, stateless, and widely understood protocol. Sufficient for synchronous validation calls between services. |

## 3. CI/CD Pipeline 

### 3.1 Pipeline Overview
The CI/CD pipeline is implemented using **GitHub Actions** and is triggered automatically on every `git push` to the `main` branch. No manual intervention is required at any stage.

### 3.2 Pipeline Stages

| Stage | Action | Tool |
|-------|--------|------|
| 1. Build & Test | Install dependencies, run tests, audit dependencies | Node.js, npm, npm audit |
| 2. Code Quality | Static analysis and quality gate enforcement | SonarCloud |
| 3. Docker Build | Build container images for both services | Docker |
| 4. Security Scan | Scan images for known CVEs | Trivy |
| 5. Push | Push images to Docker Hub registry | Docker Hub |
| 6. Deploy | Provision infrastructure via IaC | Terraform (KinD cluster) |
| 7. Verify | Confirm rollout success for all services | kubectl rollout status |

### 3.3 Justification

| Decision | Justification |
|----------|---------------|
| **GitHub Actions** | Tightly integrated with the Git repository. Free tier sufficient for this project. YAML-based declarative pipelines are reproducible and version-controlled. |
| **Docker Hub** | Industry-standard public registry. Simplifies image distribution for Kubernetes. |
| **Trivy** | Open-source, fast vulnerability scanner. Integrates seamlessly into CI/CD without additional infrastructure. |
| **SonarCloud** | Provides automated code quality analysis, code smell detection, and a formal Quality Gate. Free for open-source projects. |
| **npm audit** | Built-in Node.js dependency vulnerability scanner. Catches known CVEs in third-party packages before they reach production. |

## 4. Infrastructure as Code (Terraform)

### 4.1 What Terraform Manages
Terraform provisions all Kubernetes resources declaratively:
- Namespace, Deployments, Services, PVCs, and HPA

### 4.2 Reproducibility
The system can be:
- **Created:** `terraform apply`
- **Destroyed:** `terraform destroy`
- **Re-created:** `terraform apply` again

This satisfies the requirement for fully automated, reproducible infrastructure provisioning.

### 4.3 Justification

| Decision | Justification |
|----------|---------------|
| **Terraform over manual kubectl** | Declarative state management. Terraform tracks what exists and only applies differences. The entire infrastructure is version-controlled. |
| **Kubernetes provider** | Allows managing K8s resources directly without shell scripts, ensuring idempotency. |

## 5. Deployment Strategy

### 5.1 Rolling Updates
Both services use a **RollingUpdate** strategy configured in their Kubernetes Deployments:
- `maxUnavailable: 1` — At most one pod is taken down at a time
- `maxSurge: 1` — At most one extra pod is created during the update

**Result:** Users experience zero downtime during deployments.

### 5.2 Rollback Strategy
Kubernetes maintains previous ReplicaSets. If a deployment fails:
```bash
kubectl rollout undo deployment/task-service -n taskmanager
```
This instantly reverts to the last known-good state.

## 6. Change Management

### 6.1 How Updates Are Deployed
```
Developer makes code change
        ↓
Git push to main branch
        ↓
GitHub Actions pipeline triggers automatically
        ↓
Build → Test → Docker Build → Security Scan → Push → Deploy
        ↓
Kubernetes performs rolling update
        ↓
New version is live (zero downtime)
```

**Key Point:** There are zero manual steps between code change and live deployment. The pipeline is fully automated and reproducible.

## 7. Scaling Strategy

### 7.1 Horizontal Pod Autoscaler (HPA)
The task-service is configured with an HPA:
- **Min replicas:** 2
- **Max replicas:** 5
- **Trigger:** CPU utilization exceeds 70%

### 7.2 Justification
Auto-scaling ensures the system can handle traffic spikes without manual intervention, and scales back down to save resources during low-traffic periods.

## 8. Backup & Recovery Strategy

### 8.1 Backup Plan
- **Tool:** `mongodump` — creates binary exports of the MongoDB database
- **Automation:** A Kubernetes `CronJob` (`mongodb-backup`) runs `mongodump` daily at midnight (schedule: `0 0 * * *`)
- **Storage:** Backups are written to a dedicated PersistentVolumeClaim (`mongo-backup-pvc`, 1Gi) mounted at `/backups`
- **Retention:** The CronJob retains the last 3 successful backups and 1 failed job for debugging
- **IaC:** The CronJob and its PVC are fully managed by Terraform, ensuring they are provisioned automatically alongside all other infrastructure

### 8.2 Recovery Plan
- **Tool:** `mongorestore` — restores from a `mongodump` backup
- **Process:**
  1. Identify the most recent backup: `kubectl exec -it <backup-pod> -n taskmanager -- ls /backups/`
  2. Scale down task-service and user-service: `kubectl scale deployment task-service user-service --replicas=0 -n taskmanager`
  3. Run `mongorestore` against the MongoDB instance: `mongorestore --host mongodb.taskmanager.svc.cluster.local:27017 --db taskmanager /backups/backup-YYYYMMDD-HHMMSS/taskmanager`
  4. Scale services back up: `kubectl scale deployment task-service --replicas=2 user-service --replicas=2 -n taskmanager`
  5. Verify data integrity by checking task and user counts through the API

### 8.3 Kubernetes-Level Recovery
- MongoDB uses a PersistentVolumeClaim (PVC), ensuring data survives pod restarts
- Container images are stored in Docker Hub, so any service can be redeployed from scratch
- All infrastructure is codified in Terraform; a full cluster rebuild is a single `terraform apply` command

## 9. Security

### 9.1 Container Security
- **Trivy scanning** in CI/CD catches known CVEs before images are deployed
- **npm audit** checks all Node.js dependencies for known vulnerabilities during the Build & Test stage
- **SonarCloud** performs static code analysis and enforces a Quality Gate for code smells, bugs, and security hotspots
- **Alpine-based images** minimize attack surface by reducing the number of installed packages

### 9.2 Network Security — Kubernetes Network Policies
Three `NetworkPolicy` resources are deployed via Terraform to enforce pod-to-pod traffic isolation:

| Policy | Target | Allowed Ingress |
|--------|--------|-----------------|
| `mongodb-allow-services-only` | MongoDB pods | Only from `user-service` and `task-service` pods on port 27017 |
| `task-service-policy` | Task-service pods | Any source on port 3001 |
| `user-service-policy` | User-service pods | Any source on port 3000 |

**Effect:** MongoDB is completely isolated from external access. Only the two application services can reach the database. This follows the principle of least privilege at the network layer.

### 9.3 Application Security
- Services communicate internally via Kubernetes ClusterIP (not exposed externally)
- Only task-service is exposed via NodePort for demo purposes
- Passwords are not returned in API responses (user-service strips the password field)

## 10. Monitoring & Logging

### 10.1 Current Implementation
- **Application logging:** Morgan HTTP logger in both services (combined format for production-grade access logs)
- **Kubernetes logs:** `kubectl logs deployment/task-service -n taskmanager`
- **Health checks:** `/health` endpoints used by Kubernetes readiness and liveness probes on all three deployments (user-service, task-service, and MongoDB)
- **HPA Metrics:** The Horizontal Pod Autoscaler monitors real-time CPU utilization via the Kubernetes Metrics Server

### 10.2 Monitoring Setup Guide (Prometheus + Grafana)
For full observability in a production environment, deploy the Prometheus monitoring stack:
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring
```
Access Grafana at `http://localhost:3000` (default credentials: admin/prom-operator). Import the Kubernetes cluster dashboard (ID: 6417) for pod-level CPU, memory, and network metrics.

### 10.3 Load Testing (HPA Validation)
To validate the auto-scaling configuration, a `k6` load test script is included:
```bash
kubectl port-forward svc/task-service 3001:3001 -n taskmanager
k6 run load-test.js
```
Monitor the HPA in real-time during the test:
```bash
kubectl get hpa -n taskmanager --watch
```
Expected behaviour: task-service scales from 2 to 5 replicas when CPU exceeds 70%, and scales back down after the load subsides.

### 10.4 Future Improvements
- Prometheus + Grafana for persistent metrics dashboards
- ELK/EFK stack for centralized log aggregation
- Jaeger or OpenTelemetry for distributed tracing across microservices

## 11. Evaluation

### 11.1 Performance
- Lightweight Node.js services start in under 2 seconds
- Health probes ensure traffic only routes to ready pods

### 11.2 Cost
- Minikube: Free for local development
- Cloud: Minimal cost (2 small pods + 1 DB = ~$20/month on DigitalOcean)

### 11.3 Scalability
- HPA enables automatic horizontal scaling
- Microservice architecture allows independent scaling of each service

### 11.4 Ease of Use
- `docker-compose up` for local dev
- `terraform apply` for full deployment
- One git push triggers entire pipeline

### 11.5 Trade-offs
| Advantage | Limitation |
|-----------|-----------|
| Zero-downtime deployments | Adds complexity vs. simple server deployment |
| Full automation | Requires initial setup of secrets and cluster |
| Reproducible infrastructure | Learning curve for Terraform + K8s |

## 12. Future Improvements

While the current system meets all enterprise requirements, the following enhancements would further strengthen the architecture for a large-scale production deployment:

| Improvement | Description |
|-------------|-------------|
| **Service Mesh (Istio)** | Would provide mutual TLS between services, advanced traffic routing (canary deployments, traffic splitting), and built-in observability without modifying application code. |
| **Secret Management (HashiCorp Vault)** | Currently, secrets are stored in GitHub repository secrets. Vault would provide dynamic secret generation, automatic rotation, and fine-grained access control for database credentials and API keys. |
| **GitOps (ArgoCD/Flux)** | Would replace the push-based CI/CD model with a pull-based approach, continuously reconciling cluster state with the Git repository. |
| **Centralised Logging (EFK Stack)** | Elasticsearch, Fluentd, and Kibana would aggregate logs from all services into a searchable dashboard, replacing per-pod log inspection. |
| **Database Replication** | A MongoDB ReplicaSet with 3 members would provide high availability and automatic failover for the data layer. |
| **Container Registry (Private)** | Migrating from Docker Hub to a private registry (e.g., AWS ECR, GitHub Container Registry) would improve security by preventing public image exposure. |
