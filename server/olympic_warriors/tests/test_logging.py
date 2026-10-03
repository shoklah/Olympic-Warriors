"""
The app's own loggers (getLogger(__name__) under `olympic_warriors`) print on the console, so
`docker compose logs` shows why a password reset sent no mail. Without the `olympic_warriors`
entry of settings.LOGGING only WARNING and above reach stderr, through Python's last-resort
handler, and every INFO line is lost.
"""

import logging

from django.conf import settings
from django.test import SimpleTestCase


class TestAppLogging(SimpleTestCase):
    def test_the_app_logger_has_a_console_handler(self):
        loggers = settings.LOGGING["loggers"]
        self.assertIn("olympic_warriors", loggers)
        self.assertIn("console", loggers["olympic_warriors"]["handlers"])
        handlers = logging.getLogger("olympic_warriors").handlers
        self.assertTrue(any(isinstance(h, logging.StreamHandler) for h in handlers), handlers)

    def test_info_reaches_the_password_reset_log(self):
        self.assertTrue(
            logging.getLogger("olympic_warriors.password_reset").isEnabledFor(logging.INFO)
        )
