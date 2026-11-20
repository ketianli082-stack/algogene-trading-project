"""Immutable GitHub checkpoint for EXP-021-DIAGNOSTIC; only redacted local JSON is uploaded."""
import base64
import json
import os
from pathlib import Path
import re
import urllib.request

REPO = "ketianli082-stack/algogene-trading-project"
BRANCH = "research/four-asset-basis-2023-2025"


def archive(source, name):
    if os.environ.get("GITHUB_REPOSITORY") != REPO or \
            os.environ.get("GITHUB_REF_NAME") != BRANCH:
        raise ValueError("Unexpected repository branch; refusing archive")
    run = os.environ["GITHUB_RUN_ID"]
    attempt = os.environ["GITHUB_RUN_ATTEMPT"]
    if not run.isdigit() or not attempt.isdigit() or \
            not re.fullmatch(r"[a-z0-9-]+", name):
        raise ValueError("Unexpected immutable artifact name")
    path = "experiments/EXP-021-DIAGNOSTIC/runs/%s-attempt-%s-%s.json" % (run, attempt, name)
    payload = {"message": "exp021_diagnostic: checkpoint " + name, "branch": BRANCH,
               "content": base64.b64encode(Path(source).read_bytes()).decode()}
    headers = {"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
               "Accept": "application/vnd.github+json",
               "Content-Type": "application/json",
               "X-GitHub-Api-Version": "2022-11-28"}
    req = urllib.request.Request("https://api.github.com/repos/" + REPO +
                                 "/contents/" + path,
                                 data=json.dumps(payload).encode(),
                                 headers=headers, method="PUT")
    with urllib.request.urlopen(req, timeout=45) as response:
        data = json.load(response)
    print("SAVED", data["content"]["html_url"], flush=True)


if __name__ == "__main__":
    archive("outputs/exp021_diagnostic/platform-responses.json", "final")
