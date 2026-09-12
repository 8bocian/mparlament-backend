import sqlite3

conn = sqlite3.connect(r"A:\mparl backend\mparlament-backend\mparlament.db")
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tabele:", tables)
print()

if "users" in tables:
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    print(f"Users count: {count}")
    print()
    cur.execute("SELECT id, username, name, role, password_hash FROM users LIMIT 20")
    print("Users:")
    for row in cur.fetchall():
        hash_prefix = (row[4][:50] + "...") if row[4] else "None"
        print(f"  id={row[0]} | username={row[1]!r} | name={row[2]!r} | role={row[3]!r} | hash={hash_prefix}")
else:
    print("!!! Brak tabeli users !!!")

conn.close()
