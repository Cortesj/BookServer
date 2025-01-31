# ********************************************
# |docname| - Configuring Runestone BookServer
# ********************************************
# Many thing about Runestone BookServer are configurable. This is the place to change
# the configuration for most things.  **Private** things should be configured in the
# environment so they are not accidentally committed to Github.
# Defaults provided here may be overridden by environment variables `Per <https://fastapi.tiangolo.com/advanced/settings/>`_.
#
#
# Imports
# =======
# These are listed in the order prescribed by `PEP 8`_.
#
# Standard library
# ----------------
from enum import Enum
from functools import lru_cache
import os
from pathlib import Path

# Third-party imports
# -------------------
import pkg_resources
from pydantic import BaseSettings

# Local application imports
# -------------------------
from .applogger import rslogger

# Settings
# ========
# Define the possible bookserver configurations. The values assigned must  be strings, since Pydantic will match these with environment variables.


class BookServerConfig(Enum):
    development = "development"
    test = "test"
    production = "production"


# A enum for the type of database in use.
class DatabaseType(Enum):
    SQLite = 0
    PostgreSQL = 1


class Settings(BaseSettings):
    # Pydantic provides a wonderful utility to handle settings.  The beauty of it
    # is that you can specify variables with or without default values, and Pydantic
    # will check your environment variables in a case-insensitive way. So that
    # if you have ``PROD_DBURL``` set in the environment it will be set as the value
    # for ``prod_dburl``` in settings.
    # This is a really nice way to keep from
    # committing any data you want to keep private.

    google_ga: str = ""

    # Provide a path to the book server files. The leading underscore prevents environment variables from affecting this value. See the `docs <https://pydantic-docs.helpmanual.io/usage/models/#automatically-excluded-attributes>`_, which don't say this explicitly, but testing confirms it.
    _book_server_path: str = str(
        Path(pkg_resources.resource_filename("bookserver", "")).absolute()
    )

    # The path to the Runestone application inside web2py.
    runestone_path: Path = Path(
        os.environ.get(
            "RUNESTONE_PATH",
            Path(_book_server_path).parents[1] / "web2py/applications/runestone",
        )
    ).resolve()

    # _`book_path`: specify the directory to serve books from. For now, default to serving from the same place as the Runestone server, since the server uses some of these files.
    book_path: Path = runestone_path / "books"

    # The path to store error logs.
    error_path: Path = Path.home() / "Runestone/errors"

    # Define the mode of operation for the webserver, taken from ``BookServerConfig```. This looks a bit odd, since the string value will be parsed by Pydantic into a Config.
    #
    # .. admonition:: warning
    #
    #    When using an Enum for a configuration setting you cannot compare against
    #    a string.  The value will actually be ``BookServerConfig.development``` or whatever.
    #    Our style will be to compare against the Enum not the ``.name`` attribute.
    #
    book_server_config: BookServerConfig = "development"  # type: ignore

    # Database setup: this must be an standard (synchronous) connection; for example:
    #
    # - ``sqlite:///./runestone.db``
    # - ``postgresql://postgres:bully@localhost/runestone``
    dburl: str = f"sqlite:///{_book_server_path}/runestone.db"
    dev_dburl: str = f"sqlite:///{_book_server_path}/runestone_dev.db"
    test_dburl: str = f"sqlite:///{_book_server_path}/runestone_test.db"

    # Given a sync database URI, return its async equivalent.
    @staticmethod
    def _sync_to_async_uri(sync_uri: str) -> str:
        return sync_uri.replace("sqlite://", "sqlite+aiosqlite://", 1).replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )

    # Determine the synchronous database URL based on the ``book_server_config`` and the dburls above.
    @property
    def _sync_database_url(self) -> str:
        return {
            "development": self.dev_dburl,
            "test": self.test_dburl,
            "production": self.dburl,
        }[self.book_server_config.value]

    # Return the async equivalent of the URI from ``sync_database_url``.
    @property
    def database_url(self) -> str:
        return self._sync_to_async_uri(self._sync_database_url)

    # Determine the database type from the URL.
    @property
    def database_type(self) -> DatabaseType:
        dburl = self.database_url
        if dburl.startswith("sqlite"):
            return DatabaseType.SQLite
        elif dburl.startswith("postgresql"):
            return DatabaseType.PostgreSQL
        else:
            raise RuntimeError(f"Unknown database type; URL is {dburl}.")

    # Setting db_echo to True makes for a LOT of sqlalchemy output - it gives you the SQL for every query!
    db_echo = False

    # The docker-compose.yml file will set the REDIS_URI environment variable
    redis_uri = "redis://localhost:6379/0"

    # Select normal mode or a high-stakes assessment mode (for administering a examination). In this mode, answers to supported question types are not shown.
    is_exam: bool = False

    # Configure ads. TODO: Link to the place in the Runestone Components where this is used.
    adsenseid: str = ""
    num_banners: int = 0
    serve_ad: bool = False

    # This is the secret key used for generating the JWT token.
    secret: str = "supersecret"

    # This is the private key web2py uses for hashing passwords.
    @property
    def web2py_private_key(self) -> str:
        # Put the cache here; above the def, it produces ``TypeError: unhashable type: 'Settings'``.
        @lru_cache
        def read_key():
            key_file = self.runestone_path / "private/auth.key"
            if key_file.exists():
                with open(key_file, encoding="utf-8") as f:
                    return f.read().strip()
            else:
                rslogger.error("No Key file is found will default to settings.secret")
                return self.secret

        return read_key()

    # if you want to reinitialize your database set this to ``Yes``.
    # All data in the database will be lost! This will only work for
    # development and test ``book_server_config`` settings.
    drop_tables: str = "No"


settings = Settings()
