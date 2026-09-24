"""
A real environment variable overrides the env file and is parsed like it: CI reads every
setting from its job variables, so `DEBUG=False` has to arrive as False, not as the true-valued
string 'False'.
"""

import os
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from olympic_warriors.config import DevConfig

REQUIRED = {
    "SECRET_KEY": "test",
    "DEBUG": "False",
    "DB_HOST": "localhost",
    "DB_NAME": "test",
    "DB_USER": "test",
    "DB_PASS": "test",
    "DB_PORT": "5432",
}


class TestConfigFromEnvironment(SimpleTestCase):
    """DevConfig built from environment variables alone, as in CI."""

    def config(self, env, env_file=None):
        with mock.patch.dict(os.environ, env, clear=True):
            return DevConfig(_env_file=env_file)

    def test_values_are_parsed(self):
        config = self.config({
            **REQUIRED,
            "ALLOWED_HOSTS": '["localhost","server"]',
            "NUM_PROXIES": "2",
        })
        self.assertIs(config.DEBUG, False)
        self.assertEqual(config.DB_PORT, 5432)
        self.assertEqual(config.ALLOWED_HOSTS, ["localhost", "server"])
        self.assertEqual(config.NUM_PROXIES, 2)

    def test_environment_overrides_the_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as env_file:
            env_file.write("DEBUG=True\nDB_PORT=5433\nNUM_PROXIES=1\n")
        self.addCleanup(os.remove, env_file.name)
        config = self.config({**REQUIRED, "NUM_PROXIES": "3"}, env_file.name)
        self.assertIs(config.DEBUG, False)
        self.assertEqual(config.DB_PORT, 5432)
        self.assertEqual(config.NUM_PROXIES, 3)

    def test_the_file_fills_what_the_environment_lacks(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as env_file:
            env_file.write("NUM_PROXIES=4\n")
        self.addCleanup(os.remove, env_file.name)
        self.assertEqual(self.config(REQUIRED, env_file.name).NUM_PROXIES, 4)
