""" Core scraper for bitcointalk.org. """
import bitcointalk
import logging
import memoizer
import os
import sys
import traceback
import multiprocessing
from multiprocessing import Pool, freeze_support
from tqdm import tqdm

boardId = 1

def scrapeBoardPage(boardPageNum):
    logging.info(">Scraping page {0}...".format(boardPageNum))
    topicIds = memoizer.scrapeTopicIds(boardId, boardPageNum)
    for topicId in topicIds:
        logging.info(">>Starting scrape of topic ID {0}...".format(topicId))
        try:
            topic = memoizer.scrapeTopic(topicId)
        except Exception as e:
            logging.info(">>Could not request URL for topic {0}:".format(
                topicId))
            print e
            continue
        logging.info(">>Found {0} message pages in topic...".format(
            topic['num_pages']))
        # if the number of pages is less than 25 then they would have showed up in one page
        # and already been scraped. Otherwise it must be done page by page
        if topic['num_pages'] <= 25:
            continue
        else:
            for topicPageNum in range(1, topic['num_pages'] + 1):
                logging.info(">>>Scraping page {0}...".format(topicPageNum))
                messages = memoizer.scrapeMessages(topic['id'], topicPageNum)
                for message in messages:
                    if message['member'] > 0:
                        memoizer.scrapeMember(message['member'])
                logging.info(">>>Done with page {0}.".format(topicPageNum))
            logging.info(">>Done scraping topic ID {0}.".format(topicId))
    logging.info(">Done with page {0}.".format(boardPageNum))

if __name__ == '__main__':
    logging.basicConfig(
        filename="output.log",
        level=logging.INFO,
        format='%(asctime)s %(levelname)s:%(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p')

    freeze_support()
    # Make sure we don't rescrape information already in the DB
    memoizer.remember()

    print "Beginning scrape of board ID...".format(boardId)
    logging.info("Beginning scrape of board ID...".format(boardId))
    board = memoizer.scrapeBoard(boardId)
    logging.info("Found {0} topic pages in board...".format(board['num_pages']))

    count = board['num_pages']
    cpuCount = multiprocessing.cpu_count()
    r1 = range(1, count+1)

    print "Getting data from {} pages equalling ~{} topics.".format(count, count*40)
    print "Executing on {} threads".format(cpuCount)
    logging.info("Executing on {} threads".format(cpuCount))
        
    pool = Pool(processes=cpuCount)
    for _ in tqdm(pool.imap_unordered(scrapeBoardPage, range(1, board['num_pages'] + 1)), total=count):
        pass
    pool.close()

    logging.info("Made {0} requests in total.".format(bitcointalk.countRequested))

