# simple script to make random signatures for testing
:
import sys
import random
import json

# usage: python make_random_signatures.py <stride> <start: "[x,y,z]"> <finish: "[x,y,z]">
stride_size = int(sys.argv[1])
bbox_start = json.loads(sys.argv[2])
bbox_finish = json.loads(sys.argv[3])

# python make_random_signatures.py 50 "[0, 0, 1000]" "[29000, 21000, 26000]"

fout = open("signatures.b", 'wb')

# how many duplicates to allow per signature
duplicates = 4

zs = (bbox_finish[2] - bbox_start[2]) // stride_size
ys = (bbox_finish[1] - bbox_start[1]) // stride_size
xs = (bbox_finish[0] - bbox_start[0]) // stride_size

# max value
num_vals = (zs * ys * xs) // duplicates
incr = sys.maxsize // num_vals 

for z in range(bbox_start[2], bbox_finish[2], stride_size):
    for y in range(bbox_start[1], bbox_finish[1], stride_size):
        for x in range(bbox_start[0], bbox_finish[0], stride_size):
            # write location
            fout.write(x.to_bytes(4, byteorder='little'))
            fout.write(y.to_bytes(4, byteorder='little'))
            fout.write(z.to_bytes(4, byteorder='little'))
            
            # write sig
            sig = random.randint(0, num_vals) * incr
            fout.write(sig.to_bytes(8, byteorder='little'))

fout.close()
