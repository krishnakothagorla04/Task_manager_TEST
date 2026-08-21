# Adaptive CI/CD - integrated into deploy.yml

The pipeline (`.github/workflows/deploy.yml`) is now risk-aware. A prediction
stage runs first and decides how much of the pipeline to execute:

| Predicted risk | Stages that run |
|----------------|-----------------|
| LOW (docs / tiny change) | Build & Test only |
| MEDIUM (normal code change) | Build & Test + SonarCloud + Docker build/scan/push |
| HIGH (security-sensitive / large change) | All of the above + full k8s/Terraform deploy + manual approval gate |

Low-risk commits skip the expensive SonarCloud, Docker and deployment stages,
saving several minutes of pipeline time. High-risk commits get the full pipeline
plus a human approval gate.

## Demo commits (run each, watch the Actions graph collapse/expand)

LOW - only Build & Test runs:
    echo "Updated docs." >> README.md
    git commit -am "docs: update README" && git push

MEDIUM - adds SonarCloud + Docker:
    (add a multi-line helper function to task-service/index.js)
    git commit -am "feat: add task stats helper" && git push

HIGH - adds the full deployment + approval gate:
    (add a checkPassword function to user-service/index.js)
    git commit -am "feat: add password validation" && git push

## Setup
- Enable Settings -> Actions -> General -> Read and write permissions.
- Add secrets DOCKERHUB_USERNAME/DOCKERHUB_TOKEN/SONAR_TOKEN (only needed for the
  Medium/High stages; the LOW demo runs without them).
- (Optional) create a `production` environment with a required reviewer for the
  HIGH-risk approval gate.
