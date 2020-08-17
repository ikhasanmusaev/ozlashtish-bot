from pymongo import MongoClient

client = MongoClient('localhost', 27017)

db = client['abt']

question_coll = db['question']
results_coll = db['results']
attempt_coll = db['attempt']
users_coll = db['users']
