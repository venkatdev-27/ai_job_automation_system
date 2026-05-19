from database.client import get_collection
col = get_collection('students')
doc = col.find_one({'active': True})
if doc:
    print('Keys:', list(doc.keys()))
    print('full_name:', doc.get('full_name', '*** MISSING ***'))
    print('name:', doc.get('name', '*** MISSING ***'))
    print('student_id:', doc.get('student_id', '*** MISSING ***'))
else:
    print('NO ACTIVE STUDENTS FOUND')
