import unittest

from bot import active_game_ids, candidates


def fixture(steals=4, blocks=5, points=5, rebounds=5, assists=5):
    return {"header": {"id": "401909300"}, "boxscore": {"players": [{"statistics": [{
        "labels": ["MIN", "PTS", "REB", "AST", "STL", "BLK"],
        "athletes": [{"athlete": {"id": "123", "displayName": "Test Player"},
                      "didNotPlay": False,
                      "stats": ["30", str(points), str(rebounds), str(assists), str(steals), str(blocks)]}]}]}]}}


class AlertTests(unittest.TestCase):
    def test_three_by_five(self):
        self.assertEqual([a["stage"] for a in candidates(fixture(steals=2, blocks=2))], ["3x5"])

    def test_four_by_five_and_one_away(self):
        alerts = candidates(fixture())
        self.assertEqual([a["key"] for a in alerts],
                         ["401909300:123:4x5", "401909300:123:one-away"])
        self.assertEqual(alerts[1]["missing"], "STL")

    def test_four_by_five_without_one_away(self):
        self.assertEqual([a["stage"] for a in candidates(fixture(steals=3))], ["4x5"])

    def test_achieved_has_distinct_key(self):
        self.assertEqual([a["key"] for a in candidates(fixture(steals=5))],
                         ["401909300:123:achieved"])

    def test_two_categories_reached_is_not_alert(self):
        self.assertEqual(candidates(fixture(points=2, steals=2, blocks=2)), [])

    def test_only_live_games(self):
        data = {"events": [{"id": "1", "status": {"type": {"state": "pre"}}},
                           {"id": "2", "status": {"type": {"state": "in"}}},
                           {"id": "3", "status": {"type": {"state": "post"}}}]}
        self.assertEqual(active_game_ids(data), ["2"])


if __name__ == "__main__":
    unittest.main()

