import os
import time
import traceback

import tqdm as tqdm
from solidity_parser import parse_file
from multiprocessing import Pool, Manager
from visit import ASTVisitor
import pandas as pd

TRAIN_DATA_PATH = './contracts'


def travel(result, path, counter, lock):
    try:
        try:
            ast = parse_file(path)
        except TypeError:
            return
        result.extend(ASTVisitor.run(ast).get_result())
        with lock:
            counter.value += 1
    except Exception:
        traceback.print_exc()


def daemon(total, counter):
    pbar = tqdm.tqdm(total=total)
    last_len = 0
    while True:
        length = counter.value
        pbar.update(length - last_len)
        if length >= total:
            break
        last_len = length
        time.sleep(2)
    pbar.close()


if __name__ == '__main__':
    manager = Manager()
    rs = manager.list()
    contracts = list(os.scandir(TRAIN_DATA_PATH))
    cnt = manager.Value('i', 0)
    lck = manager.Lock()

    pool = Pool(processes=8)
    pool.apply_async(daemon, (len(contracts), cnt))
    for f in contracts:
        pool.apply_async(travel, (rs, f.path, cnt, lck))

    pool.close()
    pool.join()

    df = pd.DataFrame(list(rs))
    df.to_csv('result.csv')
