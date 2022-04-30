import uuid
import time
import sys
import signal
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from collections import OrderedDict
from pymongo import MongoClient, results
from faker import Faker

# db_client = MongoClient('mongodb://localhost:27017')
db_client = MongoClient('mongodb://mongodb_1:27021,mongodb_2:27022,mongodb_3:27023', replicaSet='rs0', maxPoolSize=100)
time.sleep(1) # wait for replica set discovery
poc_db = db_client['poc']
profile_collection = poc_db['profile']

fake = Faker()

def insert_profile():
    profile_doc = {
        'profile_id': str(uuid.uuid4()),
        'first_name': fake.first_name(),
        'last_name': fake.last_name(),
        'phone_number': fake.phone_number(),
        'email': fake.email(),
        'address': fake.address(),
        'dob': datetime.combine(fake.date_of_birth(minimum_age=20, maximum_age=80), datetime.min.time()),
        'created_time': datetime.now(),
    }
    insert_result = profile_collection.insert_one(profile_doc)
    if isinstance(insert_result, results.InsertOneResult):
        print("Insert profile - {}".format(insert_result.inserted_id))
    else:
        print("Insert profile - {}".format(insert_result['_id']))

def update_profile():
    random_profile = pick_random_profile()
    if random_profile is None:
        return

    fields_to_set = {
        'phone_number': fake.phone_number(),
        'email': fake.email(),
        'address': fake.address(),
        'updated_time': datetime.now(),
    }
    profile_collection.update_one({"_id": random_profile['_id']}, {'$set': fields_to_set})
    print("Update profile - {}".format(random_profile['_id']))

def delete_profile():
    random_profile = pick_random_profile()
    if random_profile is None:
        return

    profile_collection.delete_one({"_id": random_profile['_id']})
    print("Delete profile - {}".format(random_profile['_id']))


action_switcher = {
    'I': insert_profile,
    'U': update_profile,
    'D': delete_profile,
}

def ensure_profile_index():
    profile_collection.create_index('profile_id', name='profile_id_1', background=True, unique=True)

def pick_random_profile():
    pipeline = [
        {"$sample": {'size': 10}}
    ]
    results = profile_collection.aggregate(pipeline)
    return fake.random_element(elements=results)

def fake_profile_task(action):
    action_hanlder = action_switcher.get(action, lambda: print('mismatch action handler'))
    action_hanlder()

def signal_handler(signal, frame):
    print('Quit profiles faking ...')
    executor.shutdown(True)
    sys.exit(0)

if __name__ == '__main__':
    ensure_profile_index()

    signal.signal(signal.SIGINT, signal_handler)

    global executor
    executor = ThreadPoolExecutor(max_workers=100)

    while True:
        action = fake.random_element(elements=OrderedDict([("I", 0.7), ("U", 0.25), ("D", 0.05)]))
        executor.submit(fake_profile_task, action)
        time.sleep(0.001)
