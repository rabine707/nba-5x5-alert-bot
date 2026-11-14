"""Poll NBA live data and publish one-away/achieved 5x5 alerts."""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
BOXSCORE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={}"
API = "https://api.github.com"
CATEGORIES = ("PTS", "REB", "AST", "STL", "BLK")


def request_json(url, *, method="GET", data=None, headers=None):
    base_headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*", "Referer": "https://www.espn.com/"}
    base_headers.update(headers or {})
    body = json.dumps(data).encode() if data is not None else None
    if body is not None:
        base_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=base_headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def candidates(boxscore):
    game_id = str(boxscore["header"]["id"])
    result = []
    for team in boxscore["boxscore"].get("players", []):
        for group in team.get("statistics", []):
            labels = group.get("labels", [])
            if not all(label in labels for label in CATEGORIES):
                continue
            for player in group.get("athletes", []):
                if player.get("didNotPlay"):
                    continue
                values = [int(player["stats"][labels.index(label)] or 0) for label in CATEGORIES]
                result.extend(classify(game_id, str(player["athlete"]["id"]),
                                       player["athlete"]["displayName"], values))
    return result


def classify(game_id, player_id, name, values):
    if len(values) != 5:
        raise ValueError("A 5x5 requires five stat values")
    reached = sum(value >= 5 for value in values)
    stages = []
    if reached == 3:
        stages.append("3x5")
    elif reached == 4:
        stages.append("4x5")
        low = [i for i, value in enumerate(values) if value < 5]
        if values[low[0]] == 4:
            stages.append("one-away")
    elif reached == 5:
        stages.append("achieved")
    return [{"key": f"{game_id}:{player_id}:{stage}", "game_id": game_id,
             "name": name, "stage": stage,
             "missing": CATEGORIES[low[0]] if stage == "one-away" else None,
             "values": values} for stage in stages]


def active_game_ids(scoreboard):
    return [str(g["id"]) for g in scoreboard["events"]
            if g["status"]["type"].get("state") == "in"]


def publish(topic, alert):
    if not topic or "/" in topic or "?" in topic:
        raise ValueError("NTFY_TOPIC must be a single topic name")
    url = "https://ntfy.sh/" + urllib.parse.quote(topic, safe="")
    stats = " · ".join(f"{value} {label}" for value, label in zip(alert["values"], CATEGORIES))
    titles = {"3x5": "3×5 milestone", "4x5": "4×5 milestone",
              "one-away": "5×5 watch: one away", "achieved": "5×5 achieved!"}
    details = {"3x5": "has 5+ in three stat categories",
               "4x5": "has 5+ in four stat categories",
               "one-away": f"needs one more {alert['missing']}",
               "achieved": "has reached a 5×5"}
    title = titles[alert["stage"]]
    detail = details[alert["stage"]]
    body = f"{alert['name']} {detail}.\n{stats}"
    req = urllib.request.Request(url, data=body.encode(), method="POST", headers={
        "Title": title, "Priority": "high", "Tags": "basketball", "Content-Type": "text/plain; charset=utf-8",
        "User-Agent": "nba-5x5-alert-bot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status >= 300:
            raise RuntimeError(f"ntfy returned HTTP {response.status}")


def publish_test(topic):
    if not topic or "/" in topic or "?" in topic:
        raise ValueError("NTFY_TOPIC must be a single topic name")
    req = urllib.request.Request("https://ntfy.sh/" + urllib.parse.quote(topic, safe=""),
        data=b"Connection test from GitHub Actions. No live NBA milestone.", method="POST",
        headers={"Title": "NBA 5x5 bot test", "Priority": "default", "Tags": "basketball",
                 "User-Agent": "nba-5x5-alert-bot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status >= 300:
            raise RuntimeError(f"ntfy returned HTTP {response.status}")


class GitHubState:
    """Store sent keys in a dedicated branch using GitHub's contents API."""
    def __init__(self, repo, token, branch="alert-state"):
        self.repo, self.token, self.branch = repo, token, branch
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28"}
        self.path = f"{API}/repos/{repo}/contents/sent.json?ref={urllib.parse.quote(branch)}"

    def ensure(self):
        ref_url = f"{API}/repos/{self.repo}/git/ref/heads/{self.branch}"
        try:
            request_json(ref_url, headers=self.headers)
            return
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
        default = request_json(f"{API}/repos/{self.repo}", headers=self.headers)["default_branch"]
        head = request_json(f"{API}/repos/{self.repo}/git/ref/heads/{default}", headers=self.headers)
        try:
            request_json(f"{API}/repos/{self.repo}/git/refs", method="POST",
                         data={"ref": f"refs/heads/{self.branch}", "sha": head["object"]["sha"]}, headers=self.headers)
        except urllib.error.HTTPError as e:
            if e.code != 422:  # Another run created it.
                raise

    def load(self):
        import base64
        try:
            item = request_json(self.path, headers=self.headers)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}, None
            raise
        return json.loads(base64.b64decode(item["content"]).decode()), item["sha"]

    def save(self, sent, sha):
        import base64
        payload = {"message": "Record delivered NBA 5x5 alert", "branch": self.branch,
                   "content": base64.b64encode((json.dumps(sent, sort_keys=True, indent=2) + "\n").encode()).decode()}
        if sha:
            payload["sha"] = sha
        request_json(f"{API}/repos/{self.repo}/contents/sent.json", method="PUT", data=payload, headers=self.headers)


def run():
    if os.getenv("TEST_NOTIFICATION") == "1":
        topic = os.getenv("NTFY_TOPIC")
        if not topic:
            raise RuntimeError("Missing NTFY_TOPIC")
        publish_test(topic)
        print("Test notification accepted by ntfy")
        return
    if os.getenv("DRY_RUN") == "1":
        print("Dry run: no notification or state write")
    else:
        for name in ("NTFY_TOPIC", "GITHUB_TOKEN", "GITHUB_REPOSITORY"):
            if not os.getenv(name):
                raise RuntimeError(f"Missing {name}")
    ids = active_game_ids(request_json(SCOREBOARD))
    print(f"Active games: {len(ids)}")
    alerts = []
    for game_id in ids:
        alerts.extend(candidates(request_json(BOXSCORE.format(game_id))))
    print(f"Eligible alerts: {len(alerts)}")
    if os.getenv("DRY_RUN") == "1":
        for alert in alerts:
            print(f"DRY RUN: {alert['name']} {alert['stage']} {alert['values']}")
        if os.getenv("GITHUB_TOKEN") and os.getenv("GITHUB_REPOSITORY"):
            state = GitHubState(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])
            state.ensure()
            sent, _ = state.load()
            print(f"Stored alert keys: {len(sent)}")
        return
    state = GitHubState(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])
    state.ensure()
    sent, sha = state.load()
    for alert in alerts:
        if alert["key"] in sent:
            continue
        publish(os.environ["NTFY_TOPIC"], alert)
        sent[alert["key"]] = datetime.now(timezone.utc).isoformat()
        # Persist after each successful publish so a later failure cannot replay earlier alerts.
        for attempt in range(3):
            try:
                state.save(sent, sha)
                sent, sha = state.load()
                break
            except urllib.error.HTTPError as e:
                if e.code != 409 or attempt == 2:
                    raise
                sent, sha = state.load()
                sent[alert["key"]] = datetime.now(timezone.utc).isoformat()
                time.sleep(attempt + 1)
        print(f"Published {alert['stage']} for {alert['name']}")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"Bot failed: {type(e).__name__}: {e}", file=sys.stderr)
        raise SystemExit(1)

