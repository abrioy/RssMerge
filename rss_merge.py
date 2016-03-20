import json
import re
import feedparser
import socket
import PyRSS2Gen
import pytz
import datetime
import sys
import argparse
import logging

now = pytz.UTC.localize(datetime.datetime.utcnow())
logger = logging.getLogger("RssMerge")

YOUTUBE_URL_CHANNEL = "https://www.youtube.com/feeds/videos.xml?channel_id=%s"
YOUTUBE_URL_PLAYLIST = "https://www.youtube.com/feeds/videos.xml?playlist_id=%s"

DEFAULTS = {
    "title": "Feed",
    "link": "",
    "summary": "RSSfeed",
    "size": 30,

    "feeds": {
        "name": "Feed",

        "type": "normal",
        "source": "",

        "size": 6,

        "prefix": "",
        "regex": {
            "pattern": None,
            "replace": None
        },
        "filter": None
    }
}

# Sets a timeout for feedparser
socket.setdefaulttimeout(15)


def fill_feeds_with_defaults(data, default):
    if isinstance(data, dict):
        for key in default:
            if key in data:
                fill_feeds_with_defaults(data[key], default[key])
            else:
                data[key] = default[key]

    elif isinstance(data, list):
        for i, val in enumerate(data):
            fill_feeds_with_defaults(data[i], default)


def open_feeds_database(database_path):
    with open(database_path, 'r') as dbFile:
        db = json.loads(dbFile.read())
        dbFile.close()
        if 'defaults' in db:
            fill_feeds_with_defaults(db, DEFAULTS)
            fill_feeds_with_defaults(db, db['defaults'])
        else:
            fill_feeds_with_defaults(db, DEFAULTS)

        return db


def create_feed(feed_info, out_stream):
    logger.info("Creating feed \"" + feed_info['title'] + "\".")

    feed = []
    for item_info in feed_info['feeds']:
        # Fusing the feed lists while keeping them sorted
        feed.extend(fetch_feed(item_info))

    # Sorting (to be sure)
    feed = sorted(feed, key=lambda k: k['published_parsed'], reverse=True)
    # Truncating
    del feed[feed_info['size']:]

    # Creating the feed
    rss_items = []
    for item in feed:
        rss_items.append(
            PyRSS2Gen.RSSItem(
                title=item['title'],
                link=item['link'],
                description=item['summary'],
                guid=PyRSS2Gen.Guid(item['link']),
                pubDate=item['published'],
            )
        )

    rss = PyRSS2Gen.RSS2(
        title=feed_info['title'],
        link=feed_info['link'],
        description=feed_info['summary'],
        lastBuildDate=now,
        items=rss_items
    )

    rss.write_xml(out_stream)


def fetch_feed(item_info):
    logger.info("\tFetching feed \"" + item_info['name'] + "\".")

    if item_info['type'] == 'youtube':
        source_url = YOUTUBE_URL_CHANNEL % item_info['source']
    elif item_info['type'] == 'youtube-playlist':
        source_url = YOUTUBE_URL_PLAYLIST % item_info['source']
    else:
        source_url = item_info['source']

    source = feedparser.parse(source_url, agent='Mozilla/5.0')
    if source.bozo and source.bozo != 0:
        if not source.feed:
            logger.error("Error with an RSS feed, no elements found: \"" + source_url + "\".\n" + source)
        else:
            logger.warning("There is an error with the feed: \"" + source_url + "\": " + str(source.bozo_exception))
    elif not source.feed:
        logger.warning("Feed is empty: \"" + source_url + "\".")
    feed = []

    i = 0
    for entry in source.entries:
        # Making sure the required fields are here
        fill_feeds_with_defaults(entry,
                                 {'title': "TITLE", 'link': "LINK", 'summary': "SUMMARY", 'media_description': None})

        # Special treatment for the summary in youtube feeds
        if 'youtube' in item_info['type']:
            entry['summary'] = '<h1>%s</h1>'  \
                               '<iframe id="ytplayer" type="text/html" width="640" height="390" ' \
                               'src="https://www.youtube.com/embed/%s"/>' \
                               % (entry['title'], re.sub(r'.*youtube.com/watch.*v=([^&]+)', r'\1', entry['link']))
            if entry['media_description']:
                entry['summary'] += '<p>' + entry['media_description'] + '</p>'

        # Pattern substitution on the title
        if item_info['regex']['pattern'] is not None and item_info['regex']['replace'] is not None:
            entry['title'] = re.sub(item_info['regex']['pattern'], item_info['regex']['replace'], entry['title'])

        # Filtering the titles
        if not (item_info['filter'] is not None and not re.match(item_info['filter'], entry['title'])):
            entry['title'] = item_info['prefix'] + entry['title']

            # Checking that there is time information in the feed
            if not (('published' in entry) and ('published_parsed' in entry) and
                    (entry['published'] is not None) and (entry['published_parsed'] is not None)):
                # Creating a phony date
                entry['published'] = datetime.datetime.fromtimestamp(1) + datetime.timedelta(
                    days=(len(source.entries) - i))
                entry['published_parsed'] = entry['published'].timetuple()
                logger.warning("Incorrect entry in \"" + item_info['name'] + "\": \"" + entry[
                    'title'] + "\" - no time data. Adding a phony date: " + str(entry['published']))

            feed.append(entry)
        i += 1

    # Sorting
    feed = sorted(feed, key=lambda k: k['published_parsed'], reverse=True)
    # Truncating
    del feed[item_info['size']:]

    return feed


if __name__ == "__main__":
    # Parsing arguments
    parser = argparse.ArgumentParser(description='Merge RSS feeds.')
    parser.add_argument(
        '--log', '-l', action='store', required=False,
        dest='logLevel', default='4',
        help='logging level (default=4): 0=off, 1=critical, 2=errors, 3=warnings, 4=info, 5=debug'
    )
    parser.add_argument(
        '--log-output', action='store', required=False,
        dest='logOutputFile', default=None,
        help='output file for the log'
    )
    parser.add_argument(
        '-o', '-output', action='store', required=False,
        dest='output', default=None,
        help='output rss file'
    )
    parser.add_argument(
        'feedsFilePath', metavar="feeds.json", action='store',
        help='name of the json file containing the feeds to parse'
    )
    args = parser.parse_args()

    # Logging
    if args.logOutputFile:
        handler = logging.FileHandler(args.logOutputFile)
    else:
        handler = logging.StreamHandler()

    formatter = logging.Formatter(
        '%(asctime)s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    levels = {
        '0': logging.NOTSET,
        '1': logging.CRITICAL,
        '2': logging.ERROR,
        '3': logging.WARNING,
        '4': logging.INFO,
        '5': logging.DEBUG
    }
    try:
        logger.setLevel(levels[args.logLevel])
    except KeyError:
        logger.setLevel(logging.INFO)
        logger.warning("Invalid logging level: " + args.logLevel)

    # Opening the db and creating the feeds
    feeds = None
    try:
        feeds = open_feeds_database(args.feedsFilePath)
    except IOError as e:
        logger.critical("Error while opening the input file \"%s\": %s" % (args.feedsFilePath, e))

    if feeds and args.output:
        with open(args.output, "wb") as output_stream:
            create_feed(feeds, output_stream)
    else:
        create_feed(feeds, sys.stdout)