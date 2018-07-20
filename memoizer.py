""" Module for loading parsed data from bitcointalk into PostgreSQL. """
import bitcointalk
import codecs
from datetime import datetime
import os
import pg
import time
import unittest
import logging
from tqdm import tqdm
from requests.exceptions import RequestException

memo = {
    'boards': set(),
    'members': set(),
    'topics': set()
}

logging.basicConfig(
    filename="output.log",
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p')

def _insertBoardPage(data):
    """Insert just the board."""
    del data['topic_ids']
    pg.insertBoard(data)


def _insertTopicPage(data):
    """Insert data as topic and messages and splice off messages."""
    pg.insertMessages(data.pop("messages"))
    pg.insertTopic(data)


entityFunctions = {
    'board': {
        'requestor': bitcointalk.requestBoardPage,
        'parser': bitcointalk.parseBoardPage,
        'inserter': _insertBoardPage,
        'selector': pg.selectBoard
    },
    'member': {
        'requestor': bitcointalk.requestProfile,
        'parser': bitcointalk.parseProfile,
        'inserter': pg.insertMember,
        'selector': pg.selectMember
    },
    'topic': {
        'requestor': bitcointalk.requestTopicPageAll,
        'parser': bitcointalk.parseTopicPage,
        'inserter': _insertTopicPage,
        'selector': pg.selectTopic
    }
}


def _saveToFile(html, fileType, fileDescriptor):
    """Save given entity to a file."""
    f = codecs.open("{0}/data/{1}_{2}_{3}.html".format(
        os.path.dirname(os.path.abspath(__file__)),
        fileType, fileDescriptor,
        int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds())),
        'w', 'utf-8')
    f.write(html)
    f.close()


def remember():
    """Remember what's already in the database to avoid re-scraping."""
    global memo
    cursor = pg.cursor()
    for key in memo.keys():
        cursor.execute("SELECT sid FROM {0}".format(pg.tables[key[:-1]]))
        rows = cursor.fetchall()
        for row in rows:
            memo[key].add(row[0])
    return True


def _scrape(entity, entityId):
    global memo
    global entityFunctions
    entityPlural = "{0}s".format(entity)
    if entityId in memo[entityPlural]:
        return entityFunctions[entity]['selector'](entityId)
    else:
        html = entityFunctions[entity]['requestor'](entityId)
        # _saveToFile(html, entity, entityId)
        datum = entityFunctions[entity]['parser'](html)
        entityFunctions[entity]['inserter'](datum)
        memo[entityPlural].add(entityId)
        return datum


def scrapeBoard(boardId):
    """Scrape information on the specified board."""
    print "Beginning scrape of board ID...".format(boardId)
    logging.info("Beginning scrape of board ID...".format(boardId))

    board = _scrape('board', boardId)
    count = board['num_pages']

    logging.info("Found {0} topic pages in board...".format(count))

    print "Getting data from {} pages equalling ~{} topics.".format(count, count*40)
        
    for i in tqdm(range(1, board['num_pages'] + 1), total=count):
        scrapeBoardPage(boardId, i)


def scrapeBoardPage(boardId, boardPageNum):
    logging.info(">Scraping page {0}...".format(boardPageNum))
    try:
        topicIDs = scrapeTopicIDs(boardId, boardPageNum)
    except RequestException as e:
        logging.exception(">>Could not request URL for board {0} at page {1},:".format(boardId, boardPageNum))
        return

    for topicID in tqdm(topicIDs, total=len(topicIDs)):
        logging.info(">>Starting scrape of topic ID {0}...".format(topicID))
        try:
            topic = scrapeTopic(topicID)
        except RequestException as e:
            logging.exception(">>Could not request URL for topic {0}:".format(topicID))
            continue

        numPages = topic['num_pages']

        logging.info(">>Found {0} message pages in topic...".format(
            numPages))
        # if the number of pages is less than 25 then they would have showed up in one page
        # and already been scraped. Otherwise it must be done page by page
        if numPages <= 25:
            continue
        else:
            for topicPageNum in range(1, numPages + 1):
                logging.info(">>>Scraping page {0}...".format(topicPageNum))
                try:
                    scrapeMessages(topicID, topicPageNum)
                except RequestException as e:
                    logging.exception(">>Could not request URL for topic {0} at page {1}:".format(topic['id'], topicPageNum))
                    continue

                logging.info(">>>Done with page {0}.".format(topicPageNum))
            logging.info(">>Done scraping topic ID {0}.".format(topicID))
    logging.info(">Done with page {0}.".format(boardPageNum))


def scrapeTopicIDs(boardId, pageNum):
    """Scrape topic IDs from a board page. Will not store values."""
    offset = (pageNum-1)*40
    html = bitcointalk.requestBoardPage(boardId, offset)
    # _saveToFile(html, "boardpage", "{0}.{1}".format(boardId, offset))
    data = bitcointalk.parseBoardPage(html)
    data = data['topic_ids']
    return data


def scrapeMember(memberId):
    """Scrape the profile of the specified member."""
    return _scrape('member', memberId)


def scrapeMessages(topicID, pageNum):
    """Scrape all messages on the specified topic, page combination."""
    """CAVEAT: Messages are not memoized."""
    offset = (pageNum-1)*20
    html = bitcointalk.requestTopicPage(topicID, offset)
    # _saveToFile(html, "topicpage", "{0}.{1}".format(topicId, offset))
    data = bitcointalk.parseTopicPage(html)
    data = data['messages']
    pg.insertMessages(data)
    return data


def scrapeTopic(topicID):
    """Scrape information on the specified topic."""
    html = bitcointalk.requestTopicPageAll(topicID)
    data = bitcointalk.parseTopicPage(html)
    messages = data.pop('messages')
    pg.insertMessages(messages)

    if topicID not in memo["topics"]:
        pg.insertTopic(data)
        memo.add(topicID)

    return data


class MemoizerTest(unittest.TestCase):

    """"Testing suite for memoizer module."""

    def setUp(self):
        """Setup tables and memo for test."""
        # Swap and sub tables
        self.tablesOriginal = pg.tables
        pg.tables = {}
        for key, table in self.tablesOriginal.iteritems():
            pg.tables[key] = "{0}_test".format(table)

        # Create test tables
        cur = pg.cursor()
        for key, table in pg.tables.iteritems():
            cur.execute("""CREATE TABLE IF NOT EXISTS
                {0} (LIKE {1} INCLUDING ALL)""".format(
                table, self.tablesOriginal[key]))
        cur.execute("""COMMIT""")

        # Reset memo
        global memo
        self.memoOriginal = memo
        memo = {
            'boards': set(),
            'members': set(),
            'topics': set()
        }

    def tearDown(self):
        """Teardown tables for test and restore memo."""
        # Drop test tables
        cur = pg.cursor()
        for table in pg.tables.values():
            cur.execute("""DROP TABLE IF EXISTS
                {0}""".format(table))
        cur.execute("""COMMIT""")

        # Undo swap / sub of tables
        pg.tables = self.tablesOriginal

        # Undo swap / sub of memo
        global memo
        memo = self.memoOriginal

    def testScrapeBoard(self):
        """Test scrapeBoard function."""
        countRequestedStart = bitcointalk.countRequested
        datumFirst = scrapeBoard(74)
        datumSecond = scrapeBoard(74)
        countRequestedEnd = bitcointalk.countRequested
        self.assertEqual(countRequestedEnd - countRequestedStart, 1)
        datumExpected = {
            'id': 74,
            'name': 'Legal',
            'container': 'Bitcoin',
            'parent': 1,
            'num_pages': 23
        }
        self.assertEqual(datumExpected, datumFirst)
        self.assertEqual(datumExpected, datumSecond)
        self.assertEqual(datumFirst, datumSecond)

    def testScrapeMember(self):
        """Test scrapeMember function."""
        countRequestedStart = bitcointalk.countRequested
        datumFirst = scrapeMember(12)
        datumSecond = scrapeMember(12)
        countRequestedEnd = bitcointalk.countRequested
        self.assertEqual(countRequestedEnd - countRequestedStart, 1)
        datumExpected = {
            'id': 12,
            'name': 'nanaimogold',
            'position': 'Sr. Member',
            'date_registered': datetime(2009, 12, 9, 19, 23, 55),
            'last_active': datetime(2014, 6, 3, 0, 38, 1),
            'email': 'hidden',
            'website_name': 'Nanaimo Gold Digital Currency Exchange',
            'website_link': 'https://www.nanaimogold.com/',
            'bitcoin_address': None,
            'other_contact_info': None,
            'signature': '<a href="https://www.nanaimogold.com/" ' +
            'target="_blank">https://www.nanaimogold.com/</a> ' +
            '- World\'s first bitcoin exchange service'
        }
        self.assertEqual(datumExpected, datumFirst)
        self.assertEqual(datumExpected, datumSecond)
        self.assertEqual(datumFirst, datumSecond)

    def testScrapeTopic(self):
        """Test scrapeTopic function."""
        countRequestedStart = bitcointalk.countRequested
        datumFirst = scrapeTopic(14)
        datumSecond = scrapeTopic(14)
        countRequestedEnd = bitcointalk.countRequested
        self.assertEqual(countRequestedEnd - countRequestedStart, 1)
        datumExpected = {
            'id': 14,
            'name': 'Break on the supply\'s increase',
            'board': 7,
            'num_pages': 1
        }
        self.assertEqual(datumFirst['count_read'], datumSecond['count_read'])
        self.assertEqual(datumFirst.pop('count_read') > 3057, True)
        self.assertEqual(datumSecond.pop('count_read') > 3057, True)
        self.assertEqual(datumExpected, datumFirst)
        self.assertEqual(datumExpected, datumSecond)
        self.assertEqual(datumFirst, datumSecond)

        # Make sure we can pull in the associated messages without error
        pg.selectMessages([53, 56])

    def testScrapeMessages(self):
        """Test scrapeMessages function."""
        countRequestedStart = bitcointalk.countRequested
        data = scrapeMessages(14, 1)
        countRequestedEnd = bitcointalk.countRequested
        self.assertEqual(countRequestedEnd - countRequestedStart, 1)
        self.assertEqual(len(data), 2)

        # Make sure we can pull in the associated messages without error
        pg.selectMessages([53, 56])

    def testRemember(self):
        """Test remember function."""
        scrapeBoard(74)
        scrapeMember(12)
        scrapeTopic(14)
        global memo
        memo = {
            'boards': set(),
            'members': set(),
            'topics': set()
        }
        remember()
        expectedMemo = {
            'boards': set([74]),
            'members': set([12]),
            'topics': set([14])
        }
        self.assertEqual(memo, expectedMemo)


if __name__ == "__main__":
    unittest.main()
