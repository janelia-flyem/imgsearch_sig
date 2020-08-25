import os
import json


from google.cloud import storage
from google.cloud import bigquery

# constants for signature search
SIG_BUCKET = os.environ["SIG_BUCKET"]
SIG_CACHE = None # dataset to meta data caache for signature image search
SIG_DATASET_SUFFIX = "_imgsearch"
MAX_DISTANCE = 100 # 100 pixels (TODO: make dynamic) 


# helper function for getting sig/xyz for x,y,z
def fetch_signature(dataset, x, y, z):
    global SIG_CACHE
    storage_client = storage.Client()
    bucket = storage_client.bucket(SIG_BUCKET)

    # fetch metaadata
    meta = None
    if SIG_CACHE is not None and dataset in SIG_CACHE:
        meta = SIG_CACHE[dataset]
    else:
        blob = bucket.blob(dataset + "/info.json") 
        try:
            meta = json.loads(blob.download_as_string())
            if SIG_CACHE is None:
                SIG_CACHE = {}
            SIG_CACHE[dataset] = meta
        except Exception as e:
            print(e)
            raise Exception("dataset not found")

    block_size = meta["block_size"]

    # TODO: get stride information from info and predict perfect coordinate or design sampling
    # so block boundaries do not contain samples
    xb = x // block_size
    yb = y // block_size
    zb = z // block_size

    closest_dist = 999999999999
    closest_point = [0, 0, 0]
    closest_sig = 0

    def distance(pt):
        return (((x-pt[0])**2 + (y-pt[1])**2 + (z-pt[2])**2)**(0.5))
    
    # grab block and find closest match
    try:
        RECORD_SIZE = 20 # 20 bytes per x,y,z,signature
        blob = bucket.blob(dataset + f"/blocks/{xb}_{yb}_{zb}")
        blockbin = blob.download_as_string()
        records = len(blockbin) // RECORD_SIZE

        for record in range(records):
            start = record*RECORD_SIZE
            xt = int.from_bytes(blockbin[start:(start+4)], "little")
            start += 4
            yt = int.from_bytes(blockbin[start:(start+4)], "little")
            start += 4
            zt = int.from_bytes(blockbin[start:(start+4)], "little")
            start += 4
            dist = distance((xt,yt,zt))
            if dist <= MAX_DISTANCE and dist < closest_dist:
                closest_dist = dist
                closest_point = [xt,yt,zt]
                #print(int.from_bytes(blockbin[start:(start+8)], "little"))
                #closest_sig = int.from_bytes(blockbin[start:(start+8)], "little") - 2**64 # make signed int
                closest_sig = int.from_bytes(blockbin[start:(start+8)], "little", signed=True) # make signed int
        if closest_dist > MAX_DISTANCE:
            raise Exception("point not found")
    except Exception:
        raise Exception("point not found")

    return closest_point, closest_sig

def murmur64(h):
    h ^= h >> 33
    h *= 0xff51afd7ed558ccd
    h &= 0xFFFFFFFFFFFFFFFF 
    h ^= h >> 33
    h *= 0xc4ceb9fe1a85ec53
    h &= 0xFFFFFFFFFFFFFFFF 
    h ^= h >> 33
    return h

# find the closest signatures by hamming distance
def find_similar_signatures(dataset, x, y, z):
    # don't catch error if there is one
    point, signature = fetch_signature(dataset, x, y, z)
    meta = SIG_CACHE[dataset]    
    PARTITIONS = 4000

    # find partitions for the signature
    part0 = murmur64(int(meta["ham_0"]) & signature) % PARTITIONS
    part1 = murmur64(int(meta["ham_1"]) & signature) % PARTITIONS
    part2 = murmur64(int(meta["ham_2"]) & signature) % PARTITIONS
    part3 = murmur64(int(meta["ham_3"]) & signature) % PARTITIONS
   
    """
    part0 = murmur64(signature) % PARTITIONS
    part1 = murmur64(signature) % PARTITIONS
    part2 = murmur64(signature) % PARTITIONS
    part3 = murmur64(signature) % PARTITIONS
    """

    max_ham = 8

    SQL = f"SELECT signature, BIT_COUNT(signature^{signature}) AS hamming, x, y, z FROM `{dataset}{SIG_DATASET_SUFFIX}.hamming0`\nWHERE part={part0} AND BIT_COUNT(signature^{signature}) < {max_ham}\nUNION DISTINCT\n"
    SQL += f"SELECT signature, BIT_COUNT(signature^{signature}) AS hamming, x, y, z FROM `{dataset}{SIG_DATASET_SUFFIX}.hamming1`\nWHERE part={part1} AND BIT_COUNT(signature^{signature}) < {max_ham}\nUNION DISTINCT\n"
    SQL += f"SELECT signature, BIT_COUNT(signature^{signature}) AS hamming, x, y, z FROM `{dataset}{SIG_DATASET_SUFFIX}.hamming2`\nWHERE part={part2} AND BIT_COUNT(signature^{signature}) < {max_ham}\nUNION DISTINCT\n"
    SQL += f"SELECT signature, BIT_COUNT(signature^{signature}) AS hamming, x, y, z FROM `{dataset}{SIG_DATASET_SUFFIX}.hamming3`\nWHERE part={part3} AND BIT_COUNT(signature^{signature}) < {max_ham}\n"
    SQL += f"ORDER BY BIT_COUNT(signature^{signature}), rand()\nLIMIT 200" 

    client = bigquery.Client()

    query_job = client.query(SQL)
    results = query_job.result()
    
    def distance(pt):
        return (((x-pt[0])**2 + (y-pt[1])**2 + (z-pt[2])**2)**(0.5))

    pruned_results = []
    for row in results:
        # load results
        if distance((row.x, row.y, row.z)) > MAX_DISTANCE: 
            pruned_results.append({"point": [row.x, row.y, row.z], "dist": row.hamming, "score": (1.0-row.hamming/max_ham)})
    
    return pruned_results

""" Implement in toplevel clio

def getSignature(roles, dataset, point):
    if "clio_general" not in roles:
        abort(403)

    try:
        pt, sig = fetch_signature(dataset, *point)
        res = {"point": pt, "signature": str(sig)}
    except Exception as e:
        res = {"messsage": str(e)}
    return json.dumps(res)

def getMatches(roles, dataset, point):
    if "clio_general" not in roles:
        abort(403)

    try:
        data = fetch_similar_signatures(dataset, *point)
        res = {"matches": data}
        if len(data) == 0:
            res["message"] = "no matches"
    except Exception as e:
        res = {"messsage": str(e)}
    return json.dumps(res)

# TODO: function for calling thumbnail -- I could just relay the call for now

    elif urlparts[0] == "signatures" and len(urlparts) == 3 and urlparts[1] == "atlocation":
        dataset = urlparts[2]
        # not necessary for a GET request
        x = request.args.get('x')
        y = request.args.get('y')
        z = request.args.get('z')
        resp = getSignature(roles, dataset, (x,y,z))
    elif urlparts[0] == "signatures" and len(urlparts) == 3 and urlparts[1] == "likelocation":
        dataset = urlparts[2]
        # not necessary for a GET request
        x = request.args.get('x')
        y = request.args.get('y')
        z = request.args.get('z')
        resp = getMatches(roles, dataset, (x,y,z))
"""

#print(fetch_signature("mb20", 18416,16369,26467)) 
#print(fetch_signature("mb20", 24683, 15887, 16976)) 
#print(find_similar_signatures("mb20", 18416,16369,26467))
print(find_similar_signatures("mb20", 24683, 15887, 16976))



