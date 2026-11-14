import unittest

from bot import active_game_ids, candidates


def fixture(steals=4, blocks=5, points=5, rebounds=5, assists=5):
    return {"header": {"id": "401909300"}, "boxscore": {"players": [{"statistics": [{
        "labels": ["MIN", "PTS", "REB", "AST", "STL", "BLK"],
        "athletes": [{"athlete": {"id": "123", "displayName": "Test Player"},
                      "didNotPlay": False,
                      "stats": ["30", str(points), str(rebounds), str(assists), str(steals), str(blocks)]}]}]}]}}


class AlertTests(unittest.TestCase):
    def test_one_away(self):
        alert = candidates(fixture())[0]
        self.assertEqual((alert["key"], alert["missing"]), ("401909300:123:one-away", "STL"))

    def test_achieved_has_distinct_key(self):
        self.assertEqual(candidates(fixture(steals=5))[0]["key"], "401909300:123:achieved")

    def test_two_categories_short_is_not_alert(self):
        self.assertEqual(candidates(fixture(steals=4, blocks=4)), [])

    def test_more_than_one_short_is_not_alert(self):
        self.assertEqual(candidates(fixture(steals=3)), [])

    def test_only_live_games(self):
        data = {"events": [{"id": "1", "status": {"type": {"state": "pre"}}},
                           {"id": "2", "status": {"type": {"state": "in"}}},
                           {"id": "3", "status": {"type": {"state": "post"}}}]}
        self.assertEqual(active_game_ids(data), ["2"])


if __name__ == "__main__":
    unittest.main()

