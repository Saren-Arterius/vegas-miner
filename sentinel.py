#!/usr/bin/env python3
from pyquery import PyQuery as pq
from urllib.request import urlopen
from os.path import join, dirname, realpath
from time import sleep, time
from subprocess import Popen, call
import pyscreenshot as ImageGrab
import logging

CHECK_URL = 'http://127.0.0.1:8080/h'
SCRIPT_PATH = realpath(dirname(__file__))
SCREENSHOTS_PATH = join(SCRIPT_PATH, 'screenshots')
HR_THRESHOLD = 15500
ERROR_COUNT_THRESHOLD = 5
DROP_COUNT_THRESHOLD = 20

WAIT_DELAY_SECOND = 200
CHECK_INTERVAL_SECOND = 5

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M:%S',
                    filename=join(SCRIPT_PATH, 'sentinel.log'),
                    filemode='w')
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

def take_screenshot():
    logger = logging.getLogger('sentinel.screenshot')
    logger.info('Taking screenshot')
    for i in range(10):
        try:
            im = ImageGrab.grab()
            im.save(join(SCREENSHOTS_PATH, '{}.png'.format(round(time()))))
            logger.info('Done')
            return True
        except Exception as e:
            logger.error('ERROR:' + str(e))
            logger.info('Retrying...')
            sleep(CHECK_INTERVAL_SECOND)
    logger.warn('Fail to take screenshot')
    return False


def check_health():
    logger = logging.getLogger('sentinel.miner-checker')
    error_count = 0
    drop_count = 0
    while True:
        try:
            doc = pq(urlopen(CHECK_URL, timeout=5).read().decode())
            hr60s = doc.find(
                'body > div > div.data > table > tr:nth-child(18) > td:nth-child(3)').text().strip()
            hr60s = float(hr60s)
            logger.info('60s hash rate = {}/s'.format(hr60s))
            logger.debug(doc.find('body > div > div.data > table').html())
            error_count = 0
            if hr60s <= HR_THRESHOLD:
                logger.warn(
                    '60s hash rate ({}/s) less then threshold! ({}/s)'.format(hr60s, HR_THRESHOLD))
                drop_count += 1
            else:
                drop_count = 0
        except Exception as e:
            logger.error('ERROR: ' + str(e))
            error_count += 1
        if error_count >= ERROR_COUNT_THRESHOLD:
            logger.warn('Miner is down')
            take_screenshot()
            return False
        if drop_count >= DROP_COUNT_THRESHOLD:
            logger.warn('Miner has dropped hashrate')
            take_screenshot()
            return False
        sleep(CHECK_INTERVAL_SECOND)


def restart_miner():
    logger = logging.getLogger('sentinel.miner-restarter')
    call(['taskkill', '/IM', 'xmr-stak.exe', '/T', '/F'])
    proc = Popen([join(SCRIPT_PATH, 'start.bat')])
    logger.info('Waiting {}s for miner to initialize...'.format(WAIT_DELAY_SECOND))
    sleep(WAIT_DELAY_SECOND)
    """
    epl = 0
    for i in range(WAIT_DELAY_SECOND):
        logger.debug('{}/{}'.format(epl, WAIT_DELAY_SECOND))
        sleep(1)
        epl += 1
    """


if __name__ == '__main__':
    take_screenshot()
    restart_miner()
    while True:
        check_health()
        restart_miner()
