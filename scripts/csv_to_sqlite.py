import sqlite3
import csv
from pathlib import Path

DB_PATH = "data/kure_fish.db"
DATA_DIR = "data"

conn = sqlite3.connect(DB_PATH)

conn.execute('''
    CREATE TABLE IF NOT EXISTS fish (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        品目    TEXT,
        産地    TEXT,
        年      INTEGER,
        月      INTEGER,
        数量_kg INTEGER,
        金額_円 INTEGER
    )
''')

# data/以下のCSVを全部読み込む
csv_files = sorted(Path(DATA_DIR).glob("kure_fish_market_*.csv"))
print(f"{len(csv_files)}件のCSVを処理します")

for csv_file in csv_files:
    with open(csv_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append((
                row["品目"], row["産地"], int(row["年"]), int(row["月"]),
                int(row["数量_kg"]) if row["数量_kg"] else None,
                int(row["金額_円"]) if row["金額_円"] else None,
            ))
        conn.executemany(
            "INSERT INTO fish (品目, 産地, 年, 月, 数量_kg, 金額_円) VALUES (?,?,?,?,?,?)",
            rows
        )
        print(f"  {csv_file.name}: {len(rows)}件")

conn.commit()
conn.close()
print("完了！kure_fish.db に保存されました")