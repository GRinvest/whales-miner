import numpy as np
import pyopencl as cl
import pyopencl.tools
import pyopencl.array
import base64
import hashlib
import time
import os, sys, inspect
import requests
import threading
import logging
import json
import hashlib
import traceback
import queue
from client import PoolClient
from sha256 import SHA256
from hdata import get_hdata, get_hdata_prefixed

mf = cl.mem_flags
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('pyopencl').setLevel(logging.FATAL)
start_time = time.time()

# Config
batchSize = 512 * 64
repeats = 1
internal_iterations = 500000
threads = 1
double_ring = False
wallet = sys.argv[1] if len(sys.argv) >= 2 else None
pool_addr = sys.argv[2] if len(sys.argv) >= 3 else 'https://server1.whalestonpool.com'
APP_VERSION = '1.1.4' # keep in sync with hive config

def check_wallet(pool_address, wallet):
    try:
        res = requests.get(f'{pool_address}/wallet/{wallet}').json()
    except:
        print('Connection error. Check pool address.')
        sys.exit(0)
    if not res['registered']:
        print("- whales miner version " + APP_VERSION)
        print(">")
        print("> To use miner you should register via @WhalesPoolBot")
        print(">")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

check_wallet(pool_addr, wallet)

# Resolve unique id
if os.path.isfile('state.json'):
    with open('state.json', 'r') as json_file:
        data = json.load(json_file)
else:
    with open('state.json', 'w') as json_file:
        json.dump({'wallet': wallet}, json_file)



pool_client = PoolClient(pool_addr, wallet)
if not wallet:
    print('Invalid wallet.')
    sys.exit(1)

logger.info("Starting miner...")
logger.info("Pool address: " + pool_addr)
logger.info("Wallet: " + wallet)

# Mining config
def load_config():
    while True:
        try:
            task = pool_client.load_next_task()
            task['lock'] = threading.Lock()
            task['offset'] = 0
            return task
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.warn("Config load error")
            time.sleep(5)
            continue

def get_kernel_config(params):
    hdata = get_hdata_prefixed(params['wallet'], params['prefix'], params['expire'], params['seed'])
    hash = SHA256()
    hash.update(bytes(hdata[:64]))
    head = np.fromiter(hash.h, np.uint32)
    tail = hdata[64:]
    complexity = np.frombuffer(params['complexity'], np.uint8)
    return (head, tail, complexity, params['expire'], params['seed'], params['giver'])
    

def validate(config, random, value):
    m = hashlib.sha256()
    m.update(get_hdata(config['wallet'], random, config['expire'], config['seed']).tobytes())
    if m.digest().hex() != value.hex():
        return False
    else:
        return True

def apply_speed(src, value):
    src.append(value)
    if len(src) > 5:
        del src[0]

def resolve_speed(src):
    if len(src) == 0:
        return 0
    res = 0
    for i in range(0, len(src)):
        res = res + src[i]
    res = res / len(src)
    return res


reportQueue = queue.Queue()
def report(wallet, giver, random, expire, seed):
    global shipId
    global shipName
    while True:
        try:
            solution = { 'giver': giver, 'input': get_hdata(wallet, random, expire, seed).tobytes().hex()  }
            pool_client.report_solution(solution)
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.warn("Reporting error")
            time.sleep(5)
            continue
        break
def reportQueueJob():
    while True:
        try:
            item = reportQueue.get()
            report(item['wallet'], item['giver'], item['random'], item['expire'], item['seed'])
            reportQueue.task_done()
        except Exception as e:
            logging.warn(traceback.format_exc())
            logging.warn("Monitoring error")
            time.sleep(5)
            continue
def startReportQueue():
    threading.Thread(target=reportQueueJob).start()

def postReport(wallet, giver, random, expire, seed):
    reportQueue.put({'wallet': wallet, 'giver': giver, 'random': random, 'expire': expire, 'seed': seed})

# Code
platforms = cl.get_platforms()
devices = []
for p in cl.get_platforms():
    devices = devices + p.get_devices()
ctx = cl.Context(devices)
src = ''
# with open(os.path.join(os.path.dirname(__file__),"kernels/sha256_util.cl"), "r") as rf:
#     src += rf.read()
# src += '\n'    
# with open(os.path.join(os.path.dirname(__file__),"kernels/sha256_impl.cl"), "r") as rf:
#     src += rf.read()    
# src += '\n'
# with open(os.path.join(os.path.dirname(__file__),"kernels/miner.cl"), "r") as rf:
#     src += rf.read()
with open(os.path.join(os.path.dirname(__file__),"opencl_sha256.cl"), "r") as rf:
    src += rf.read()

program = cl.Program(ctx, src).build()
sha256_kernel = program.hash_main

queue = []
for i in range(0, len(devices)):
    queue.append(cl.CommandQueue(ctx, devices[i]))
def compare(a, b):
    i = 0
    while (i < 32):
        if (a[i] != b[i]):
            if a[i] < b[i]:
                return -1
            else:
                return 1
        i += 1
    return 0


#
# Config
#

logging.info("Loading initial config...")
latest_config = load_config()
logging.info("Config loaded")

def config_refresh_job():
    global latest_config
    latest_config = load_config()

#
# Mining
#

mined = 0
mined_dev = {}
rate = 0
speed_average = []
speed_average_dev = {}
def miner_job(index, deviceId):
    global mined
    global mined_dev
    global repeats
    global latest_config
    global speed_average
    
    config = latest_config
    start = time.time()
    # logging.info("[" + str(index) + "/"+str(deviceId)+"]: Job started")
    # random = os.urandom(32)
    random = bytes(np.random.bytes(32))
    data = get_hdata(config['wallet'], random, config['expire'], config['seed'])
    m = SHA256()
    m.update(bytes(data[0:64]))
    initial_vector = np.fromiter(m._h, np.uint32)

    tail = data[64:]
    tail = np.pad(tail, (0, 64 - len(tail)))
    head_g = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=initial_vector)
    tail_g = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=tail)
    complexity_g = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=np.frombuffer(config['complexity'], dtype=np.uint8))

    output_1 = np.zeros(32, dtype=np.uint8)
    output_1_random = np.zeros(32, dtype=np.uint8)
    output_2 = np.zeros(32, dtype=np.uint8)
    output_2_random = np.zeros(32, dtype=np.uint8)
    res = None
    res_random = None
    cl_output_1 = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY | cl.mem_flags.COPY_HOST_PTR, output_1.nbytes, hostbuf=output_1)
    cl_output_1_random = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY | cl.mem_flags.COPY_HOST_PTR, output_1_random.nbytes, hostbuf=output_1_random)
    cl_output_2 = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY | cl.mem_flags.COPY_HOST_PTR, output_2.nbytes, hostbuf=output_2)
    cl_output_2_random = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY | cl.mem_flags.COPY_HOST_PTR, output_2_random.nbytes, hostbuf=output_2_random)
    found = False
    for i in range(0, repeats):
        # print("[" + str(index) +"/"+str(deviceId)+ "]: Iteration " + str(i))
        
        
        # Assign offset
        config['lock'].acquire()
        offset = config['offset']
        config['offset'] += internal_iterations * batchSize
        config['lock'].release()

        params = np.fromiter([offset, internal_iterations], np.uint64)
        params_g = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=params)
        
        event1 = sha256_kernel(queue[deviceId], (batchSize,), None,
            head_g,
            tail_g,
            params_g,
            complexity_g,
            cl_output_1_random,
            cl_output_1,
        )
        
        # event1.wait()
        # elapsed = 1e-9*(event1.profile.end - event1.profile.start)
        # logging.info("[" + str(index) + "/"+str(deviceId)+"]: Elapsed  " + str(elapsed))
        if double_ring:

            # Assign offset
            config['lock'].acquire()
            offset = config['offset']
            config['offset'] += internal_iterations * batchSize
            config['lock'].release()

            params = np.fromiter([offset, internal_iterations], np.uint64)
            params_g2 = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=params)

            event2 = sha256_kernel(queue[deviceId], (batchSize,), None, 
                head_g,
                tail_g,
                params_g2,
                complexity_g,
                cl_output_2_random,
                cl_output_2,
            )
        wait_start = time.time()
        # event1.wait()
        # logging.info("[" + str(index) + "/"+str(deviceId)+"]: Waited (1) " + str(( time.time() - wait_start)))
        # wait_start = time.time()
        read1 = cl.enqueue_copy(queue[deviceId], output_1, cl_output_1, is_blocking=False)
        read2 = cl.enqueue_copy(queue[deviceId], output_1_random, cl_output_1_random, is_blocking=False)
        queue[deviceId].flush()

        while read1.get_info(cl.event_info.COMMAND_EXECUTION_STATUS) != cl.command_execution_status.COMPLETE or read2.get_info(cl.event_info.COMMAND_EXECUTION_STATUS) != cl.command_execution_status.COMPLETE:
            time.sleep(0.05)
        
        mined += internal_iterations * batchSize
        mined_dev[str(deviceId)] = mined_dev.get(str(deviceId),0) + internal_iterations * batchSize
        logging.info("[" + str(index) + "/"+str(deviceId)+"]: Processed in " + str(( time.time() - wait_start)))

        if double_ring:
            wait_start = time.time()
            event2.wait()
            # logging.info("[" + str(index) + "/"+str(deviceId)+"]: Waited (2) " + str(( time.time() - wait_start)))
            wait_start = time.time()
            read1 = cl.enqueue_copy(queue[deviceId], output_2, cl_output_2)
            read2 = cl.enqueue_copy(queue[deviceId], output_2_random, cl_output_2_random)
            queue[deviceId].flush()

            while read1.get_info(cl.event_info.COMMAND_EXECUTION_STATUS) != cl.command_execution_status.COMPLETE or read2.get_info(cl.event_info.COMMAND_EXECUTION_STATUS) != cl.command_execution_status.COMPLETE:
                time.sleep(0.05)
            # logging.info("[" + str(index) + "/"+str(deviceId)+"]: Read (2) " + str(( time.time() - wait_start)))
            mined += internal_iterations * batchSize
            mined_dev[str(deviceId)] = mined_dev.get(str(deviceId),0) + internal_iterations * batchSize
    
        res = config['complexity']
        if np.sum(output_1) > 0 and np.sum(output_1_random) > 0:
            if compare(output_1.tobytes(), res) < 0:
                found = True
                res = output_1.tobytes()
                res_random = output_1_random.tobytes()
        if double_ring:
            if np.sum(output_2) > 0 and np.sum(output_2_random) > 0 and compare(output_2.tobytes(), res) < 0:
                found = True
                res = output_2.tobytes()
                res_random = output_2_random.tobytes()
#        if found_new:
#            print("[" + str(index) +"/"+str(deviceId)+ "]: Intermediate result: " + res.hex())
    params_g.release()
    tail_g.release()
    head_g.release()
    complexity_g.release()
    cl_output_1.release()
    cl_output_1_random.release()
    cl_output_2.release()
    cl_output_2_random.release()
    if found:
        logging.info("[" + str(index) +"/"+str(deviceId)+ "]: Job result: " + res.hex())
        if not validate(config, res_random, res):
            logging.info("[" + str(index) +"/"+str(deviceId)+ "]: Invalid job result")
        else:
            postReport(config['wallet'], config['giver'], res_random, config['expire'], config['seed'])
    else:
        logging.debug("[" + str(index) +"/"+str(deviceId)+ "]: Job not found valid share")
    # logging.info("[" + str(index) +"/"+str(deviceId)+ "]: Job ended")

def buildHash(data):
    m = hashlib.sha256()
    m.update(data)
    return m.digest()

def miner_thread(index, deviceId):
    logging.info("[" + str(index) + "/"+str(deviceId)+"]: Thread started")
    while True:
        try:
            miner_job(index, deviceId)
        except:
            logging.warn(traceback.format_exc())
            logging.info("[" + str(index) + "/"+str(deviceId)+"]: Miner error")
            time.sleep(5)
            continue
        
def start_miner_thread(index, deviceId):
    threading.Thread(target=miner_thread, args=(index,deviceId)).start()

def miner_config_thread():
    while True:
        time.sleep(1)
        try:
            config_refresh_job()
            # logging.info("Config updated")
        except Exception as e:
            logging.warn(traceback.format_exc())
            logging.warn("Config error")
            time.sleep(20)
            continue
def start_miner_config_thread():
    threading.Thread(target=miner_config_thread).start()

def miner_mon(count):
    global mined
    global mined_dev
    global rate
    global speed_average
    global speed_average_dev

    # Start Timer
    start = time.time()

    # Reset mined state
    mined = 0
    for i in range(0, count):
        mined_dev[str(i)] = 0
        speed_average_dev[str(i)] = []
    
    while True:
        time.sleep(10)
        try:

            # Resolve time
            time_delta = time.time() - start
            start = time.time()

            # Resolve speed
            delta = mined / (time_delta * 1000 * 1000)
            mined = 0

            # Update average speed
            apply_speed(speed_average, delta)
            total_average = resolve_speed(speed_average)
            rate = total_average

            # Calculate thread speed
            rates = []
            for i in range(0, count):

                # Resolve speed
                dev_delta = mined_dev.get(str(i), 0) / (time_delta * 1000 * 1000)
                mined_dev[str(i)] = 0

                # Update average speed
                apply_speed(speed_average_dev[str(i)], dev_delta)
                rates.append(resolve_speed(speed_average_dev[str(i)]))

            # Logging
            logging.info("Performance " + str(total_average) + " MH/s")          

            # Persisting
            with open('stats.json', 'w') as json_file:
                json.dump({
                    'total': total_average * 1000, # in khs
                    'rates': rates,
                    'uptime': time.time() - start_time
                }, json_file)
        except Exception as e:
            logging.warn(traceback.format_exc())
            logging.warn("Monitoring error")
            time.sleep(5)
            continue

def start_miner_mon(count):
    threading.Thread(target=miner_mon, args=(count,)).start()

#
# Start
#

# Start monitoring
start_miner_mon(len(devices))

# Start config loader
start_miner_config_thread()

# Start reporting queue
startReportQueue()

# Start miners
for i in range(0, len(devices)):
    for t in range(0, threads):
        start_miner_thread(i * threads + t, i)

logger.info("Miner started")