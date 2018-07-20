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

if __name__ == '__main__':
    logging.basicConfig(
        filename="output.log",
        level=logging.INFO,
        format='%(asctime)s %(levelname)s:%(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p')

    freeze_support()
    # Make sure we don't rescrape information already in the DB
    memoizer.remember()

    boardId = 1

    memoizer.scrapeBoard(boardId)

    logging.info("Made {0} requests in total.".format(bitcointalk.countRequested))

