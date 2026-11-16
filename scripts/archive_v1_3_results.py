"""Archive only this run's redacted platform evidence on its existing branch."""
import base64
import json
import os
from pathlib import Path
import urllib.request


def main():
    source = Path("outputs/v1_3/platform-responses.json")
    if not source.is_file():
        print("No result bundle available; see job logs")
        return
    repository = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ["GITHUB_REF_NAME"]
    if repository != "ketianli082-stack/algogene-trading-project" or branch != "codex/algogene-crypto-v1.0":
        raise ValueError("Unexpected archive destination")
    run_id = os.environ["GITHUB_RUN_ID"]
    attempt = os.environ["GITHUB_RUN_ATTEMPT"]
    if not run_id.isdigit() or not attempt.isdigit():
        raise ValueError("Unexpected run identifier")
    path = "experiments/EXP-008/runs/%s-attempt-%s.json" % (run_id, attempt)
    payload = {"message": "results: archive V1.3 platform response run " + run_id,
               "branch": branch, "content": base64.b64encode(source.read_bytes()).decode("ascii")}
    url = "https://api.github.com/repos/" + repository + "/contents/" + path
    headers = {"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
               "Accept": "application/vnd.github+json", "Content-Type": "application/json",
               "X-GitHub-Api-Version": "2022-11-28"}
    # An existing run/attempt file is immutable. Never overwrite a prior record.
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="PUT")
    with urllib.request.urlopen(request, timeout=45) as response:
        created = json.load(response)
    print("Saved " + created["content"]["html_url"])


if __name__ == "__main__":
    main()
