#!/usr/bin/env python3
"""
Adaptive CI/CD - pre-build risk predictor (runs inside GitHub Actions).

Decision policy is HYBRID:
  * Clearly trivial changes (docs-only, tiny) -> LOW  (fast lane)
  * Clearly risky changes (large, many files, security-sensitive) -> HIGH (extended)
  * Otherwise -> the calibrated ML model's score decides (defaults to MED)

If model.joblib is present it is used for the middle band; if not, the rule-based
policy alone is used so the demo always runs. Outputs lane/risk/score to
$GITHUB_OUTPUT and a report card to the run summary.
"""
import os, subprocess, json, random, datetime
import numpy as np

LOW_MAX, HIGH_MIN = 0.10, 0.20
EXPLORE_RATE = 0.15
DOC_EXT = {".md", ".rst", ".txt"}
SRC_EXT = {".py", ".js", ".ts", ".go", ".java", ".yml", ".yaml"}
RISKY_HINTS = ("auth", "security", "secret", "password", "payment", "subprocess", "eval")


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def get_diff():
    parent = sh(["git", "rev-parse", "HEAD~1"])
    base = parent if parent else sh(["git", "hash-object", "-t", "tree", "/dev/null"])
    out = sh(["git", "diff", "--numstat", base, "HEAD"])
    files = []
    for line in out.splitlines():
        p = line.split("\t")
        if len(p) == 3:
            files.append((p[2], int(p[0]) if p[0].isdigit() else 0,
                          int(p[1]) if p[1].isdigit() else 0))
    return files


def classify(path):
    ext = os.path.splitext(path)[1].lower(); low = path.lower()
    if "test" in low or "spec" in low: return "test"
    if ext in DOC_EXT or low.startswith("docs/"): return "doc"
    if ext in SRC_EXT: return "src"
    return "other"


def added_lines():
    """Return the text of lines ADDED in this commit (for content-based risk rules)."""
    parent = sh(["git", "rev-parse", "HEAD~1"])
    base = parent if parent else sh(["git", "hash-object", "-t", "tree", "/dev/null"])
    diff = sh(["git", "diff", base, "HEAD"])
    return "\n".join(l[1:] for l in diff.splitlines()
                     if l.startswith("+") and not l.startswith("+++")).lower()


def features():
    files = get_diff()
    src_churn = test_churn = 0; src_files = doc_files = 0
    add = dele = mod = 0; risky = False
    content = added_lines()
    for path, a, d in files:
        k = classify(path); ch = a + d
        if k == "test": test_churn += ch
        elif k == "src": src_churn += ch; src_files += 1
        elif k == "doc": doc_files += 1
        # risky if the file PATH or the ADDED CODE mentions a sensitive keyword
        if any(h in path.lower() for h in RISKY_HINTS): risky = True
        if d == 0 and a > 0: add += 1
        elif a == 0 and d > 0: dele += 1
        else: mod += 1
    if any(h in content for h in RISKY_HINTS): risky = True
    total_files = len(files); total_churn = src_churn + test_churn
    is_docs_only = int(src_files == 0 and doc_files > 0 and total_files > 0)
    return dict(total_files=total_files, total_churn=total_churn, src_churn=src_churn,
                test_churn=test_churn, src_files=src_files, doc_files=doc_files,
                is_docs_only=is_docs_only, risky=risky,
                files_add=add, files_del=dele, files_mod=mod)


def model_score(f):
    """Use model.joblib if available; else return None."""
    try:
        import joblib, pandas as pd
        b = joblib.load("model.joblib"); model, feats = b["model"], b["features"]
        # map what we can; the rest imputed by the model pipeline
        known = {"src_churn": f["src_churn"], "test_churn": f["test_churn"],
                 "total_churn": f["total_churn"], "files_add": f["files_add"],
                 "files_del": f["files_del"], "files_mod": f["files_mod"],
                 "total_files": f["total_files"], "src_files": f["src_files"],
                 "doc_files": f["doc_files"], "is_docs_only": f["is_docs_only"], "is_pr": 0}
        row = {c: known.get(c, np.nan) for c in feats}
        return float(model.predict_proba(pd.DataFrame([row])[feats])[:, 1][0])
    except Exception:
        return None


def decide(f):
    reasons = []
    # rule 1 (highest priority): clearly risky -> HIGH  (checked FIRST so a small
    # but security-sensitive change is never mislabelled as low risk)
    if f["risky"]:
        reasons.append("touches a security-sensitive area (auth/password/etc.)")
        return "HIGH", 0.85, reasons
    if f["total_files"] >= 8 or f["total_churn"] >= 300:
        reasons.append(f"large change ({f['total_files']} files, {f['total_churn']} lines)")
        return "HIGH", 0.75, reasons
    # rule 2: clearly trivial -> LOW
    if f["is_docs_only"] or (f["total_files"] <= 1 and f["total_churn"] <= 4):
        reasons.append("small / documentation change - low risk")
        return "LOW", 0.05, reasons
    # rule 3: otherwise -> model score (or default MED)
    p = model_score(f)
    if p is None:
        reasons.append("moderate code change - standard validation")
        return "MED", 0.15, reasons
    reasons.append(f"model risk score {p:.2f}")
    lane = "LOW" if p < LOW_MAX else ("HIGH" if p >= HIGH_MIN else "MED")
    return lane, p, reasons


def meter(p, w=20):
    fill = int(round(p * w)); return "`[" + "#"*fill + "-"*(w-fill) + f"]` **{p*100:.0f}%**"


def summary(p, risk, lane, reasons, f):
    action = {"LOW": "**Fast lane** - npm install + tests only (skips Docker build, scan, deploy)",
              "MED": "**Standard lane** - tests + dependency audit",
              "HIGH": "**Extended lane** - tests + blocking audit + Docker build + Trivy scan + approval gate"}[lane]
    rr = "\n".join(f"- {x}" for x in reasons)
    return f"""## Pre-Build Risk Prediction

| | |
|---|---|
| **Risk level** | **{risk}** |
| **Risk score** | {meter(p)} |
| **Pipeline lane** | `{lane}` |
| **Files changed** | {f['total_files']} |
| **Code churn** | {f['total_churn']} lines |

### Selected pipeline
{action}

### Why this prediction
{rr}

<sub>Predicted before any test stage ran. The fast lane skips the slow e2e suite,
which is where most of the pipeline time is spent.</sub>
"""


def main():
    f = features()
    predicted_lane, p, reasons = decide(f)
    explored = int(predicted_lane == "LOW" and random.random() < EXPLORE_RATE)
    lane = "MED" if explored else predicted_lane
    if explored: reasons.append("selected for exploration (full run to verify a low-risk prediction)")
    risk = {"LOW": "Low", "MED": "Medium", "HIGH": "High"}[lane]

    print("="*52)
    print(f"  RISK: {risk} | LANE: {lane} | score {p:.2f}")
    print("  " + "; ".join(reasons)); print("="*52)

    md = summary(p, risk, lane, reasons, f)
    ss = os.environ.get("GITHUB_STEP_SUMMARY")
    if ss: open(ss, "a").write(md)
    open("risk_summary.md", "w").write(md)

    rec = {"timestamp": datetime.datetime.utcnow().isoformat(),
           "commit": os.environ.get("GITHUB_SHA", sh(["git", "rev-parse", "HEAD"])),
           "score": round(p, 4), "predicted_lane": predicted_lane, "lane_run": lane,
           "explored": explored, "total_files": f["total_files"], "total_churn": f["total_churn"]}
    open("prediction.json", "w").write(json.dumps(rec))

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        open(out, "a").write(f"lane={lane}\nrisk={risk}\nscore={p:.2f}\nexplored={explored}\n")


if __name__ == "__main__":
    main()
