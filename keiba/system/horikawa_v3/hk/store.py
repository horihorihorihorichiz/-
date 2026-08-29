# -*- coding: utf-8 -*-
"""SQLite に貯める。取得が途中で止まっても続きから再開できる。"""
import sqlite3, json, os

SCHEMA = """
CREATE TABLE IF NOT EXISTS races (
  id TEXT PRIMARY KEY, date TEXT, place TEXT, surf TEXT, turn TEXT, io TEXT,
  dist INTEGER, weather TEXT, ground TEXT, cls TEXT, n INTEGER, body TEXT);
CREATE INDEX IF NOT EXISTS ix_races_date ON races(date);
CREATE TABLE IF NOT EXISTS oikiri (id TEXT PRIMARY KEY, body TEXT);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS failed (id TEXT, kind TEXT, PRIMARY KEY (id, kind));
"""


class Store:
    def __init__(self, path):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.commit()

    # 着順表
    def put_race(self, r):
        self.db.execute(
            "INSERT OR REPLACE INTO races VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (r["id"], r["date"], r["place"], r["surf"], r["turn"], r["io"],
             r["dist"], r["weather"], r["ground"], r["cls"], r["n"],
             json.dumps({"rows": r["rows"], "tidx": r["tidx"]}, ensure_ascii=False)))

    def have_races(self):
        return {x[0] for x in self.db.execute("SELECT id FROM races")}

    def all_races(self):
        out = []
        for row in self.db.execute(
                "SELECT id,date,place,surf,turn,io,dist,weather,ground,cls,n,body "
                "FROM races ORDER BY date, id"):
            b = json.loads(row[11])
            out.append({"id": row[0], "date": row[1], "place": row[2], "surf": row[3],
                        "turn": row[4], "io": row[5], "dist": row[6], "weather": row[7],
                        "ground": row[8], "cls": row[9], "n": row[10],
                        "rows": b["rows"], "tidx": b.get("tidx") or []})
        return out

    # 追い切り
    def put_oikiri(self, rid, rows):
        self.db.execute("INSERT OR REPLACE INTO oikiri VALUES (?,?)",
                        (rid, json.dumps(rows, ensure_ascii=False)))

    def have_oikiri(self):
        return {x[0] for x in self.db.execute("SELECT id FROM oikiri")}

    def all_oikiri(self):
        return {r[0]: json.loads(r[1]) for r in
                self.db.execute("SELECT id, body FROM oikiri")}

    # そのほか
    def mark_failed(self, rid, kind):
        self.db.execute("INSERT OR REPLACE INTO failed VALUES (?,?)", (rid, kind))

    def clear_failed(self, kind):
        self.db.execute("DELETE FROM failed WHERE kind=?", (kind,))

    def failed(self, kind):
        return [x[0] for x in
                self.db.execute("SELECT id FROM failed WHERE kind=?", (kind,))]

    def set(self, k, v):
        self.db.execute("INSERT OR REPLACE INTO kv VALUES (?,?)",
                        (k, json.dumps(v, ensure_ascii=False)))

    def get(self, k, d=None):
        r = self.db.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return json.loads(r[0]) if r else d

    def commit(self):
        self.db.commit()
