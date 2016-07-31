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
import fileUtils


# Configure logger globally
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def process(filename, config, title, desc):
    """Transcode the audio file if necessary, then add ID3 tags."""
    # Check that the file exists
    if not fileUtils.exists(filename):
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
    length = calcLength(filename)

    # Return the name of the processed audio file and the length
    return filename, length


def transcodeAudio(filename):
    """Convert the WAV to an MP3 using Lame."""
    logging.info("Transcoding to MP3...")

    # Check if the mp3 already exists
    fileroot, _ = os.path.splitext(filename)
    if fileUtils.exists(fileroot + ".mp3"):
        logger.fatal("\'" + fileroot + ".mp3\' already exists.")
        exit(1)

    # Transcode the mp3
    try:
        cmd = "lame -V2 -h  --quiet %s.wav %s.mp3" % (fileroot, fileroot)
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
    metaData["title"] = title
    metaData["artist"] = unicode(config["artist"])
    metaData["date"] = unicode(str(datetime.datetime.now().year))
    metaData["album"] = unicode(config["album"])
    metaData.save()


def addCoverArt(filename, config):
    """Add cover art."""
    # Create the image tag
    logger.info("Adding the Cover Image...")
    imageFilepath = config["imageFilepath"]
    _, imageFileExtension = os.path.splitext(imageFilepath)
    imageTag = APIC()

    # Determine the file type
    if imageFileExtension.lower() == ".png":
        imageTag.mime = 'image/png'
    elif imageFileExtension.lower() == ".jpg":
        imageTag.mime = 'image/jpeg'
    else:
        logger.fatal("Cover image must be a PNG or JPG.")
        exit(1)

    # Set the image tags
    imageTag.encoding = 3  # 3 is for utf-8
    imageTag.type = 3      # 3 is for cover image
    imageTag.desc = u'Cover'
    with open(imageFilepath, 'rb') as f:
        imageTag.data = f.read()

    # Add the tag using ID3
    try:
        mp3 = MP3(filename, ID3=ID3)
        mp3.tags.add(imageTag)
        mp3.save()
    except:
        raise


def calcLength(filename):
    """Calculate the length of the track in hours, mins, and secs."""
    try:
        mp3 = MP3(filename)
        hours, rem = divmod(mp3.info.length, 3600)
        mins, secs = divmod(rem, 60)
    except:
        raise

    # Return length as a tuple
    return (hours, mins, secs)