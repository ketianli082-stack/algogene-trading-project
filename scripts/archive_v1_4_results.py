"""Immutable, redacted research checkpoints and final bundle on the existing branch."""
import base64
import argparse
import json
import os
from pathlib import Path
import re
import urllib.request


def archive(source, name="bundle", experiment="EXP-009"):
    source = Path(source)
    if not source.is_file():
        print("No result bundle available; inspect workflow logs")
        return
    repository, branch = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_REF_NAME"]
    if experiment not in ("EXP-009", "EXP-010", "EXP-011", "EXP-012", "EXP-013"):
        raise ValueError("Unexpected experiment destination")
    if repository != "ketianli082-stack/algogene-trading-project" or branch != "codex/algogene-crypto-v1.0":
        raise ValueError("Unexpected archive destination")
    run_id, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    if not run_id.isdigit() or not attempt.isdigit() or not re.fullmatch(r"[a-z0-9.-]+", name):
        raise ValueError("Unexpected archive identifier")
    path = "experiments/" + experiment + "/runs/%s-attempt-%s-%s.json" % (run_id, attempt, name)
    payload = {"message": "results: " + experiment + " " + name + " run " + run_id,
               "branch": branch, "content": base64.b64encode(source.read_bytes()).decode("ascii")}
    headers = {"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
               "Accept": "application/vnd.github+json", "Content-Type": "application/json",
               "X-GitHub-Api-Version": "2022-11-28"}
    request = urllib.request.Request("https://api.github.com/repos/" + repository + "/contents/" + path,
                                     data=json.dumps(payload).encode(), headers=headers, method="PUT")
    # No sha: a prior run/attempt checkpoint can never be overwritten.
    with urllib.request.urlopen(request, timeout=45) as response:
        created = json.load(response)
    print("Saved " + created["content"]["html_url"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="outputs/v1_4/platform-responses.json")
    parser.add_argument("--experiment", default="EXP-009", choices=("EXP-009", "EXP-010", "EXP-011", "EXP-012", "EXP-013"))
    args = parser.parse_args()
    archive(args.source, experiment=args.experiment)
