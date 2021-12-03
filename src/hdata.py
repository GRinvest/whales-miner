import numpy as np
import struct
import base64


def get_hdata(wallet, rdata, expire, seed):
    wallet = base64.urlsafe_b64decode(wallet)

    hdata = np.zeros(123, np.uint8)
    hdata[0] = 0x00
    hdata[1] = 0xf2
    hdata[2:6] = np.frombuffer(b'\x4d\x69\x6e\x65', np.uint8)
    hdata[6] = (wallet[1] * 4) & 0xFF
    for i, b in enumerate(struct.pack('>I', expire)):
        hdata[i+7] = b
        for i in range(32):
            hdata[i + 11] = wallet[i+2]

    hdata[91:91+32] = hdata[43:43+32] = np.frombuffer(rdata, np.uint8)
        
    seed = np.frombuffer(seed, np.uint8)
    hdata[75:75 + 16] = seed
    return hdata

def get_hdata_prefixed(wallet, prefix, expire, seed):
    return get_hdata(wallet, np.pad(np.fromiter(prefix, np.uint8), (0, 32 - len(prefix))), expire, seed)