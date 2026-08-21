#!/usr/bin/env python3
"""Close the loop: pair prediction with real outcome -> logs/outcomes.csv."""
import os, csv, json, datetime
LOG = "logs/outcomes.csv"
rec = json.load(open("prediction.json"))
outcome = (os.environ.get("OUTCOME", "unobserved").strip() or "unobserved")
if rec.get("lane_run") == "LOW" and not rec.get("explored"):
    outcome = "unobserved"
row = {"logged_at": datetime.datetime.utcnow().isoformat(), "commit": rec.get("commit"),
       "score": rec.get("score"), "predicted_lane": rec.get("predicted_lane"),
       "lane_run": rec.get("lane_run"), "explored": rec.get("explored"),
       "outcome": outcome, "total_files": rec.get("total_files"),
       "total_churn": rec.get("total_churn")}
os.makedirs("logs", exist_ok=True)
new = not os.path.exists(LOG)
with open(LOG, "a", newline="") as fp:
    w = csv.DictWriter(fp, fieldnames=list(row.keys()))
    if new: w.writeheader()
    w.writerow(row)
print("Logged:", row["lane_run"], row["outcome"])
