#!/usr/bin/env python3
from pyquery import PyQuery as pq
from urllib.request import urlopen
from os.path import join, dirname, realpath
from subprocess import Popen, call
from json import load, dump
from time import sleep, time
from sys import argv
import re

CHECK_URL = 'http://127.0.0.1:8080/h'
SCRIPT_PATH = realpath(dirname(__file__))
DB_PATH = join(SCRIPT_PATH, 'optimizer-db.json')
MINER_THREADS_PATH = join(SCRIPT_PATH, 'xmr-stak', 'amd.txt')
ODNT_PATH = join(SCRIPT_PATH, 'OverdriveN', 'OverdriveNTool.ini')

START_GPU_MV, START_MEM_CLK = 895, 1150
MAX_GPU_MV, MIN_MEM_CLK = 995, 900
GPU_MV_STEP, MEM_CLK_STEP = 10, 25

STATE_INCRESING_GPU_MV = 1
STATE_DECREASING_MEM_CLK = 2
STATE_INCRESING_GPU_MV_2ND = 3


class OptimizingWorker():
    def __init__(self, idx, optimizer, check_only=False):
        self.idx = idx
        self.optimizer = optimizer
        self.check_only = check_only
        if self.idx not in self.optimizer.db:
            self.optimizer.db[self.idx] = {}

    def calc_next_mv_clk(self):
        if 'progress' not in self.optimizer.db[self.idx]:
            self.optimizer.db[self.idx]['progress'] = {
                'state': STATE_INCRESING_GPU_MV,
                'gpu_mv': START_GPU_MV,
                'mem_clk': START_MEM_CLK
            }
        progress = self.optimizer.db[self.idx]['progress']

        if progress['state'] == STATE_INCRESING_GPU_MV:
            progress['gpu_mv'] += GPU_MV_STEP
            if progress['gpu_mv'] > MAX_GPU_MV:
                progress['state'] = STATE_DECREASING_MEM_CLK
                progress['gpu_mv'] = MAX_GPU_MV

        if progress['state'] == STATE_DECREASING_MEM_CLK:
            progress['mem_clk'] -= MEM_CLK_STEP
            if progress['mem_clk'] < MIN_MEM_CLK:
                progress['mem_clk'] = MIN_MEM_CLK
                raise Exception('mem clk getting too low')

        if progress['state'] == STATE_INCRESING_GPU_MV_2ND:
            progress['gpu_mv'] += GPU_MV_STEP
            if progress['gpu_mv'] > MAX_GPU_MV:
                progress['gpu_mv'] = MAX_GPU_MV
                raise Exception('GPU mV getting too high')

    def update_miner_threads(self):
        with open(MINER_THREADS_PATH, 'r') as f:
            content = f.readlines()
        content[39] = re.sub(
            '"index" : \d+', '"index" : {}'.format(self.idx), content[39])
        content[40] = re.sub(
            '"index" : \d+', '"index" : {}'.format(self.idx), content[40])
        with open(MINER_THREADS_PATH, 'w+') as f:
            f.writelines(content)

    def update_mv_clk(self):
        with open(ODNT_PATH, 'r', encoding='utf-16') as f:
            content = f.read()
        content = re.sub('GPU_P6=1212;\d+', 'GPU_P6=1212;{}'.format(
            self.optimizer.db[self.idx]['progress']['gpu_mv'] - 5), content)
        content = re.sub('GPU_P7=1408;\d+', 'GPU_P7=1408;{}'.format(
            self.optimizer.db[self.idx]['progress']['gpu_mv']), content)
        content = re.sub('Mem_P3=\d+;900', 'Mem_P3={};900'.format(
            self.optimizer.db[self.idx]['progress']['mem_clk']), content)
        with open(ODNT_PATH, 'w+', encoding='utf-16') as f:
            f.write(content)

    def check_stable(self):
        proc = Popen([join(SCRIPT_PATH, 'exec-miner.bat')])
        print('Waiting for miner to initialize...')
        sleep(40)
        check_until = time() + 1800
        error_count = 0
        while True:
            try:
                doc = pq(urlopen(CHECK_URL, timeout=5).read().decode())
                hr10s = doc.find(
                    'body > div > div.data > table > tr:nth-child(2) > td:nth-child(2)').text().strip()
                print(
                    '10s hash rate = {}/s, time to left = {}s'.format(float(hr10s), check_until - time()))
                sleep(1)
                if time() >= check_until:
                    print('Health check succeed')
                    call(['taskkill', '/IM', 'xmr-stak.exe', '/T', '/F'])
                    return True
            except Exception as e:
                print('ERROR', e)
                error_count += 1
                if error_count >= 5:
                    print('Health check failed because of too many errors')
                    call(['taskkill', '/IM', 'xmr-stak.exe', '/T', '/F'])
                    return False
                sleep(1)

    def run(self):
        self.update_miner_threads()
        if self.check_only:
            self.update_mv_clk()
            print(self.idx, self.optimizer.db[self.idx]['progress'])
            call([join(SCRIPT_PATH, 'apply-oc.bat')])
            stable = self.check_stable()
            if stable:
                print('Card {} is stable.'.format(self.idx))
            else:
                print('Card {} is NOT stable!'.format(self.idx))
            return
        stable = False
        while not stable:
            try:
                self.calc_next_mv_clk()
            except Exception as e:
                self.optimizer.db[self.idx]['result'] = {
                    'error': str(e)
                }
                self.optimizer.save_db()
                return
            self.update_mv_clk()
            print(self.idx, self.optimizer.db[self.idx]['progress'])
            call([join(SCRIPT_PATH, 'apply-oc.bat')])
            stable = self.check_stable()
            if stable:
                self.optimizer.db[self.idx]['result'] = self.optimizer.db[self.idx]['progress']
            self.optimizer.save_db()


class VegaOptimizer():

    def __init__(self):
        try:
            self.db = load(open(DB_PATH))
        except:
            print('Creating DB')
            self.db = {}
            self.save_db()

    def save_db(self):
        dump(self.db, open(DB_PATH, 'w'))

    def optimize_card(self, i):
        if i in self.db and 'result' in self.db[i]:
            print('Card {} already optimized.'.format(i))
            return
        print('Optimizing card {}...'.format(i))
        worker = OptimizingWorker(i, self)
        worker.run()

    def check_card(self, i):
        if i in self.db and 'progress' in self.db[i]:
            print('Checking card {}...'.format(i))
            worker = OptimizingWorker(i, self, True)
            worker.run()
            return
        print('Skipping card {}'.format(i))


if __name__ == '__main__':
    vo = VegaOptimizer()
    for i in range(6, 8):
        if 'check' in argv:
            vo.check_card(str(i))
        else:
            vo.optimize_card(str(i))
