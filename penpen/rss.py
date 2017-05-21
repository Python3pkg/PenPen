#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Create RSS feeds and append items."""

import datetime
import logging
import os
import re
import shutil
import xml.dom.minidom

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from . import fileUtils

# Configure logger globally
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def generateXml(config, newEpisode):
    """Generate the XML for the RSS feed."""
    # Register namespaces
    namespaces = {'itunes': "http://www.itunes.com/dtds/podcast-1.0.dtd",
                  'atom': "http://www.w3.org/2005/Atom"}

    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)

    # Initialize the root node
    rss = ET.Element("rss", version="2.0")
    chan = ET.SubElement(rss, 'channel')

    # Get old episodes, the first year of publishing (for building the
    # copyright string), and set RSS attributes
    oldEpisodes, firstYear = getOldEpisodes(config, rss, chan, namespaces)

    # Add feed elements
    addSubElementFromConfig(chan, 'title', config, 'rssTitle')
    addSubElementFromConfig(chan, 'link', config, 'websiteLink')
    addSubElementFromConfig(chan, 'language', config, 'language')
    addSubElementFromConfig(chan, 'itunes:subtitle', config, 'rssSubtitle')
    addSubElementFromConfig(chan, 'itunes:author', config, 'rssAuthor')
    addSubElementFromConfig(chan, 'description', config, 'rssDescription')
    addSubElementFromConfig(chan, 'itunes:summary', config, 'rssDescription')
    addSubElementFromConfig(chan, 'itunes:explicit', config, 'itunesExplicit')
    addSubElementFromConfig(chan, 'itunes:keywords', config, 'itunesKeywords')
    addSubElementFromConfig(chan, 'managingEditor', config, 'managingEditor')

    # Copyright
    addSubElement(chan, 'copyright', generateCopyrightStr(config, firstYear))

    # Atom link
    xmlFilepath = config['xmlFilepath']
    rssLink = generateLink(config['rssDir'], os.path.basename(xmlFilepath))
    ET.SubElement(chan,
                  'atom:link',
                  href=rssLink,
                  rel="self",
                  type="application/rss+xml")

    # iTunes rss owner
    owner = ET.SubElement(chan, 'itunes:owner')
    name = ET.SubElement(owner, 'itunes:name')
    name.text = config['rssAuthor']
    email = ET.SubElement(owner, 'itunes:email')
    email.text = config['managingEditor']

    # rss image
    rssImage = config['rssImage']

    if (fileUtils.extValid(rssImage, '.png') or
            fileUtils.extValid(rssImage, '.jpg')):
        ET.SubElement(chan, 'itunes:image', href=config['rssImage'])
    else:
        logger.error('RSS image must be a PNG or JPG.')

    # Shameless self promotion
    addSubElement(chan, 'generator', 'PenPen: Audio Podcasting Suite')

    # RSS category
    ET.SubElement(chan, 'itunes:category', text=config['itunesCategory'])

    # Last build date
    addSubElement(chan, 'lastBuildDate', getFormattedUtcTime())

    # Add the episode
    chan.append(newEpisode)

    # Copy old episodes back into the RSS feed and set the attributes
    if oldEpisodes:
        chan.extend(oldEpisodes)

    # Save it out
    writeXmlFile(config, rss)


def addEpisode(config, title, desc, mp3File, duration):
    """Add an episode to the RSS feed."""
    logger.info("Adding episode to the RSS feed...")

    # Create the item for the new episode
    item = ET.Element('item')

    # Add the sub elements from the config file
    addSubElementFromConfig(item, 'itunes:author', config, 'episodeAuthor')
    # addSubElementFromConfig(item, 'itunes:subtitle', config)
    addSubElementFromConfig(item, 'itunes:explicit', config, 'episodeExplicit')
    addSubElementFromConfig(item, 'itunes:image', config, 'episodeImage')

    # Add the remaining sub elements
    addSubElement(item, 'title', title)
    addSubElement(item, 'description', desc)
    addSubElement(item, 'itunes:summary', desc)
    addSubElement(item, 'pubDate', getFormattedUtcTime())

    # Format the duration
    durationStr = "%0.f:%02.f:%02.f" % duration
    addSubElement(item, 'itunes:duration', durationStr)

    # Create the public link to the episode
    episodeDir = config['episodeDir']
    if not episodeDir.endswith('/'):
        episodeDir += "/"

    episodeLink = generateLink(config['episodeDir'], os.path.basename(mp3File))

    addSubElement(item, 'guid', episodeLink)

    # Create the enclosure tag
    byteLength = os.path.getsize(mp3File)
    ET.SubElement(item, 'enclosure',
                  url=episodeLink,
                  length=str(byteLength),
                  type="audio/mpeg3")

    # Now generate the XML
    generateXml(config, item)


def getOldEpisodes(config, rss, chan, namespaces):
    """Copy old episodes into the new RSS feed and set the attributes."""
    # Indicates items are to be added. Needed to know whether or not to
    # manually add namespaces. Yes, it is wonky. A side effect of the way
    # ElementTree adds namespaces.
    itemsAdded = False
    # Return value for the old episode elements which can be empty
    # if no old episodes exist
    items = None
    # Return value for the first year of publication as indicated by the
    # `pubDate` on the earliest episode. Used for generating the copyright
    # string. Can be empty if no old episodes exist.
    firstYear = None

    xmlFilepath = config['xmlFilepath']

    if os.path.isfile(xmlFilepath):
        # Load and strip the XML
        with open(xmlFilepath, 'r') as f:
            xmlStr = ''
            for line in f:
                # strip leading and trailing whitespace so minidom can prettify
                # without adding extraenous new lines
                xmlStr += line.lstrip().rstrip()

        # Parse the XML
        rssPrev = ET.ElementTree()

        try:
            rssPrev = ET.ElementTree(ET.fromstring(xmlStr))
        except:
            logger.fatal("Unable to parse \'" + xmlFilepath + "\'")
            exit(1)

        # Find all the items and append them to the new tree
        items = rssPrev.getroot().findall('channel/item', namespaces)

        # Append found items and add appropriate namespaces
        if items:
            # Indicate items are to be added
            itemsAdded = True

            # Items do not carry an Atom namespace element, so add it manually
            rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")

        # Find the earliest `lastBuildDate` to determine copyright
        pubDates = rssPrev.getroot().findall('channel/item/pubDate',
                                             namespaces)

        for pubDate in pubDates:
            # Parse out the year
            year = re.findall(r" \d{4} ", pubDate.text)[0].lstrip().rstrip()

            # Set the year if empty or lower
            if not firstYear:
                firstYear = year
            else:
                if int(year) < int(firstYear):
                    firstYear = year

    # No items were added, then add all namespace attributes manually.
    if not itemsAdded:
        for prefix, uri in namespaces.items():
            rss.set("xmlns:" + prefix, uri)

    return items, firstYear


def writeXmlFile(config, rss):
    """Write the XML file to disk."""
    # Create a backup first
    xmlBackupFilepath = createBackup(config)

    # Overwrite the file
    xmlFilepath = config['xmlFilepath']
    try:
        with open(xmlFilepath, 'w') as f:
            f.write(prettifyXml(rss))
    except:
        # Delete the generated file
        try:
            os.remove(xmlFilepath)
        except:
            logger.warning("Could not remove the generated file \`" +
                           xmlFilepath + "\`")

        # If a backup exists, restore the original file
        if os.path.isfile(xmlBackupFilepath):
            try:
                shutil.copy(xmlBackupFilepath, xmlFilepath)
            except:
                logger.error("XML write and backup restore both failed.")
                raise

            logger.error("XML write failed. Backup has been restored.")
        else:
            logger.error("XML write failed. No backups to restore.")

        raise

    logger.info("Saved new XML => " + config['xmlFilepath'])


def createBackup(config):
    """Create a backup of the XML file.

    Return the location of the backup file so that we can restore it upon
    a write failure.
    """
    xmlFilepath = config['xmlFilepath']

    # Only make a backup if an XML already exists
    if os.path.isfile(xmlFilepath):
        # Create the XML backup directory if it doesn't already exist
        backupDir = config["rssBackupDir"]

        try:
            os.makedirs(backupDir)
        except OSError:
            if not os.path.isdir(backupDir):
                raise

        # Construct the copy destination filename
        timeStr = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        base = os.path.basename(xmlFilepath)

        xmlBackupFilepath = "%s/%s_%s.xml" % (backupDir,
                                              os.path.splitext(base)[0],
                                              timeStr)

        try:
            shutil.copy(xmlFilepath, xmlBackupFilepath)
            logger.info("Creating backup XML => " + xmlBackupFilepath)
        except:
            raise

        return xmlBackupFilepath
    else:
        # Return an empty string that will fail `os.path.isfile()`
        return ''


def prettifyXml(elem):
    """Return a pretty-printed XML string for the Element.

    Minidom also serves as our validator since it will throw an error if
    the string is not well formed.
    """
    uglyStr = ET.tostring(elem, 'utf-8')
    reparsedStr = xml.dom.minidom.parseString(uglyStr)
    return reparsedStr.toprettyxml(indent="  ", encoding="utf-8")


def addSubElement(element, tag, value):
    """Add a subelement to the ElementTree."""
    child = ET.SubElement(element, tag)
    child.text = value


def addSubElementFromConfig(element, tag, config, key):
    """Add a subelement to the ElementTree with a value from the conf file."""
    value = config[key]

    if value:
        addSubElement(element, tag, value)
    else:
        logger.warning("Key \'" + key + "\' was not found in the conf file.")


def generateLink(folder, filename):
    """Generate a web link from a folder and a filename."""
    if not folder.endswith('/'):
        folder += "/"

    return folder + os.path.basename(filename)


def generateCopyrightStr(config, firstYear):
    """Generate a copyright notice with the year of the earliest episode."""
    copyrightStr = ""
    thisYear = str(datetime.date.today().year)

    if not firstYear or firstYear == thisYear:
        copyrightStr = "©" + thisYear + " " + \
                       config['rssAuthor'] + ". All rights reserved."
    else:
        copyrightStr = "©" + firstYear + "—" + thisYear + " " + \
                       config['rssAuthor'] + ". All rights reserved."

    return str(copyrightStr, 'utf-8')


def getFormattedUtcTime():
    """Get the current time in UTC formatted to the XML specification."""
    # Formatting must conform to RFC 822 (Section 5.1). Notably, UTC is
    # abbreviated UT, because the world has not suffered enough.
    timeStr = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S")
    return timeStr + " UT"
