# Enterprise DevOps & Microservices Task Manager
**Continuous Assessment 2 (CA2) Final Project**

---

## 1. Project Overview & Objective
This project is an enterprise-grade, DevOps-centric **Task Manager Application**. The core objective of this project is not just to build an application, but to orchestrate, automate, and secure its entire lifecycle. 

The system leverages a **Microservices Architecture** entirely provisioned via **Infrastructure as Code (Terraform)**, deployed to **Kubernetes**, and strictly automated through a **GitHub Actions CI/CD Pipeline**. It satisfies advanced enterprise requirements including Zero-Downtime deployments, DevSecOps vulnerability scanning, Local Storage Persistence, and mathematically driven Auto-Scaling.

---

## 2. The Application Architecture (Microservices)
Instead of a traditional monolithic backend, the application logic is separated into decoupled services that communicate synchronously over the network.

### 2.1 The Services
* **User-Service (Node.js/Express):** Handles user registration, secure authentication, and session generation.
* **Task-Service (Node.js/Express):** Handles the creation, status updating, and deletion of tasks.
* **MongoDB (Database):** A centralized NoSQL database utilized dynamically by both services via Mongoose to maintain dedicated collections (`users` and `tasks`).
* **Frontend SPA:** A single-page HTML/JS application (Vanilla JS) that handles Authentication (Sign Up/Sign In), Session Persistence (via `localStorage`), and strict **Data Isolation** (users can only view and manage tasks belonging directly to their secure Session ID).

### 2.2 Proof of Inter-Service Communication
When a user attempts to create a task via the Task-Service, the Task-Service does not blindly insert it into the database. Instead, the Task-Service initiates a synchronous `HTTP GET` REST API request out across the Kubernetes network to the User-Service to cryptographically validate that the user exists. If the User-Service denies the existence of the user, the task creation halts.

---

## 3. Continuous Integration & Continuous Deployment (CI/CD)
The deployment is entirely disconnected from manual human interaction. Code pushed to the `main` branch on GitHub instantly triggers the full CI/CD Pipeline.

### 3.1 Unification via Matrix Strategy
Rather than maintaining split pipelines, the project uses a **Matrix Build Strategy** to uniformly loop over both microservices concurrently, ensuring both services receive identical testing and security enforcement.

### 3.2 Pipeline Flow
1. **Build & Test:** Provisions Node.js, installs dependencies, runs unit tests, and executes `npm audit` to detect known vulnerabilities in third-party packages.
2. **Code Quality (SonarCloud):** Runs static code analysis through SonarCloud to enforce a Quality Gate covering code smells, bugs, and security hotspots.
3. **Dockerization:** Builds lightweight, multi-stage `node:18-alpine` containers.
4. **DevSecOps (Trivy):** An AquaSecurity Trivy scan halts the pipeline if `CRITICAL` or `HIGH` vulnerabilities are detected inside the freshly built Docker image.
5. **Push:** Uploads the authorized images to Docker Hub safely.
6. **Infrastructure Orchestration:** Spins up a KinD Kubernetes cluster dynamically within the GitHub server, downloads the Terraform CLI, and automatically executes `terraform apply --auto-approve` to patch the live architectural state.

### 3.3 System Architecture
## Microservice Decomposition
Rather than a single tightly coupled artefact, the application is decomposed into three independently deployable runtime units, following Newman’s small-service guidance (Newman, 2021):
User-Service (Node.js / Express, port 3000): handles user registration, authentication and session lifecycle. Passwords are bcrypt-hashed before persistence; sensitive fields are stripped from API responses.
Task-Service (Node.js / Express, port 3001): manages task CRUD. Before inserting any task, it performs a synchronous HTTP call to User-Service to validate the assignee, demonstrating true inter-service communication.
MongoDB 6 (port 27017): NoSQL data layer with separate collections for users and tasks, accessed via the Mongoose ODM and locked down by Kubernetes NetworkPolicy.
Frontend SPA (Vanilla JS / HTML): served statically, authenticates against User-Service and displays tasks scoped strictly to the authenticated session.

## Architectural Decisions
Decision
Justification
Microservices over monolith
Each service scales, deploys and fails independently, providing graceful degradation and team autonomy (Newman, 2021).
Node.js / Express
Non-blocking event loop is optimal for I/O-bound REST microservices (Node.js Foundation, 2023).
MongoDB
Schema-flexible JSON-native document store that aligns naturally with JavaScript-centric services (MongoDB, 2023).
REST for inter-service calls
Stateless and widely understood; sufficient for synchronous validation between two small services.
Vanilla JS frontend
Zero framework overhead; straightforward session management via localStorage.


## Docker Compose - Local Development
A docker-compose.yml at the repository root orchestrates all four services on a shared bridge network for local development. The task-service receives USER_SERVICE_URL as an environment variable, illustrating twelve-factor environment-driven configuration (Wiggins, 2017). MongoDB data is persisted via a named volume so that local state survives container restarts.

## Running Application
The screenshots below show the live frontend once the full stack is running. Sign-in authenticates against User-Service; tasks on the dashboard are then scoped to that session, demonstrating the path Frontend to User-Service to Task-Service to MongoDB.


---

## 4. Infrastructure as Code (Terraform) & Kubernetes
All cloud infrastructure is declared mathematically inside `terraform/main.tf` to achieve **Idempotency** (the ability to confidently destroy and perfectly reconstruct the cluster on demand).

### 4.1 Deployment Strategy (Rolling Update)
The Terraform scripts explicitly dictate a **RollingUpdate** strategy with `maxUnavailable: 1` and `maxSurge: 1`. 
* **Justification:** If an update is pushed, Kubernetes replaces the pods one-by-one, guaranteeing absolute **Zero-Downtime**. If a catastrophic bug is detected, Kubernetes supports instant rollbacks via `kubectl rollout undo` to revert to previous ReplicaSets.

### 4.2 Persistent Storage
By default, containers are stateless. The project utilizes a `kubernetes_persistent_volume_claim` (PVC) attached directly to the MongoDB cluster. 
* **Justification:** If the database pod suffers a fatal crash, the actual data is preserved safely on a protected volume and seamlessly re-attached to the replacement pod upon reboot.

### 4.3 Network Security (Network Policies)
Three Kubernetes `NetworkPolicy` resources are deployed via Terraform to enforce pod-to-pod traffic isolation. MongoDB is completely locked down: only `user-service` and `task-service` pods can communicate with it on port 27017. This implements the principle of least privilege at the network layer.

### 4.4 Automated Release Orchestration & Configuration Management
A core requirement of this RMP is to fully automate provisioning and release orchestration so that no step of a release depends on manual intervention. The stack achieves this end-to-end: GitHub Actions drives every pipeline stage (build, test, scan, push, deploy), Terraform declaratively provisions every Kubernetes resource (Deployments, Services, PVCs, HPA, NetworkPolicies and the backup CronJob), and kubectl rollout status gates the deployment before the pipeline is marked green. Because the cluster is reconstructed from source on every run, its live state cannot drift away from what is in Git — eliminating the configuration drift that plagues pipelines still dependent on hand-edited YAML or console clicks. Continued configuration management is enforced by Terraform's idempotency: re-running terraform apply converges the live cluster back to its declared state, silently correcting any ad-hoc modifications. Together, these controls realise the full promise of Continuous Delivery: every commit on main is a releasable, reproducible, drift-free unit of infrastructure and application change.

## 5. Extra DevOps Features Implemented
To ensure enterprise-level compliance, the following additional features were explicitly engineered into the core infrastructure:

1. **Security Vulnerability Scanning:** Integrated directly as a blocking phase in the CI/CD pipeline using Trivy, with additional npm audit and SonarCloud quality gates.
2. **Mathematical Auto-Scaling:** A **Horizontal Pod Autoscaler (HPA)** was added to the Task-Service via Terraform. It actively monitors CPU utilization. If organic traffic spikes CPU usage past 70%, the cluster automatically clones the Task-Service from 2 replicas up to 5 replicas dynamically to handle the load, scaling back down when traffic subsides to save computational cost.
3. **Network Policies:** Kubernetes Network Policies restrict pod-to-pod communication, isolating MongoDB from any unauthorized access.
4. **Automated Backups:** A scheduled CronJob performs daily MongoDB backups to a persistent volume for disaster recovery.

---

## 6. How to Run & Verify Locally
For local development, testing, and live presentation styling, you do not need to run the full Kubernetes cluster. 

Ensure Docker Desktop is running, then use the multi-container configuration tool:
1. Open up a terminal directory containing the project.
2. Build and start the architecture in the background:
   ```bash
   docker-compose up -d --build
   ```
3. Open `frontend/index.html` in any web browser to simulate the client application.
4. When finished, safely tear down the containers:
   ```bash
   docker-compose down
   ```

---

## 7. Load Testing (HPA Validation)
A `k6` load test script is included to validate the Horizontal Pod Autoscaler configuration:
```bash
# Forward the task-service port from the cluster
kubectl port-forward svc/task-service 3001:3001 -n taskmanager

# Run the load test (ramps to 300 virtual users)
k6 run load-test.js

# Monitor HPA scaling in real-time (in a second terminal)
kubectl get hpa -n taskmanager --watch
```
Expected result: task-service scales from 2 to 5 replicas under sustained load and scales back down once the load subsides.

---

## 8. Monitoring (Prometheus + Grafana)
For full cluster observability, deploy the Prometheus monitoring stack:
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring
```
Access Grafana at `http://localhost:3000` (default credentials: `admin` / `prom-operator`). Import dashboard ID `6417` for pod-level CPU, memory, and network metrics.

---

## 9. Troubleshooting

### Docker Compose Issues
| Problem | Solution |
|---------|----------|
| `port already in use` | Stop any local MongoDB or Node processes using ports 3000, 3001, or 27017 (`netstat -ano \| findstr :3000`) |
| `mongodb connection refused` | Ensure Docker Desktop is running. Check container logs with `docker logs taskmanager-mongodb` |
| `user-service cannot connect` | Verify all services are on the same Docker network (`docker network ls`) |

### Kubernetes / KinD Issues
| Problem | Solution |
|---------|----------|
| Pods stuck in `Pending` state | Check PVC binding: `kubectl get pvc -n taskmanager`. Ensure the StorageClass provisioner is installed. |
| Terraform fails to apply | Ensure `~/.kube/config` is valid and the cluster is running: `kubectl cluster-info` |
| HPA shows `<unknown>` CPU | Install the Metrics Server: `kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml` |
| ImagePullBackOff | Verify Docker Hub credentials and that images have been pushed: `docker pull <username>/task-service:latest` |
