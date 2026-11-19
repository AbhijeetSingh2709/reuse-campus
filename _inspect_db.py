import sqlite3
from pathlib import Path

c = sqlite3.connect("db.sqlite3")
print("TABLES")
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    print(r[0])
print("---ITEMS---")
try:
    for r in c.execute("SELECT id, title, image, price, rent_per_day, listing_type FROM items_item"):
        print(r)
except Exception as e:
    print(e)
print("---USERS---")
try:
    for r in c.execute("SELECT id, username, email FROM users_user"):
        print(r)
except Exception as e:
    print(e)
print("---MEDIA---")
root = Path("media")
print("exists", root.exists())
if root.exists():
    for p in root.rglob("*"):
        print(p, p.stat().st_size if p.is_file() else "dir")
