"""
One-click pipeline for the KuaiRec short-video project:
download (if needed) -> load CSVs -> run sql/01-06 -> save every query result to output/tables/
-> statistical tests -> charts and report.

Usage:
    python src/run_analysis.py                     # auto: download from Zenodo if needed, DuckDB if installed
    python src/run_analysis.py --engine sqlite     # no DuckDB (slow on the full 12.5M rows)
    python src/run_analysis.py --data data/sample  # synthetic test data

SQL files are split into blocks with "-- @name xxx"; if the last statement of a block is a query,
its result is saved as output/tables/xxx.csv
"""
import argparse
import csv
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR, OUT = ROOT / "sql", ROOT / "output"
ZENODO = "https://zenodo.org/records/18164998/files/KuaiRec.zip"   # official release, CC BY 4.0
NEEDED = ["big_matrix.csv", "small_matrix.csv", "user_features.csv", "item_daily_features.csv",
          "kuairec_caption_category.csv"]
SQL_FILES = ["02_engagement.sql", "03_content.sql", "04_funnel.sql", "05_users.sql", "06_recommender.sql"]

# First-level category ids -> English names (the source file only has Chinese names)
CATEGORY_EN = {
    1: "Dance", 2: "Music", 3: "Gaming", 4: "Beauty & makeup", 5: "Fashion", 6: "Celebrities & entertainment",
    7: "Sports", 8: "Good looks", 9: "Comedy", 10: "Travel", 11: "Lifestyle", 12: "Food",
    13: "Rural life", 14: "Education", 15: "Art", 16: "Health", 17: "Pets", 18: "Cars",
    19: "Relationships", 20: "Anime & ACG", 21: "Culture & humanities", 22: "Finance", 23: "Current affairs",
    24: "Astrology", 25: "Parenting", 26: "Photography", 27: "Tech & gadgets", 28: "Local news",
    29: "Science & law", 31: "Fitness", 32: "Short drama", 33: "Selfies", 34: "Other", 35: "Military",
    36: "Home & real estate", 37: "Oddities", 38: "Books", 39: "Film & TV", 418: "Everyday clips",
}


# ---------------------------------------------------------------- data
def download(target_zip: Path):
    """Resumable download: keeps a .part file, resumes with HTTP Range after a dropped connection,
    and only renames to .zip once the size matches and the zip is readable."""
    print(f"Downloading KuaiRec (432 MB) from Zenodo ...\n  {ZENODO}", flush=True)
    target_zip.parent.mkdir(parents=True, exist_ok=True)
    part = target_zip.with_suffix(".part")
    if target_zip.exists() and not zipfile.is_zipfile(target_zip):   # earlier incomplete download
        target_zip.replace(part)
    total, use_range, wait = None, True, 5
    for attempt in range(1, 81):
        have = part.stat().st_size if part.exists() else 0
        if total and have >= total:
            break
        if not use_range and have:
            part.unlink()
            have = 0
        try:
            headers = {"User-Agent": "Mozilla/5.0 (KuaiRec analysis script)"}
            if use_range and have:
                headers["Range"] = f"bytes={have}-"
            req = urllib.request.Request(ZENODO, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                cr = r.headers.get("Content-Range")              # e.g. "bytes 100-431999999/432000000"
                if cr and "/" in cr:
                    total = int(cr.split("/")[-1])
                else:                                             # full response: start the file over
                    total = int(r.headers.get("Content-Length", 0)) or None
                    have = 0
                    part.unlink(missing_ok=True)
                last = -1
                with open(part, "ab") as f:
                    while chunk := r.read(4 << 20):
                        f.write(chunk)
                        have += len(chunk)
                        if total and (have * 20 // total) != last:
                            last = have * 20 // total
                            print(f"  {have / 1e6:,.0f} / {total / 1e6:,.0f} MB ({have * 100 // total}%)", flush=True)
            wait = 5
        except urllib.error.HTTPError as e:
            if e.code == 416:                                     # range not satisfiable: local part is bad
                print(f"  HTTP 416 at {have / 1e6:,.0f} MB; discarding partial file and starting over", flush=True)
                part.unlink(missing_ok=True)
            elif e.code in (429, 503):                            # rate limited: honour Retry-After
                wait = int(e.headers.get("Retry-After") or 0) or min(wait * 2, 300)
                print(f"  HTTP {e.code} (server busy / rate limit); waiting {wait} s (attempt {attempt})", flush=True)
                time.sleep(wait)
            else:
                if use_range:
                    print(f"  HTTP {e.code} on resume; switching to a fresh full download", flush=True)
                    use_range = False
                else:
                    print(f"  HTTP {e.code}; retry {attempt} in 30 s", flush=True)
                    time.sleep(30)
        except Exception as e:
            print(f"  connection dropped at {have / 1e6:,.0f} MB ({type(e).__name__}: {e}); retry {attempt} in 10 s",
                  flush=True)
            time.sleep(10)
    size = part.stat().st_size if part.exists() else 0
    if not total or size != total or not zipfile.is_zipfile(part):
        raise RuntimeError(f"incomplete download ({size:,} of {total or '?'} bytes); run again to resume")
    part.replace(target_zip)
    print("  download complete", flush=True)


def extract(z: Path, target: Path):
    print(f"Extracting {z.name} ...")
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            base = Path(n).name
            if base in NEEDED and not (target / base).exists():
                with zf.open(n) as src, open(target / base, "wb") as dst:
                    shutil.copyfileobj(src, dst, 16 << 20)


def find_data(arg):
    if arg:
        p = Path(arg)
        if all((p / f).exists() for f in NEEDED):
            return p
        raise SystemExit(f"[ERROR] {p} does not contain {', '.join(NEEDED)}")
    target = ROOT / "data" / "kuairec"
    if all((target / f).exists() for f in NEEDED):
        return target
    zips = [z for z in sorted((ROOT / "data").glob("*.zip")) + sorted(ROOT.parent.glob("KuaiRec*.zip"))]
    z = next((z for z in zips if "kuairec" in z.name.lower() and zipfile.is_zipfile(z)), None)
    if z is None:
        z = ROOT / "data" / "KuaiRec.zip"
        try:
            download(z)
        except Exception as e:
            raise SystemExit(f"[ERROR] Download failed ({e}). Download {ZENODO} manually, put it in the data "
                             f"folder and run again.")
    extract(z, target)
    missing = [f for f in NEEDED if not (target / f).exists()]
    if missing:
        raise SystemExit(f"[ERROR] {z.name} is missing {missing}")
    return target


def read_categories(path: Path) -> pd.DataFrame:
    """The caption file has unquoted commas inside free text, so pandas cannot parse it.
    video_id is always the first field and the six category fields are always the last six."""
    rows = []
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for r in reader:
            if len(r) < 7:
                continue
            try:
                vid, cat = int(r[0].strip()), int(r[-6].strip())
            except ValueError:
                continue
            rows.append((vid, CATEGORY_EN.get(cat, "unknown")))
    return pd.DataFrame(rows, columns=["video_id", "category"]).drop_duplicates("video_id")


# ---------------------------------------------------------------- engine
class Engine:
    def __init__(self, kind: str, db: str):
        self.kind = kind
        if kind == "duckdb":
            import duckdb
            self.con = duckdb.connect(db)
            self.con.execute(f"SET temp_directory='{Path(db).parent.as_posix()}/duckdb_tmp'")
            self.con.execute("SET preserve_insertion_order=false")
        else:
            import sqlite3
            self.con = sqlite3.connect(db)
            self.con.execute("PRAGMA journal_mode=OFF")
            self.con.execute("PRAGMA synchronous=OFF")

    def load_csv(self, name: str, path: Path, types=None):
        if self.kind == "duckdb":
            t = ""
            if types:
                t = ", types={" + ", ".join(f"'{k}': '{v}'" for k, v in types.items()) + "}"
            self.con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM "
                             f"read_csv('{path.as_posix()}', header=true, sample_size=-1{t})")
            return self.con.execute(f"SELECT COUNT(*) FROM {name}").fetchall()[0][0]
        n = 0
        self.con.execute(f"DROP TABLE IF EXISTS {name}")
        for chunk in pd.read_csv(path, chunksize=1_000_000,
                                 dtype={k: str for k in (types or {})}):
            chunk.to_sql(name, self.con, if_exists="append", index=False)
            n += len(chunk)
        return n

    def load_df(self, name: str, df: pd.DataFrame):
        if self.kind == "duckdb":
            self.con.register("tmp_df", df)
            self.con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp_df")
            self.con.unregister("tmp_df")
        else:
            df.to_sql(name, self.con, if_exists="replace", index=False)

    def index(self):
        if self.kind == "sqlite":
            for sql in ["CREATE INDEX IF NOT EXISTS ix_vc ON video_cat(video_id)",
                        "CREATE INDEX IF NOT EXISTS ix_inter_u ON inter(user_id)",
                        "CREATE INDEX IF NOT EXISTS ix_inter_v ON inter(video_id)"]:
                try:
                    self.con.execute(sql)
                except Exception:
                    pass

    def run(self, sql: str, fetch: bool):
        if self.kind == "duckdb":
            r = self.con.execute(sql)
            return r.df() if fetch else None
        if fetch:
            return pd.read_sql_query(sql, self.con)
        self.con.execute(sql)
        self.con.commit()


def parse_blocks(path: Path):
    text = path.read_text(encoding="utf-8")
    for part in re.split(r"^-- @name\s+", text, flags=re.M)[1:]:
        name, body = part.split("\n", 1)
        body = "\n".join(l for l in body.splitlines() if not l.strip().startswith("--"))
        yield name.strip(), [s.strip() for s in body.split(";") if s.strip()]


def run_file(eng: Engine, path: Path):
    for name, stmts in parse_blocks(path):
        t = time.time()
        res = None
        for s in stmts:
            res = eng.run(s, fetch=s.lstrip().upper().startswith(("SELECT", "WITH")))
        if res is not None:
            (OUT / "tables").mkdir(parents=True, exist_ok=True)
            res.to_csv(OUT / "tables" / f"{name}.csv", index=False, encoding="utf-8")
        print(f"  {path.name:<20} {name:<22} {time.time() - t:6.1f}s", flush=True)
        if name == "build_inter":
            eng.index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None, help="Folder with the KuaiRec CSVs (default: download/auto-detect)")
    ap.add_argument("--engine", choices=["auto", "duckdb", "sqlite"], default="auto")
    a = ap.parse_args()
    if a.engine == "auto":
        try:
            import duckdb  # noqa: F401
            a.engine = "duckdb"
        except ImportError:
            a.engine = "sqlite"

    folder = find_data(a.data)
    real = "sample" not in folder.name
    print(f"Data folder: {folder}\nEngine: {a.engine}", flush=True)
    for sub in ("tables", "charts"):
        shutil.rmtree(OUT / sub, ignore_errors=True)
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    db = OUT / f"kuairec.{a.engine}"
    db.unlink(missing_ok=True)
    eng = Engine(a.engine, str(db))

    t0 = time.time()
    print("[1/4] Load CSV files", flush=True)
    mtypes = {"time": "VARCHAR"}
    for table, file, types in [("big", "big_matrix.csv", mtypes), ("small", "small_matrix.csv", mtypes),
                               ("users", "user_features.csv", None), ("daily", "item_daily_features.csv", None)]:
        t = time.time()
        n = eng.load_csv(table, folder / file, types)
        print(f"  {file:<30} {n:>12,} rows {time.time() - t:6.1f}s", flush=True)
    cats = read_categories(folder / "kuairec_caption_category.csv")
    eng.load_df("video_cat", cats)
    print(f"  {'kuairec_caption_category.csv':<30} {len(cats):>12,} videos with a category", flush=True)
    pd.DataFrame([{"source": "Zenodo KuaiRec release (real data)" if real else "synthetic sample"}]).to_csv(
        OUT / "tables" / "data_source.csv", index=False)

    print("[2/4] Clean and analyse (SQL)", flush=True)
    run_file(eng, SQL_DIR / "01_clean.sql")
    for f in SQL_FILES:
        run_file(eng, SQL_DIR / f)

    print("[3/4] Statistical tests", flush=True)
    sys.path.insert(0, str(Path(__file__).parent))
    from stats_tests import run_tests
    run_tests(OUT)

    print("[4/4] Charts and report", flush=True)
    from make_report import build
    build(OUT)
    print(f"Done in {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
