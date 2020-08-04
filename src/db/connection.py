from pymongo import MongoClient

client = MongoClient('localhost', 27017)

db = client['abt']

question_coll = db['question']
results_coll = db['results']
on_coll = db['is_on']
attempt_coll = db['attempt']
