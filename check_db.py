import sqlite3

conn = sqlite3.connect('curriculum.db')
cur = conn.cursor()

print('=== tables ===')
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(cur.fetchall())

print('\n=== row counts ===')
for t in ['courses', 'prerequisites', 'study_plan']:
    cur.execute(f'SELECT COUNT(*) FROM {t}')
    print(f'  {t}: {cur.fetchone()[0]} rows')

conn.close()
