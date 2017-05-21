#!/usr/bin/env python
"""Encode audio podcast episodes and add them to the RSS feed."""

import argparse
import logging
import os

from . import audio
from . import rss

# Configure logger globally
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def parseArgs():
    """Parse the command line arguments."""
    # Define the parser
    parser = argparse.ArgumentParser(description='Transcode, tag, and upload \
                                     podcast episodes.')
    parser.add_argument('-c', '--config', required=True,
                        help='Configuration file with the feed parameters.')
    parser.add_argument('-t', '--title', type=str, required=False,
                        help='Title of the episode.')
    parser.add_argument('-d', '--description', type=str, required=False,
                        help='Description of the episode.')
    parser.add_argument('audioFile', help='WAV or MP3 file to be added to the \
                        feed. WAV files will be transcoded to 128 Kbps MP3s.')

    # Returns a namespace containing the parsed arguments
    return parser.parse_args()


def validateTextField(fieldName, field):
    """Validate a text field. Prompt if empty."""
    # Get the title if it wasn't passed in on the command line.
    if not field:
        field = str(input("Enter the episode " + fieldName.lower() +
                                  ": "))

        # Check that something was entered, enforcing a non-empty title
        if not field:
            logging.fatal("\'" + fieldName + "\' must be supplied.")
            exit(1)

    return field


def parseConfigFile(configFile):
    """Parse the configuration file."""
    # Read in the config file
    if not os.path.isfile(configFile):
        logger.fatal("\'" + configFile + "\' does not exist.")
        exit(1)

    with open(configFile) as f:
        contents = f.readlines()

    # Load the contents into a dictionary
    config = dict()

    for line in contents:
        # Each line should have a single parameter delimited by "=".
        # Skip if the line is only whitespace.
        if line.isspace():
            continue

        # Skip if the line if it is a comment (starts with "#")
        if line[0] == "#":
            continue

        # Split on the "=" delimiter
        fields = line.split('=', 1)
        if len(fields) < 2:
            logger.warning("\'" + fields[0] + "\' has not been specified.")

        # Assign the key value pair and strip whitespace
        key = fields[0].lstrip().rstrip()
        value = fields[1].lstrip().rstrip()

        # Strip doubles quotes from the value if it has it
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]

        config[key] = value

    return config


def main():
    """Main function."""
    # Parse arguments and load parameters
    args = parseArgs()
    config = parseConfigFile(args.config)
    title = validateTextField('Title', args.title)
    desc = validateTextField('Description', args.description)

    # Transcode and tag the audio
    mp3File, duration = audio.process(args.audioFile, config, title, desc)

    # Add to the RSS feed
    rss.addEpisode(config, title, desc, mp3File, duration)


if __name__ == "__main__":
    main()
