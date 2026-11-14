import unittest

from bot import active_game_ids, candidates


def fixture(steals=4, blocks=5, points=5, rebounds=5, assists=5):
    return {"game": {"gameId": "0022600001", "homeTeam": {"players": [{
        "personId": 123, "firstName": "Test", "familyName": "Player", "played": "1",
        "statistics": {"points": points, "reboundsTotal": rebounds, "assists": assists,
                       "steals": steals, "blocks": blocks}}]}, "awayTeam": {"players": []}}}


class AlertTests(unittest.TestCase):
    def test_one_away(self):
        alert = candidates(fixture())[0]
        self.assertEqual((alert["key"], alert["missing"]), ("0022600001:123:one-away", "STL"))

    def test_achieved_has_distinct_key(self):
        self.assertEqual(candidates(fixture(steals=5))[0]["key"], "0022600001:123:achieved")

    def test_two_categories_short_is_not_alert(self):
        self.assertEqual(candidates(fixture(steals=4, blocks=4)), [])

    def test_more_than_one_short_is_not_alert(self):
        self.assertEqual(candidates(fixture(steals=3)), [])

    def test_only_live_games(self):
        data = {"scoreboard": {"games": [{"gameId": "1", "gameStatus": 1},
                                       {"gameId": "2", "gameStatus": 2},
                                       {"gameId": "3", "gameStatus": 3}]}}
        self.assertEqual(active_game_ids(data), ["2"])


if __name__ == "__main__":
    unittest.main()

