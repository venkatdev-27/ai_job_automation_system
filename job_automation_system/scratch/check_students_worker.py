#!/usr/bin/env python3
import sys
sys.path.insert(0, '/app')
from database.client import get_database

db = get_database()
students = list(db.students.find({'active': True}).limit(3))
print('Active students:', len(students))
for s in students:
    print('  -', s.get('_id'), ':', s.get('name'))