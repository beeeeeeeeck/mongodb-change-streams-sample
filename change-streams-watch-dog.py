import time
import sys
import signal
from pymongo import MongoClient, errors

db_client = MongoClient('mongodb://mongodb_1:27021,mongodb_2:27022,mongodb_3:27023', replicaSet='rs0')
time.sleep(1) # wait for replica set discovery
poc_db = db_client['poc']

WATCHED_COLLECTION_NAME = 'profile'
profile_collection = poc_db[WATCHED_COLLECTION_NAME]
watch_point_collection = poc_db['watch_point']
profile_compact_collection = poc_db['profile_compact']

def sync_2_profile_compact_4_insert_operation(id, document):
    profile_compact_doc = {
        'ref_id': id,
        'profile_id': document['profile_id'],
        'first_name': document['first_name'],
        'last_name': document['last_name'],
        'phone_number': document['phone_number'],
        'email': document['email'],
    }
    profile_compact_collection.insert_one(profile_compact_doc)

def sync_2_profile_compact_4_update_operation(id, document):
    if document is None:
        return # possibly the document was already deleted

    fields_to_set = {
        'ref_id': id,
        'profile_id': document['profile_id'],
        'first_name': document['first_name'],
        'last_name': document['last_name'],
        'phone_number': document['phone_number'],
        'email': document['email'],
    }
    profile_compact_collection.update_one({"ref_id": id}, {'$set': fields_to_set}, upsert=True)

def sync_2_profile_compact_4_delete_operation(id, document):
    profile_compact_collection.delete_one({"ref_id": id})

action_switcher = {
    'insert': sync_2_profile_compact_4_insert_operation,
    'update': sync_2_profile_compact_4_update_operation,
    'delete': sync_2_profile_compact_4_delete_operation,
}

def change_event_handler(event):
    # print("Handling {}".format(event))
    operationType = event['operationType']
    if operationType is None:
        print("Operation is empty")
        return

    doc_id = event['documentKey']['_id']
    print("Handling {} for action - {}".format(doc_id, operationType))
    action_hanlder = action_switcher.get(operationType, lambda: print('mismatch action handler'))
    action_hanlder(doc_id, event['fullDocument'] if 'fullDocument' in event else None)
    mark_watch_point(event['_id'])

def mark_watch_point(resume_token):
    # print("Mark watch point {}".format(resume_token))
    watch_point_collection.find_one_and_update({'collection_name': WATCHED_COLLECTION_NAME}, {'$set': {'resume_token': resume_token}})

def retrieve_watch_point():
    watch_point = watch_point_collection.find_one({'collection_name': WATCHED_COLLECTION_NAME})
    if watch_point is None:
        watch_point_collection.insert_one({'collection_name': WATCHED_COLLECTION_NAME})
        return None

    if 'resume_token' in watch_point and '_data' in watch_point['resume_token']:
        return watch_point['resume_token']

    return None

def ensure_profile_index():
    profile_compact_collection.create_index('ref_id', name='ref_id_1', background=True, unique=True)
    profile_compact_collection.create_index('profile_id', name='profile_id_1', background=True, unique=True)

def signal_handler(signal, frame):
    print('Quit change streams watch dog ...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    ensure_profile_index()
    watch_point = retrieve_watch_point()
    try:
        with profile_collection.watch(full_document='updateLookup', resume_after=watch_point) as change_stream:
            for change_event in change_stream:
                change_event_handler(change_event)
    except errors.PyMongoError:
        # The ChangeStream encountered an unrecoverable error or the
        # resume attempt failed to recreate the cursor.
        print('err')