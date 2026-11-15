import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bot
from dashboard import Handler


class DashboardTests(unittest.TestCase):
    def test_player_progress_and_dnp(self):
        box = {"boxscore": {"players": [{"team": {"id": "1"}, "statistics": [{
            "labels": ["PTS", "REB", "AST", "STL", "BLK"], "athletes": [
                {"athlete": {"id": "7", "displayName": "Starter"}, "stats": ["7", "5", "4", "2", "0"]},
                {"athlete": {"id": "8", "displayName": "Bench"}, "didNotPlay": True, "stats": []},
                {"athlete": {"id": "9", "displayName": "Bad"}, "stats": ["x"]}]}]}]}}
        event = {"id": "42", "status": {"type": {"shortDetail": "Q3"}},
                 "competitions": [{"competitors": [{"team": {"id": "1", "displayName": "Home", "abbreviation": "H"}}]}]}
        rows = bot.players(box, event)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['reached'], rows[0]['distance'], rows[0]['minimum']), (2, 9, 0))

    def test_local_history_is_preserved_and_atomic(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'sent.json'
            path.write_text('{"old:player:5x2":"yesterday"}', encoding='utf-8')
            state = bot.LocalState(path)
            sent, _ = state.load()
            sent['new:player:achieved'] = 'today'
            state.save(sent)
            self.assertEqual(json.loads(path.read_text()), sent)
            self.assertEqual(list(Path(temp).iterdir()), [path])
            path.write_text('[]', encoding='utf-8')
            with self.assertRaises(ValueError):
                state.load()

    def test_dashboard_snapshot_uses_poll_without_publishing_twice(self):
        with tempfile.TemporaryDirectory() as temp:
            event = {"id": "42", "status": {"type": {"state": "in"}}, "competitions": [{"competitors": []}]}
            box = {"header": {"id": "42"}, "boxscore": {"players": []}}
            with patch.dict('os.environ', {'STATE_MODE': 'local', 'NTFY_TOPIC': 'test',
                                           'SENT_PATH': str(Path(temp) / 'sent.json'),
                                           'DASHBOARD_DATA': str(Path(temp) / 'dashboard.json')}), \
                 patch.object(bot, 'request_json', side_effect=[{'events': [event]}, box]), \
                 patch.object(bot, 'publish') as publish:
                bot.run()
            snapshot = json.loads((Path(temp) / 'dashboard.json').read_text())
            self.assertEqual(snapshot['status'], 'ok')
            self.assertEqual(snapshot['active_games'], 1)
            self.assertTrue(snapshot['last_successful_check'])
            publish.assert_not_called()

    def test_partial_game_failure_records_degraded_and_fails_task(self):
        with tempfile.TemporaryDirectory() as temp:
            event = {"id": "42", "status": {"type": {"state": "in"}}}
            with patch.dict('os.environ', {'STATE_MODE': 'local', 'NTFY_TOPIC': 'test',
                                           'SENT_PATH': str(Path(temp) / 'sent.json'),
                                           'DASHBOARD_DATA': str(Path(temp) / 'dashboard.json')}), \
                 patch.object(bot, 'request_json', side_effect=[{'events': [event]}, KeyError('box')]):
                with self.assertRaises(RuntimeError):
                    bot.run()
            self.assertEqual(json.loads((Path(temp) / 'dashboard.json').read_text())['status'], 'degraded')


if __name__ == '__main__':
    unittest.main()
