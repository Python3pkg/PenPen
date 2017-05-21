#!/usr/bin/env python
"""Tag and transcode audio files."""

# Standard modules
import datetime
import logging
import os
import subprocess


# Third party modules
import mutagen.id3
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
from mutagen.mp3 import MP3

# Custom modules
from . import fileUtils


# Configure logger globally
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def process(filename, config, title, desc):
    """Transcode the audio file if necessary, then add ID3 tags."""
    # Check that the file exists
    if not os.path.isfile(filename):
        logger.fatal("\'" + filename + "\' does not exist.")
        exit(1)

    # Check that the file is either a WAV or an MP3
    if not fileUtils.extValid(filename, '.WAV') and \
       not fileUtils.extValid(filename, '.MP3'):
        logger.fatal("The audio file must be a WAV or MP3.")
        exit(1)

    # If it's a WAV, then transcode it to MP3
    if fileUtils.extValid(filename, '.WAV'):
        filename = transcodeAudio(filename)

    # Add and calculate meta data
    addID3Tags(filename, config, title, desc)
    addCoverArt(filename, config)
    duration = calcDuration(filename)

    # Return the name of the processed audio file and the duration
    return filename, duration


def transcodeAudio(filename):
    """Convert the WAV to an MP3 using Lame."""
    logger.info("Transcoding to MP3...")

    # Check if LAME is installed
    lamePath = fileUtils.which("lame")

    if not lamePath:
        logger.fatal("LAME could not be found. Please make sure it is " +
                     "installed (brew install lame // apt-get install lame) " +
                     "and in the current PATH.")
        exit(1)

    # Check if the mp3 already exists. Using the absolute path so that the
    # subprocess call can be done with `shell=False` (for added security).
    fileroot, _ = os.path.splitext(os.path.abspath(filename))

    if fileUtils.os.path.isfile(fileroot + ".mp3"):
        logger.warning("\'" + fileroot + ".mp3\' already exists. " +
                       "Overwriting...")

    # Transcode the mp3
    try:
        # Since subprocess is called with `shell=false`, arguments can not be
        # passed in a string. Must pass in args as a list.
        cmd = [lamePath,
               '-V2',
               '-h',
               '--quiet',
               fileroot + ".wav",
               fileroot + ".mp3"]

        # Running with shell false for security.
        subprocess.call(cmd, shell=False)
    except:
        raise

    # Return the filename of the transcoded file.
    return fileroot + ".mp3"


def addID3Tags(filename, config, title, desc):
    """Add ID3 tags."""
    logger.info("Adding ID3 tags...")

    # Get reference to tags, add them if not found
    try:
        metaData = EasyID3(filename)
    except mutagen.id3.ID3NoHeaderError:
        metaData = MP3(filename, ID3=EasyID3)
        metaData.add_tags()

    # Set tags
    metaData['title'] = title
    metaData['artist'] = str(config['episodeAuthor'])
    metaData['date'] = str(str(datetime.datetime.now().year))
    metaData['album'] = str(config['rssTitle'])
    metaData.save()


def addCoverArt(filename, config):
    """Add cover art."""
    logger.info("Adding the Cover Image...")

    # Check that the file exists
    imageFilepath = config['episodeImageFilepath']

    if not os.path.isfile(imageFilepath):
        logger.fatal("\'" + imageFilepath + "\' does not exist.")
        exit(1)

    # Initialize the tag
    imageTag = APIC()

    # Determine the file type
    if fileUtils.extValid(imageFilepath.lower(), '.png'):
        imageTag.mime = 'image/png'
    elif fileUtils.extValid(imageFilepath.lower(), '.jpg'):
        imageTag.mime = 'image/jpeg'
    else:
        logger.fatal("Cover image must be a PNG or JPG.")
        exit(1)

    # Set the image tags
    imageTag.encoding = 3  # 3 is for utf-8
    imageTag.type = 3      # 3 is for cover image
    imageTag.desc = 'Cover'

    with open(imageFilepath, 'rb') as f:
        imageTag.data = f.read()

    # Add the tag using ID3
    try:
        mp3 = MP3(filename, ID3=ID3)
        mp3.tags.add(imageTag)
        mp3.save()
    except:
        raise


def calcDuration(filename):
    """Calculate the duration of the track in hours, mins, and secs."""
    try:
        mp3 = MP3(filename)
        hours, rem = divmod(mp3.info.length, 3600)
        mins, secs = divmod(rem, 60)
    except:
        raise

    # Return duration as a tuple
    return (hours, mins, secs)
