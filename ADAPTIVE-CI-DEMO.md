# Adaptive CI/CD - Demo Guide (Task Manager TEST repo)

This repo now has an **adaptive CI/CD pipeline** (`.github/workflows/adaptive-ci.yml`)
on top of the existing Node.js microservices. It predicts each commit's risk
BEFORE building and routes it to a lighter or heavier lane, so low-risk changes
skip the expensive Docker build + scan stages and finish much faster.

## The lanes

| Lane | Trigger | Runs | Relative time |
|------|---------|------|---------------|
| Fast | docs / tiny change | npm install + tests | fastest (skips Docker build & scan) |
| Standard | normal code change | tests + dependency audit | medium |
| Extended | security-sensitive / large change | tests + blocking audit + Docker build + Trivy scan + approval gate | slowest (full validation) |

The saving is real: a documentation change avoids building and scanning Docker
images for two services, saving minutes of pipeline time.

## Before the demo
1. In `.github/workflows/`, temporarily rename `deploy.yml` to `deploy.yml.disabled`
   (or comment its `on:` triggers) so only the adaptive pipeline runs and the
   time difference is clear. Restore it afterwards.
2. Settings -> Actions -> General -> enable **Read and write permissions**.
3. (Optional) create a `production` environment with a required reviewer for the
   high-risk approval gate.

## The three-commit demo (run each, watch the Actions tab)

### 1. LOW -> Fast lane (the time-saving moment)
```bash
echo "Updated documentation." >> README.md
git commit -am "docs: update README"
git push
```
"Docs change -> low risk -> fast lane. Only install + tests run; the pipeline
skips building and scanning the Docker images. Finishes in a fraction of the time."

### 2. MEDIUM -> Standard lane
```bash
cat >> task-service/index.js <<'JS'

// simple in-memory task statistics helper
function taskStats(list) {
  const total = list.length;
  const done = list.filter(t => t.done).length;
  const open = total - done;
  return { total, done, open };
}
module.exports.taskStats = taskStats;
JS
git commit -am "feat: add task statistics helper"
git push
```
"A normal feature -> standard lane: tests plus a dependency audit. Balanced."

### 3. HIGH -> Extended lane (the safety moment)
```bash
cat >> user-service/index.js <<'JS'

// security-sensitive: password validation
function checkPassword(pw) {
  return pw === process.env.ADMIN_PW;
}
module.exports.checkPassword = checkPassword;
JS
git commit -am "feat: add password validation"
git push
```
"This touches password handling -> high risk -> extended lane: full tests, a
BLOCKING dependency audit, Docker build, and a Trivy vulnerability scan, plus a
manual approval gate. Risky changes get MORE checks, not fewer."

## Then show
- The run Summary -> the risk report card and the "finished in Ns / skipped..." lines.
- `logs/outcomes.csv` growing -> the closed learning loop.
- `dashboard.html` -> compute saved and lane distribution.

## One-line message
"The pipeline spends effort where the risk is - fast for safe changes, thorough
for risky ones - cutting overall CI time while strengthening safety on what matters."
