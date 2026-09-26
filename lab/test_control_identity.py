import unittest

from control_identity import Sessions, SESSION_SECONDS, session_cookie


class SessionContract(unittest.TestCase):
    def test_cookie_and_expiry(self):
        now = [100.0]
        sessions = Sessions(lambda: now[0])
        token = sessions.create({'username': 'alice', 'is_admin': False})
        cookie = session_cookie(token)
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Strict', cookie)
        self.assertEqual(sessions.get(cookie)['username'], 'alice')
        now[0] += SESSION_SECONDS
        self.assertIsNone(sessions.get(cookie))

    def test_logout_discards_session(self):
        sessions = Sessions()
        token = sessions.create({'username': 'bob', 'is_admin': True})
        cookie = session_cookie(token)
        sessions.discard(cookie)
        self.assertIsNone(sessions.get(cookie))


if __name__ == '__main__':
    unittest.main()
