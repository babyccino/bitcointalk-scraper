""" Core scraper for bitcointalk.org. """
import bitcointalk
import pg
import logging
import memoizer
import os
import sys
import time
import traceback
import multiprocessing
from multiprocessing import Pool, freeze_support
from tqdm import tqdm
import argparse
from forumlist import *

if __name__ == '__main__':
    logging.basicConfig(
        filename="output.log",
        level=logging.INFO,
        format='%(asctime)s %(levelname)s:%(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p')

    parser = argparse.ArgumentParser(description='Scrape bitcointalk.org')
    parser.add_argument('--boards', nargs='+', dest="boards", help='Set the forum boards you want to collect from', required=True)
    args = parser.parse_args()

    freeze_support()
    # Make sure we don't rescrape information already in the DB
    memoizer.remember()

    for board in args.boards:
        memoizer.scrapeBoard(forumIDs[board])

    logging.info("Made {0} requests in total.".format(bitcointalk.countRequested))

