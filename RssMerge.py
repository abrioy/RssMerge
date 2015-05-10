import json
import time
import re
import feedparser
import PyRSS2Gen
import pytz
import datetime
now = pytz.UTC.localize(datetime.datetime.now());
import traceback
import codecs
import sys

settings = {};


def main(argv):
	global settings

	try:
		databasePath = argv[1];
	except:
		print("The path of the json input must be passed as an argument.");
		return;
	db = openDB(databasePath)
	settings = db['settings'];
	for item in db['data']:
		try:
			createFeed(item);
		except:
			print('>>> traceback <<<')
			traceback.print_exc()
			print('>>> end of traceback <<<')



def fillWithDefault(data, default):
	if isinstance(data, dict):
		for key in default:
			if key in data:
				fillWithDefault(data[key], default[key]);
			else:
				data[key] = default[key];

	elif isinstance(data, list):
		for i,val in enumerate(data):
			fillWithDefault(data[i], default);



def openDB(databasePath):
	dbFile = open(databasePath,'r');
	db = json.loads(dbFile.read());
	dbFile.close();
	fillWithDefault(db['data'], db['defaults']),

	return db



def createFeed(feedInfos):
	global settings

	print("Creating feed \""+feedInfos['title']+"\".");

	feed = [];
	for itemInfos in feedInfos['feeds']:
		# Fusing the feed lists while keeping them sorted
		try:
			feed.extend(fetchFeed(itemInfos));
		except:
			print( '>>> traceback <<<')
			traceback.print_exc()
			print('>>> end of traceback <<<')

	# Sorting (to be sure)
	feed = sorted(feed, key=lambda k: k['published_parsed'], reverse=True) ;
	# Truncating
	del feed[feedInfos['size']:];

	# Creating the feed
	rssItems = [];
	for item in feed:
		rssItems.append(
			PyRSS2Gen.RSSItem(
				title = item['title'],
				link = item['link'],
				description = item['summary'],
				guid = PyRSS2Gen.Guid(item['link']),
				pubDate = item['published'],
			)
		);

	rss = PyRSS2Gen.RSS2(
		title = feedInfos['title'],
		link = feedInfos['link'],
		description = feedInfos['summary'],
		lastBuildDate = now,
		items = rssItems
	);

	rss = rss.to_xml("utf-8");

	feedFile = codecs.open(settings['OUTPUT_DIRECTORY'] + feedInfos['filename'] , "w", "utf-8");
	feedFile.write(rss);
	feedFile.close();


def fetchFeed(itemInfos):
	global settings

	print("\tFetching feed \""+itemInfos['name']+"\".");

	if itemInfos['type'] == 'youtube':
		sourceURL = settings['YOUTUBE_URL_CHANNEL'] + itemInfos['source'];
	elif itemInfos['type'] == 'youtube-playlist':
		sourceURL = settings['YOUTUBE_URL_PLAYLIST'] + itemInfos['source'];
	else:
		sourceURL = itemInfos['source'];

	source = feedparser.parse(sourceURL);
	if source.entries == []:
		print("X\t\t> RSS feed not found: \""+sourceURL+"\".");
	feed = []

	for entry in source.entries:
		# Making sure the required fields are here
		fillWithDefault(entry, {'title': "TITLE", 'link': "LINK", 'summary': "SUMMARY"});
		
		# Pattern substitution on the title
		if (itemInfos['regex']['pattern'] != None and itemInfos['regex']['replace'] != None):
			entry['title'] = re.sub(itemInfos['regex']['pattern'], itemInfos['regex']['replace'], entry['title']);
		
		# Filtering the titles
		if not (itemInfos['filter'] != None and not re.match(itemInfos['filter'], entry['title'])):
			entry['title'] = itemInfos['prefix'] + entry['title']
			
			# Checking that there is time information in the feed
			if (('published' in entry) and ('published_parsed' in entry) and
				(entry['published'] != None) and (entry['published_parsed'] != None)):
				feed.append(entry);
			else:
				print("\t\t> Discarded entry \""+entry['title']+"\": no time data.")
	

	# Sorting
	feed = sorted(feed, key=lambda k: k['published_parsed'], reverse=True) ;
	# Truncating
	del feed[itemInfos['size']:];

	return feed;


if __name__ == "__main__":
   main(sys.argv)