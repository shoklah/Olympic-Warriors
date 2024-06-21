import os
from functools import lru_cache
from enum import Enum
from pydantic import model_validator

from pydantic_settings import BaseSettings


class LogLevel(str, Enum):
    """
    Enum for logging levels.
    """

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class BaseConfig(BaseSettings):
    """
    Base configuration class. All configuration classes should inherit from this class.
    """

    # The following are the default values for the configuration variables.
    # These values are overridden by the values in the .env file.
    # If a .env file is not present, the values below are used.
    # If a .env file is present, but a variable is not defined in the .env file,
    # the value below is used.
    # If a .env file is present, and a variable is defined in the .env file,
    # the value in the .env file is used.
    # The .env file is not committed to the repository.
    # See the .env.example file for an example of the .env file.
    # See https://pydantic-docs.helpmanual.io/usage/settings/ for more information.

    SECRET_KEY: str
    DEBUG: bool

    DB_HOST: str
    DB_NAME: str
    DB_USER: str
    DB_PASS: str
    DB_PORT: int

    LOG_LEVEL_CONSOLE: str = "INFO"
    LOG_LEVEL_FILE: str = "INFO"
    LOG_FILE: str = "asset_monitor.log"

    SU_USERNAME: str = "admin"
    SU_PASSWORD: str = "password"

    BASE_URL: str = "localhost"

    @model_validator(mode="after")
    def validate_log_level(self):
        """
        Validate the log level.
        """
        log_level_console = self.LOG_LEVEL_CONSOLE
        log_level_file = self.LOG_LEVEL_FILE

        if log_level_console not in LogLevel.__members__:
            raise ValueError(f"Invalid log level: {log_level_console}")

        if log_level_file not in LogLevel.__members__:
            raise ValueError(f"Invalid log level: {log_level_file}")

        return self

    @model_validator(mode="after")
    def override_if_env(self):
        """
        override the values if they are defined in the environment
        """
        for key, value in os.environ.items():
            if hasattr(self, key):
                setattr(self, key, value)

        return self

    class Config:
        env_file = ".env.example"
        env_file_encoding = "utf-8"
        case_sensitive = False


class DevConfig(BaseConfig):
    """
    Development configuration class.
    """

    class Config:
        env_file = "dev.env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class ProdConfig(BaseConfig):
    """
    Production configuration class.
    """

    class Config:
        env_file = "prod.env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# decorator to return always a cached value after the first real call to the method
#  as we do not want to load and read multiple time files, validate values etc...
#  see https://docs.python.org/3/library/functools.html#functools.lru_cache
@lru_cache()
def get_settings():
    """
    Load the app configuration on the first call only and return them.

    It relies on a decorator to keep in cache the first return of this method for later calls.

    :return: configuration
    """
    env = os.environ.get("ENV", "dev").lower()
    settings = {}

    if env == "dev":
        settings = DevConfig()
    elif env == "prod":
        settings = ProdConfig()
    return settings
