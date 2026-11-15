import unittest
from unittest.mock import patch

from bot import notification_message, publish


class Response:
    status = 200
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class NotificationTests(unittest.TestCase):
    def test_every_stage_uses_ascii_title_and_includes_stats(self):
        for stage in ('5x2', '3x5-2x2', '4x5', 'one-away', 'achieved'):
            with self.subTest(stage=stage):
                title, body = notification_message({
                    'name': 'Test Player', 'stage': stage, 'missing': 'STL',
                    'values': [5, 6, 7, 4, 8], 'team': 'Home', 'game': 'H vs A'})
                title.encode('ascii')
                self.assertIn('Test Player', body)
                self.assertIn('PTS 5 · REB 6 · AST 7 · STL 4 · BLK 8', body)
                self.assertIn('Home · H vs A', body)
        self.assertIn('one more STL', notification_message({
            'name': 'Test Player', 'stage': 'one-away', 'missing': 'STL',
            'values': [5, 6, 7, 4, 8]})[1])

    def test_publish_sends_utf8_body_and_safe_headers(self):
        alert = {'name': 'José Test', 'stage': 'achieved', 'missing': None,
                 'values': [5, 5, 5, 5, 5]}
        with patch('urllib.request.urlopen', return_value=Response()) as send:
            publish('example-topic', alert)
        request = send.call_args.args[0]
        self.assertEqual(request.get_header('Title'), 'NBA 5x5 achieved!')
        self.assertIn('José Test has completed a 5×5!', request.data.decode('utf-8'))
        self.assertEqual(request.full_url, 'https://ntfy.sh/example-topic')


if __name__ == '__main__':
    unittest.main()
