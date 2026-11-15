# NBA 5×5 alert bot

Free experimental NBA 5×5 watch for an iPhone subscribed to an [ntfy](https://ntfy.sh/) topic. GitHub Actions can poll the ESPN NBA live scoreboard every five minutes; a Windows Task Scheduler deployment can poll every three minutes and checks each active game's box score. It begins alerting at 5×2 (at least 2 in all five of points, rebounds, assists, steals, and blocks), then at 3×5/2×2 (5+ in three categories and 2+ in the other two), 3×5/1×4 (5+ in three categories and 4 in a fourth, regardless of the fifth), 4×5, and 5×5. Plain 3×5 and 3×5/1×2 without a fourth category at 4 do not alert. A separate one-away alert fires when four categories are at 5+ and the fifth reaches 4. Each stage is sent at most once per player per game. If a player first appears at a later stage, the bot sends the current milestone rather than replaying earlier ones. A 4×5 and one-away alert may arrive together.

## Setup from an iPhone

1. Install ntfy and subscribe to a long, random topic name that you do not share. On ntfy.sh, a topic is **unguessable**, not truly private: anyone who learns its name can read or publish to it. For actual access control, use an authenticated ntfy server.
2. In this repository, open **Settings → Secrets and variables → Actions → New repository secret**. Name it `NTFY_TOPIC` and enter only the topic name (no `https://ntfy.sh/`). Never put this value in code, an issue, a screenshot, or a workflow input.
3. Open **Actions → NBA 5x5 alerts → Run workflow**. Leave `dry_run` checked for the first test. Review the run log for the number of active games and eligible alerts. It will send nothing and will not write state.
4. To verify delivery, run the workflow with `test_notification` checked. It sends one message labeled **NBA 5x5 bot test** to the saved topic and does not claim a live milestone.
5. Once the dry run succeeds, run it again with `dry_run` unchecked and `test_notification` unchecked. If no player qualifies, that is expected and no notification will arrive. A real milestone during a scheduled run will send one.

The workflow uses GitHub's built-in token to create an `alert-state` branch and write `sent.json` after each delivered alert. That branch contains only game/player milestone keys and timestamps, never the ntfy topic. The workflow's concurrency group prevents overlapping scheduled and manual runs. If ntfy succeeds but GitHub's state write fails, a later run can repeat that alert; the failing run will be visible in Actions.

## Local checks

```sh
python -m unittest discover -s tests -v
DRY_RUN=1 python bot.py
```

The second command still requires network access to ESPN's live feed. Its output is informational; it sends no notification.

## Limits

GitHub scheduled workflows can be delayed or dropped under load, and schedules in inactive public repositories can be disabled. This is a hobby alert, not a guaranteed real-time service. ESPN's public live JSON feed may change without notice. The bot currently checks games marked in progress, so it does not replay a milestone first discovered after a game has become final. ntfy.sh topics are public to anyone who knows the topic name.


## Windows mini PC deployment and local dashboard

This repository's original GitHub Actions workflow uses the `alert-state` branch. The local mode below uses **your existing local `sent.json`**. These are separate histories: run only one publisher for the same ntfy topic to avoid duplicate notifications. Disable the scheduled GitHub workflow if it is active. Neither local history nor the ntfy topic belongs in Git. No extra Python packages, API keys, database, or hosting are required.

1. On the mini PC, install Python 3.12+ and Git. Back up the existing `sent.json` (for example, copy it to a USB drive). From PowerShell, clone this repository or update the existing checkout after the pull request is merged. Keep the existing `sent.json` in the repository folder, beside `bot.py`. If it currently lives elsewhere, set `SENT_PATH` to its absolute path; do not replace it with an empty file. The bot reads its existing keys and writes changes atomically.
2. Set `NTFY_TOPIC` as a **user environment variable** in Windows Environment Variables (topic name only). Restart Task Scheduler or sign out and back in so scheduled tasks inherit it. Keep the topic out of scripts and Git. You can also set `SENT_PATH` and `DASHBOARD_DATA` as user environment variables to absolute file paths if needed. Set `STATE_MODE=local` for any manual `bot.py` invocation; the supplied poll script sets it automatically.
3. In PowerShell from the checkout, run `py -3 -m unittest discover -s tests -v`. Then set `$env:STATE_MODE='local'; $env:DRY_RUN='1'; py -3 bot.py` for a read-only live check. Remove `DRY_RUN` (`Remove-Item Env:DRY_RUN`) before a real poll. Run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\windows\poll.ps1` once and inspect `logs\poll.log`, `sent.json`, and `dashboard.json`. A poll with no active games correctly writes an empty leaderboard.
4. In Task Scheduler, create or update the **poll task** under the same Windows user account that owns the environment variable and history file. Action: `powershell.exe`; arguments: `-NoProfile -ExecutionPolicy Bypass -File "C:\path\to\nba-5x5-alert-bot\windows\poll.ps1"`. Trigger daily, repeat every **3 minutes** indefinitely. Set **If the task is already running: Do not start a new instance**. Use the working directory of the checkout if you wish, though the script resolves paths itself. Enable task history.
5. Create a second task at user logon for the read-only dashboard. Action: `powershell.exe`; arguments: `-NoProfile -ExecutionPolicy Bypass -File "C:\path\to\nba-5x5-alert-bot\windows\dashboard.ps1"`. Set **If already running: Do not start a new instance** and allow the task to run indefinitely. Alternatively run `py -3 dashboard.py` in an open PowerShell window. Open **http://127.0.0.1:8765/** on the mini PC. The browser refreshes every 30 seconds; the data changes when the existing three-minute poll completes. It binds to loopback only, with no internet exposure. For remote access, use a trusted tunnel such as Tailscale rather than binding the dashboard publicly.

The dashboard ranks live players by categories at 5+, then total remaining stats. Its five stat tiles show exact values; a 5×5 requires all five at 5+. It shows game context, recent alerts reconstructed from local history (old entries without names appear by player ID), the last fully successful poll, and stale/partial status. `dashboard.json`, `sent.json`, and logs are ignored by Git. A malformed game yields a nonzero task exit and a degraded snapshot; successfully processed games may still send their alerts. The most recent twenty alerts are displayed. Historical `sent.json` entries remain intact.

If the poll fails, inspect `logs\poll.log` and Task Scheduler's Last Run Result. A stale badge means no snapshot update for over ten minutes. If `sent.json` is malformed, restore the backup; the bot fails rather than clearing it. Verify that `NTFY_TOPIC` is visible to the scheduled user account. The dashboard does not directly fetch ESPN, so its server can be restarted without disturbing alert state.
