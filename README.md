# NBA 5×5 alert bot

Free experimental NBA 5×5 watch for an iPhone subscribed to an [ntfy](https://ntfy.sh/) topic. A GitHub Actions job polls the ESPN NBA live scoreboard every five minutes and checks each active game's box score. It sends one alert when a player has at least five points, rebounds, assists, steals, and blocks except for exactly one category at four, and another if the player completes the 5×5.

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

