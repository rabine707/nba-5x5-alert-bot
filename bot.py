"""Poll NBA live data and publish one-away/achieved 5x5 alerts."""
import json
import logging
import os
from pathlib import Path
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
LOG = logging.getLogger("nba5x5")


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


def players(boxscore, event):
    """Normalize a live box score for the dashboard, independently of alert eligibility."""
    teams = {str(t.get("team", {}).get("id")): t.get("team", {}).get("displayName", "")
             for t in event.get("competitions", [{}])[0].get("competitors", [])}
    rows = []
    for team in boxscore.get("boxscore", {}).get("players", []):
        team_name = teams.get(str(team.get("team", {}).get("id")),
                              team.get("team", {}).get("displayName", ""))
        for group in team.get("statistics", []):
            labels = group.get("labels", [])
            if not all(label in labels for label in CATEGORIES):
                continue
            for player in group.get("athletes", []):
                if player.get("didNotPlay"):
                    continue
                try:
                    stats = [int(player["stats"][labels.index(label)] or 0) for label in CATEGORIES]
                    athlete = player["athlete"]
                except (KeyError, IndexError, TypeError, ValueError):
                    LOG.warning("Skipping malformed player in game %s", event.get("id"))
                    continue
                rows.append({"id": str(athlete["id"]), "name": athlete["displayName"],
                             "team": team_name, "game_id": str(event["id"]),
                             "game": " vs ".join(c.get("team", {}).get("abbreviation", "")
                                                  for c in event.get("competitions", [{}])[0].get("competitors", [])),
                             "status": event.get("status", {}).get("type", {}).get("shortDetail", "Live"),
                             "values": stats, "reached": sum(v >= 5 for v in stats),
                             "distance": sum(max(0, 5 - v) for v in stats),
                             "minimum": min(stats)})
    return rows


def classify(game_id, player_id, name, values):
    if len(values) != 5:
        raise ValueError("A 5x5 requires five stat values")
    reached = sum(value >= 5 for value in values)
    stages = []
    if reached < 3:
        if min(values) >= 2:
            stages.append("5x2")
    elif reached == 3:
        low = [i for i, value in enumerate(values) if value < 5]
        if any(values[i] == 4 for i in low):
            stages.append("3x5-1x4")
        elif min(values) >= 2:
            stages.append("3x5-2x2")
    elif reached == 4:
        stages.append("4x5")
        low = [i for i, value in enumerate(values) if value < 5]
        if values[low[0]] == 4:
            stages.append("one-away")
    elif reached == 5:
        stages.append("achieved")
    return [{"key": f"{game_id}:{player_id}:{stage}", "game_id": game_id,
             "name": name, "stage": stage,
             "missing": CATEGORIES[next(i for i in low if values[i] == 4)] if stage == "3x5-1x4" else CATEGORIES[low[0]] if stage == "one-away" else None,
             "values": values} for stage in stages]


def active_game_ids(scoreboard):
    return [str(g["id"]) for g in scoreboard["events"]
            if g["status"]["type"].get("state") == "in"]


def notification_message(alert):
    """Build readable ntfy copy; HTTP header values must remain ASCII."""
    titles = {"5x2": "5x5 watch: let him cook",
              "3x5-2x2": "5x5 watch: the plot thickens",
              "3x5-1x4": "5x5 watch: the fourth category is loading",
              "4x5": "5x5 watch: we're so back",
              "one-away": "5x5 watch: EVERYBODY STAY CALM",
              "achieved": "5x5 ACHIEVED: absolute cinema"}
    details = {"5x2": "has 2+ in every category. The 5×5 recipe is on the stove.",
               "3x5-2x2": "has 5+ in three categories and 2+ in the other two. This is no longer a drill.",
               "3x5-1x4": f"has 5+ in three categories and 4 {alert['missing']}. One more {alert['missing']} makes it four at 5+. The plot thickens.",
               "4x5": "has 5+ in four categories. One category left. Do you believe in miracles?",
               "one-away": f"needs just one more {alert['missing']} for a 5×5. EVERYBODY STAY CALM.",
               "achieved": "just pulled off a 5×5. Hang the box score in the Louvre."}
    stats = " · ".join(f"{label} {value}" for label, value in zip(CATEGORIES, alert["values"]))
    context = " · ".join(v for v in (alert.get("team"), alert.get("game")) if v)
    body = f"{alert['name']} {details[alert['stage']]}\n{stats}"
    if context:
        body += f"\n{context}"
    return titles[alert["stage"]], body


def publish(topic, alert):
    if not topic or "/" in topic or "?" in topic:
        raise ValueError("NTFY_TOPIC must be a single topic name")
    url = "https://ntfy.sh/" + urllib.parse.quote(topic, safe="")
    title, body = notification_message(alert)
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


STAGE_RANK = {"3x5": 0, "3x5-1x2": 0, "5x2": 1,
              "3x5-2x2": 2, "3x5-1x4": 2.5, "4x5": 3, "one-away": 4, "achieved": 5}


def should_send(alert, sent):
    prefix = alert["key"].rsplit(":", 1)[0] + ":"
    return alert["key"] not in sent and not any(
        key.startswith(prefix) and
        STAGE_RANK.get(key.rsplit(":", 1)[-1], 0) > STAGE_RANK[alert["stage"]]
        for key in sent
    )


class LocalState:
    """Atomic local history writes; the existing JSON key/timestamp format stays intact."""
    def __init__(self, path):
        self.path = Path(path)

    def ensure(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self):
        if not self.path.exists():
            return {}, None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("sent.json must contain an object")
        return data, None

    def save(self, sent, sha=None):
        import tempfile
        import os
        fd, name = tempfile.mkstemp(prefix=".sent-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(sent, file, indent=2, sort_keys=True)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def write_dashboard(path, snapshot):
    import tempfile
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".dashboard-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(snapshot, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def run():
    if os.getenv("TEST_NOTIFICATION") == "1":
        topic = os.getenv("NTFY_TOPIC")
        if not topic:
            raise RuntimeError("Missing NTFY_TOPIC")
        publish_test(topic)
        print("Test notification accepted by ntfy")
        return
    dry_run = os.getenv("DRY_RUN") == "1"
    local = os.getenv("STATE_MODE", "github").lower() == "local"
    if dry_run:
        LOG.info("Dry run: no notification or state write")
    else:
        for name in (("NTFY_TOPIC",) if local else ("NTFY_TOPIC", "GITHUB_TOKEN", "GITHUB_REPOSITORY")):
            if not os.getenv(name):
                raise RuntimeError(f"Missing {name}")
    scoreboard = request_json(SCOREBOARD)
    events = [e for e in scoreboard["events"] if e["status"]["type"].get("state") == "in"]
    LOG.info("Active games: %s", len(events))
    alerts = []
    rows = []
    errors = []
    for event in events:
        game_id = str(event["id"])
        try:
            box = request_json(BOXSCORE.format(game_id))
            game_rows = players(box, event)
            rows.extend(game_rows)
            context = {row["id"]: row for row in game_rows}
            for alert in candidates(box):
                row = context.get(alert["key"].split(":")[1], {})
                alert.update({"team": row.get("team", ""), "game": row.get("game", "")})
                alerts.append(alert)
        except (urllib.error.URLError, KeyError, ValueError, TypeError) as exc:
            LOG.exception("Game %s failed", game_id)
            errors.append(game_id)
    LOG.info("Eligible alerts: %s", len(alerts))
    if dry_run:
        for alert in alerts:
            LOG.info("DRY RUN: %s %s %s", alert['name'], alert['stage'], alert['values'])
        if os.getenv("GITHUB_TOKEN") and os.getenv("GITHUB_REPOSITORY"):
            state = GitHubState(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])
            state.ensure()
            sent, _ = state.load()
            LOG.info("Stored alert keys: %s", len(sent))
        return
    root = Path(__file__).resolve().parent
    state = LocalState(os.getenv("SENT_PATH", str(root / "sent.json"))) if local else GitHubState(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])
    state.ensure()
    sent, sha = state.load()
    recent = []
    for alert in alerts:
        if not should_send(alert, sent):
            continue
        publish(os.environ["NTFY_TOPIC"], alert)
        timestamp = datetime.now(timezone.utc).isoformat()
        sent[alert["key"]] = timestamp
        # Persist after each successful publish so a later failure cannot replay earlier alerts.
        for attempt in range(3):
            try:
                state.save(sent, sha)
                sent, sha = state.load()
                break
            except urllib.error.HTTPError as e:
                if local or e.code != 409 or attempt == 2:
                    raise
                sent, sha = state.load()
                sent[alert["key"]] = datetime.now(timezone.utc).isoformat()
                time.sleep(attempt + 1)
        recent.append({"name": alert["name"], "stage": alert["stage"], "team": alert.get("team", ""), "at": timestamp})
        LOG.info("Published %s for %s", alert['stage'], alert['name'])
    if local:
        snapshot_path = Path(os.getenv("DASHBOARD_DATA", str(root / "dashboard.json")))
        previous = {}
        if snapshot_path.exists():
            try:
                previous = json.loads(snapshot_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                LOG.warning("Previous dashboard snapshot unreadable")
        history = (recent + previous.get("recent_alerts", []))[:20]
        known = {f"{a['name']}:{a['stage']}:{a['at']}" for a in history}
        names = {(r['game_id'], r['id']): r for r in rows}
        for key, timestamp in sorted(sent.items(), key=lambda item: str(item[1]), reverse=True):
            parts = key.split(":")
            if len(parts) != 3 or not isinstance(timestamp, str):
                continue
            row = names.get((parts[0], parts[1]), {})
            name = row.get('name', f'Player {parts[1]}')
            if f"{name}:{parts[2]}:{timestamp}" not in known:
                history.append({"name": name, "stage": parts[2], "team": row.get('team', ''), "at": timestamp})
                known.add(f"{name}:{parts[2]}:{timestamp}")
        history = sorted(history, key=lambda a: a.get('at', ''), reverse=True)[:20]
        snapshot = {"updated_at": datetime.now(timezone.utc).isoformat(),
                    "last_successful_check": datetime.now(timezone.utc).isoformat() if not errors else previous.get("last_successful_check"),
                    "status": "degraded" if errors else "ok", "failed_games": errors,
                    "active_games": len(events), "players": sorted(rows, key=lambda r: (r["reached"], -r["distance"], r["minimum"]), reverse=True),
                    "recent_alerts": history}
        write_dashboard(snapshot_path, snapshot)
    if errors:
        raise RuntimeError(f"Failed to check {len(errors)} active game(s): {', '.join(errors)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    try:
        run()
    except Exception as e:
        print(f"Bot failed: {type(e).__name__}: {e}", file=sys.stderr)
        raise SystemExit(1)

