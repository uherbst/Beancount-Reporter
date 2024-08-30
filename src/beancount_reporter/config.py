"""Config class for beancount_reporter."""

import sys
from dataclasses import dataclass
from argparse import ArgumentParser
import logging
import importlib.metadata
import os

# We use toml as configuration language
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class Config:
    """Class with all config settings."""

    def __init__(self):
        """Set config values from config-file, env, command line, ..."""
        # Default Values for some parameters
        defaults = {
            # just an example....
            # Timeout to wait for any REST-call (Cloud API, SEMP)
            "rest_timeout": 10,
            #
        }

        # Which parameters are required to be set by user ?
        # (obviously these list is only for parameters WITHOUT
        # default values)
        self.required = [
            "BEANCOUNT_FILE",
        ]

        # Which parameters could be set via ENV ?
        self.from_env = ["debug", "BEANCOUNT_FILE"]

        self.version = importlib.metadata.version("Beancount-Reporter")

        args = self.read_cmdline()
        self.debug = args.debug
        self.config_file = args.file
        self.max_loops = args.n

        self.logger = self.setup_custom_logger("BeancountReporter")

        # Order of relevance:
        # Default Values (Lowest)
        # Env Variables
        # Config File
        # Command Line (Highest)

        # Not every option has to be configurable on each level...

        # Step 1: Set real values from default values.
        for key, value in defaults.items():
            setattr(self, key, value)

        # Step 2: Read from env
        self.read_config_from_env()

        # Step 3: Read from config file
        self.read_config_from_file(self.config_file)

        # Step 4: Options from CMD line
        for key, value in vars(args).items():
            # Maybe we need to filter out some items
            if key == "file":
                continue
            setattr(self, key, value)

        # Step 5: Check, if all required parameters are set
        self.check_required_config()

    def read_cmdline(self):
        """Handle command line arguments for SolaceMonitorMessageAge."""
        parser = ArgumentParser(
            description="BeancountReporter.py: create your own beancount reports"
        )

        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            help="Turn on debug output",
        )

        parser.add_argument(
            "-f",
            "--file",
            type=str,
            required=True,
            help="Required config file",
        )

        return parser.parse_args()

    def setup_custom_logger(self, name):
        """Set up customized logging."""
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        if self.debug:
            logger.setLevel(logging.DEBUG)

        # No file logging needed for now
        # Uncomment the following 3 lines, if needed
        # handler = logging.FileHandler('log.txt', mode='w')
        # handler.setFormatter(formatter)
        # logger.addHandler(handler)

        # Logging to stdout enabled
        # Comment the following 3 lines, if not needed
        screen_handler = logging.StreamHandler(stream=sys.stdout)
        screen_handler.setFormatter(formatter)
        logger.addHandler(screen_handler)

        return logger

    def read_config_from_file(self, file):
        """Read config file."""
        try:
            with open(file, "rb") as f:
                content = tomllib.load(f)
        except Exception as ex:
            self.logger.error(f"Can't read config file {file}:")
            self.config_filelogger.error(ex)
            exit()

        # Now, we need to traverse content and put them into attributs
        # of this class
        # FIXME:
        if content is not None:
            for key, value in content.items():
                setattr(self, key.lower(), value)

    def read_config_from_env(self):
        """Read config from ENVIRONMENT"""
        for parameter in self.from_env:
            if os.environ.get(parameter):
                setattr(self, parameter, os.environ.get(parameter))

    def check_required_config(self):
        """Check, if all required parameters are available"""
        for parameter in self.required:
            if not hasattr(self, parameter):
                self.logger.error(f"Required config parameter {parameter} not found!")
