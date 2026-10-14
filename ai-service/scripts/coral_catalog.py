# -*- coding: utf-8 -*-
"""珊瑚图鉴数据库（SQLite）—— 图鉴数据的唯一真源，支持上传/编辑/导出。

为什么用 SQLite 而不是页面里的静态数组：
  · 条目从 24 涨到几百条，静态数组没法维护；
  · 要「自行上传新种类」，就必须有个可增量写入、可校验的地方；
  · 单文件数据库便于备份/迁移（data/corals/corals.db），且零第三方依赖。

数据流：
  tools/gen_coral_catalog.py  ->  data/corals/coral_species.json（种子，入 git）
                              ->  corals.db（本文件建库并灌种子）
  /admin.html 上传 或 POST /corals/import   -> corals.db 增量写入
  小程序/网页版 GET /corals                 <- corals.db 读出展示

命令行：
    python scripts/coral_catalog.py --stats
    python scripts/coral_catalog.py --import some.csv
    python scripts/coral_catalog.py --export out.json
    python scripts/coral_catalog.py --reload      # 用种子补齐/刷新
"""
import argparse
import csv
import io
import json
import pathlib
import re
import sqlite3
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "corals" / "corals.db"
SEED_PATH = ROOT / "data" / "corals" / "coral_species.json"
# 种子来源标记：必须与 tools/gen_coral_catalog.py 写进 JSON 的 source 一致，
# 这样 --reload 才知道「哪些行是种子来的、可以覆盖」（用户自己改过的行不会被覆盖）
SEED_SOURCE = "原版精编图鉴（蓝珊）"

# 可写字段（id 由系统生成或沿用上传值）
FIELDS = ["id", "name", "latin", "genus", "genusCn", "family", "level", "group",
          "desc", "dist", "bleachingRisk", "reefBuilding", "aiGenus", "featured",
          "imgKey", "tags", "source", "updatedAt",
          "seq",
          # 详情页字段（四大板块）
          "form", "formCn", "alias", "taxonomy", "protection", "protectionNote",
          "colonyForm", "sizeCm", "colorDesc", "idFeature", "depthM", "tempSal",
          "growthRate", "symbiosis", "companions", "feeding", "threats", "population",
          # 配图：imgUrl = 实拍照片链接（可选）；hue 用于自动生成示意图
          "hue", "imgUrl", "imageNote"]

# 表头别名（中文/英文都能吃，方便用 Excel 整理后直接上传）
ALIAS = {
    "id": "id", "编号": "id",
    "name": "name", "中文名": "name", "名称": "name", "种名": "name",
    "latin": "latin", "拉丁名": "latin", "学名": "latin", "latin_name": "latin",
    "genus": "genus", "属": "genus", "属名": "genus",
    "genuscn": "genusCn", "属中文名": "genusCn",
    "family": "family", "科": "family", "科名": "family",
    "level": "level", "级别": "level",
    "group": "group", "类群": "group", "组别": "group",
    "desc": "desc", "描述": "desc", "简介": "desc", "说明": "desc",
    "dist": "dist", "分布": "dist",
    "bleachingrisk": "bleachingRisk", "白化敏感度": "bleachingRisk", "耐热性": "bleachingRisk",
    "reefbuilding": "reefBuilding", "造礁": "reefBuilding", "是否造礁": "reefBuilding",
    "aigenus": "aiGenus", "ai可识别": "aiGenus", "模型可识别": "aiGenus",
    "featured": "featured", "精选": "featured", "热门": "featured",
    "imgkey": "imgKey", "配图": "imgKey", "图片": "imgKey",
    "tags": "tags", "标签": "tags",
    "source": "source", "来源": "source",
    "imgurl": "imgUrl", "图片url": "imgUrl", "照片": "imgUrl", "实拍照片": "imgUrl",
    "form": "form", "形态码": "form",
    "alias": "alias", "别名": "alias",
    "taxonomy": "taxonomy", "生物分类": "taxonomy", "分类": "taxonomy",
    "protection": "protection", "保护等级": "protection",
    "colonyform": "colonyForm", "群落形态": "colonyForm",
    "sizecm": "sizeCm", "成体尺寸": "sizeCm", "尺寸": "sizeCm",
    "colordesc": "colorDesc", "外观颜色": "colorDesc", "颜色": "colorDesc",
    "idfeature": "idFeature", "辨识特征": "idFeature",
    "depthm": "depthM", "栖息水深": "depthM", "水深": "depthM",
    "tempsal": "tempSal", "水温盐度": "tempSal",
    "growthrate": "growthRate", "生长速度": "growthRate",
    "symbiosis": "symbiosis", "共生特点": "symbiosis", "虫黄藻共生": "symbiosis",
    "companions": "companions", "伴生生物": "companions",
    "feeding": "feeding", "捕食方式": "feeding", "摄食方式": "feeding", "食性": "feeding",
    "threats": "threats", "致危因素": "threats", "主要威胁": "threats",
    "population": "population", "野外种群现状": "population", "种群现状": "population",
    "hue": "hue",
}


def _slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return s


def _bool(v, default=False):
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "y", "是", "造礁", "✓")


def normalize(raw):
    """把任意来源的一条记录（中文/英文键、字符串/布尔）规范成入库字段。"""
    it = {}
    for k, v in (raw or {}).items():
        key = ALIAS.get(str(k).strip().lower().replace(" ", ""), str(k).strip())
        if key in FIELDS:
            it[key] = v
    for k in FIELDS:
        it.setdefault(k, "")
    it["reefBuilding"] = 1 if _bool(it["reefBuilding"]) else 0
    it["aiGenus"] = 1 if _bool(it["aiGenus"]) else 0
    it["featured"] = 1 if _bool(it["featured"]) else 0
    tags = it.get("tags")
    it["tags"] = ",".join(tags) if isinstance(tags, (list, tuple)) else str(tags or "")
    it["name"] = str(it["name"]).strip()
    it["latin"] = str(it["latin"]).strip()
    it["genus"] = str(it["genus"]).strip()
    if not it["id"]:
        base = _slug(it["latin"] or it["name"])
        it["id"] = ("genus-" + base) if (it["level"] == "genus" and base) else (
            "species-" + base if base else "")
    it["id"] = str(it["id"]).strip()
    it["updatedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return it


DDL = """
CREATE TABLE IF NOT EXISTS corals (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL DEFAULT '',
  latin         TEXT DEFAULT '',
  genus         TEXT DEFAULT '',
  genusCn       TEXT DEFAULT '',
  family        TEXT DEFAULT '',
  level         TEXT DEFAULT '',
  "group"       TEXT DEFAULT '',
  "desc"        TEXT DEFAULT '',
  dist          TEXT DEFAULT '',
  bleachingRisk TEXT DEFAULT '',
  reefBuilding  INTEGER DEFAULT 0,
  aiGenus       INTEGER DEFAULT 0,
  featured      INTEGER DEFAULT 0,
  imgKey        TEXT DEFAULT '',
  tags          TEXT DEFAULT '',
  source        TEXT DEFAULT '',
  seq           INTEGER DEFAULT 0,
  form          TEXT DEFAULT '',
  formCn        TEXT DEFAULT '',
  alias         TEXT DEFAULT '',
  taxonomy      TEXT DEFAULT '',
  protection    TEXT DEFAULT '',
  protectionNote TEXT DEFAULT '',
  colonyForm    TEXT DEFAULT '',
  sizeCm        TEXT DEFAULT '',
  colorDesc     TEXT DEFAULT '',
  idFeature     TEXT DEFAULT '',
  depthM        TEXT DEFAULT '',
  tempSal       TEXT DEFAULT '',
  growthRate    TEXT DEFAULT '',
  symbiosis     TEXT DEFAULT '',
  companions    TEXT DEFAULT '',
  feeding       TEXT DEFAULT '',
  threats       TEXT DEFAULT '',
  population    TEXT DEFAULT '',
  hue           INTEGER DEFAULT 0,
  imgUrl        TEXT DEFAULT '',
  imageNote     TEXT DEFAULT '',
  updatedAt     TEXT DEFAULT ''
)
"""
COLS = ["id", "name", "latin", "genus", "genusCn", "family", "level", "group",
        "desc", "dist", "bleachingRisk", "reefBuilding", "aiGenus", "featured",
        "imgKey", "tags", "source", "updatedAt",
        "seq",
        "form", "formCn", "alias", "taxonomy", "protection", "protectionNote",
        "colonyForm", "sizeCm", "colorDesc", "idFeature", "depthM", "tempSal",
        "growthRate", "symbiosis", "companions", "feeding", "threats", "population",
        "hue", "imgUrl", "imageNote"]
INT_COLS = {"reefBuilding", "aiGenus", "featured", "hue", "seq"}
_ENSURED = False


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error:
        pass
    return conn


def _upsert(conn, it):
    quoted = ", ".join(f'"{c}"' for c in COLS)
    marks = ", ".join("?" for _ in COLS)
    upd = ", ".join(f'"{c}"=excluded."{c}"' for c in COLS if c != "id")
    conn.execute(f'INSERT INTO corals ({quoted}) VALUES ({marks}) '
                 f'ON CONFLICT(id) DO UPDATE SET {upd}',
                 [it.get(c) for c in COLS])


def _migrate(conn):
    """老库补列：把 DDL 里新增的列 ALTER 上去（SQLite 的 ADD COLUMN 没有 IF NOT EXISTS）。"""
    have = {r["name"] for r in conn.execute("PRAGMA table_info(corals)")}
    added = []
    for col in COLS:
        if col not in have:
            typ = "INTEGER" if col in INT_COLS else "TEXT"
            default = "0" if typ == "INTEGER" else "''"
            conn.execute(f'ALTER TABLE corals ADD COLUMN "{col}" {typ} DEFAULT {default}')
            added.append(col)
    if added:
        conn.commit()
    return added


def _write_many(conn, items, overwrite=False, only_seed=False):
    added = updated = skipped = 0
    errors = []
    for i, raw in enumerate(items or []):
        it = normalize(raw)
        if not it["id"] or not it["name"]:
            errors.append(f"第 {i + 1} 条：缺少「中文名」或无法生成 id，已跳过")
            skipped += 1
            continue
        row = conn.execute('SELECT source FROM corals WHERE id=?', (it["id"],)).fetchone()
        if row and only_seed and (row["source"] or "") != SEED_SOURCE:
            skipped += 1                      # 用户自己维护过这条，种子不覆盖
            continue
        if row and not overwrite:
            skipped += 1
            continue
        _upsert(conn, it)
        if row:
            updated += 1
        else:
            added += 1
    conn.commit()
    return {"added": added, "updated": updated, "skipped": skipped, "errors": errors}


def seed_import(overwrite=False):
    """把种子 JSON 灌进库。overwrite=False 只补缺失项（不碰用户改过的数据）。"""
    if not SEED_PATH.exists():
        return {"added": 0, "updated": 0, "skipped": 0,
                "errors": [f"种子文件不存在: {SEED_PATH}"]}
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    conn = connect()
    conn.execute(DDL)
    try:
        return _write_many(conn, items, overwrite=overwrite, only_seed=True)
    finally:
        conn.close()


# 后加的详情页字段：库里为空时按 id 用种子补上（已有内容不动，覆盖不到用户自己维护的数据）
BACKFILL_FIELDS = ("colorDesc", "feeding", "population")
# 早期自动生成的占位别名（“…（俗称）”“…（中文名）”），视为空，允许被种子里的正式别名覆盖
ALIAS_PLACEHOLDER = ("（俗称）", "（中文名）", "（网络资料）", "（网上资料）")


def backfill_from_seed(fields=BACKFILL_FIELDS):
    """用种子补齐库中为空的详情字段；别名里的占位文案一并换成种子里的正式别名（可为空）。

    返回补写的字段个数。
    """
    if not SEED_PATH.exists():
        return 0
    try:
        data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return 0
    items = data.get("items") if isinstance(data, dict) else data
    like = " OR ".join(f'"alias" LIKE \'%{s}\'' for s in ALIAS_PLACEHOLDER)
    conn = connect()
    conn.execute(DDL)
    n = 0
    try:
        for raw in items or []:
            it = normalize(raw)
            if not it["id"]:
                continue
            # 别名特殊处理：空值/占位值都换成种子里的值（种子为空则清掉占位）
            n += conn.execute(
                f'UPDATE corals SET "alias"=? WHERE id=? AND '
                f'("alias" IS NULL OR "alias"=\'\' OR {like})',
                (str(it.get("alias") or ""), it["id"])).rowcount
            for f in fields:
                v = it.get(f)
                if not v:
                    continue
                n += conn.execute(
                    f'UPDATE corals SET "{f}"=? '
                    f'WHERE id=? AND ("{f}" IS NULL OR "{f}"=\'\')',
                    (v, it["id"])).rowcount
        conn.commit()
    finally:
        conn.close()
    return n


def init(reload=False, verbose=False):
    """建库建表；空库自动灌种子。返回统计。"""
    global _ENSURED
    conn = connect()
    conn.execute(DDL)
    added = _migrate(conn)
    if added and verbose:
        print(f"[图鉴] 数据库补列：{'、'.join(added)}")
    conn.execute('CREATE INDEX IF NOT EXISTS idx_corals_genus ON corals(genus)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_corals_name ON corals(name)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_corals_level ON corals(level)')
    conn.commit()
    n = conn.execute('SELECT COUNT(*) c FROM corals').fetchone()["c"]
    conn.close()
    seeded = None
    if n == 0 or reload:
        seeded = seed_import(overwrite=reload)
        if verbose:
            print(f"[图鉴] 灌入种子：新增 {seeded['added']} / 更新 {seeded['updated']} / "
                  f"跳过 {seeded['skipped']}")
    # 老库缺详情字段（form 为空）时，用种子刷新一次，把新的板块字段补上
    conn = connect()
    blank = conn.execute(
        "SELECT COUNT(*) c FROM corals WHERE form IS NULL OR form=''").fetchone()["c"]
    conn.close()
    if blank:
        refill = seed_import(overwrite=True)
        if verbose:
            print(f"[图鉴] 补齐详情字段：更新 {refill['updated']} 条"
                  f"（未覆盖你自己改过的条目）")
    # 后加的字段（捕食方式 / 野外种群现状 / 外观颜色）同样按需补空
    filled = backfill_from_seed()
    if filled and verbose:
        print(f"[图鉴] 补齐后加字段（捕食方式 / 野外种群现状 / 外观颜色）：{filled} 处")
    _ENSURED = True
    return seeded


def ensure():
    if not _ENSURED:
        init()


def _row_to_dict(row):
    d = {k: row[k] for k in row.keys()}
    d["reefBuilding"] = bool(d.get("reefBuilding"))
    d["aiGenus"] = bool(d.get("aiGenus"))
    d["featured"] = bool(d.get("featured"))
    d["hue"] = int(d.get("hue") or 0)
    d["tags"] = [t for t in str(d.get("tags") or "").split(",") if t]
    return d


ORDER = {"seq": "seq ASC, name ASC",           # 默认：按种子/上传顺序（= 原来的展示顺序）
         "name": "name ASC", "latin": "latin ASC", "updated": "updatedAt DESC",
         "genus": "genus ASC, name ASC"}


def list_items(q="", genus="", group="", level="", featured=None,
               limit=50, offset=0, order="seq"):
    ensure()
    where, args = [], []
    if q:
        like = f"%{q.strip()}%"
        where.append('(name LIKE ? OR latin LIKE ? OR genusCn LIKE ? OR genus LIKE ? '
                     'OR "desc" LIKE ? OR tags LIKE ? OR family LIKE ?)')
        args += [like] * 7
    if genus:
        where.append('genus = ?')
        args.append(genus)
    if group:
        where.append('"group" = ?')
        args.append(group)
    if level:
        where.append('level = ?')
        args.append(level)
    if featured is not None:
        where.append('featured = ?')
        args.append(1 if featured else 0)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    order_by = ORDER.get(order, ORDER["name"])
    conn = connect()
    try:
        total = conn.execute(f'SELECT COUNT(*) c FROM corals {clause}', args).fetchone()["c"]
        rows = conn.execute(
            f'SELECT * FROM corals {clause} '
            f'ORDER BY featured DESC, {order_by} LIMIT ? OFFSET ?',
            args + [max(1, min(int(limit or 50), 500)), max(0, int(offset or 0))]).fetchall()
        return total, [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_item(item_id):
    ensure()
    conn = connect()
    try:
        row = conn.execute('SELECT * FROM corals WHERE id=?', (item_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def add_item(raw, overwrite=True):
    """单条新增/覆盖。返回 (item, created)。"""
    it = normalize(raw)
    if not it["id"] or not it["name"]:
        raise ValueError("缺少「中文名」或无法生成 id")
    ensure()
    conn = connect()
    try:
        existed = conn.execute('SELECT 1 FROM corals WHERE id=?', (it["id"],)).fetchone()
        _upsert(conn, it)
        conn.commit()
        return it, not existed
    finally:
        conn.close()


def update_item(item_id, fields):
    """局部更新；id 不可改。"""
    ensure()
    conn = connect()
    try:
        row = conn.execute('SELECT * FROM corals WHERE id=?', (item_id,)).fetchone()
        if not row:
            return None
        cur = dict(row)
        for k, v in (fields or {}).items():
            key = ALIAS.get(str(k).strip().lower().replace(" ", ""), str(k).strip())
            if key in FIELDS and key != "id":
                cur[key] = v
        it = normalize(cur)
        it["id"] = item_id
        _upsert(conn, it)
        conn.commit()
        return it
    finally:
        conn.close()


def delete_item(item_id):
    ensure()
    conn = connect()
    try:
        cur = conn.execute('DELETE FROM corals WHERE id=?', (item_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def stats():
    ensure()
    conn = connect()
    try:
        total = conn.execute('SELECT COUNT(*) c FROM corals').fetchone()["c"]
        by_group = {r["k"]: r["c"] for r in conn.execute(
            'SELECT "group" k, COUNT(*) c FROM corals GROUP BY 1 ORDER BY c DESC')}
        by_level = {r["k"]: r["c"] for r in conn.execute(
            'SELECT level k, COUNT(*) c FROM corals GROUP BY 1 ORDER BY c DESC')}
        genera = conn.execute(
            'SELECT genus, MAX(genusCn) genusCn, MAX(family) family, COUNT(*) c '
            'FROM corals GROUP BY genus ORDER BY c DESC, genus ASC').fetchall()
        updated = conn.execute('SELECT MAX(updatedAt) m FROM corals').fetchone()["m"]
        return {
            "total": total,
            "genera": len(genera),
            "families": conn.execute(
                'SELECT COUNT(DISTINCT family) c FROM corals').fetchone()["c"],
            "featured": conn.execute(
                'SELECT COUNT(*) c FROM corals WHERE featured=1').fetchone()["c"],
            "aiGenera": conn.execute(
                "SELECT COUNT(*) c FROM corals WHERE aiGenus=1"
            ).fetchone()["c"],
            "byGroup": by_group,
            "byLevel": by_level,
            "generaList": [{"genus": r["genus"], "genusCn": r["genusCn"],
                            "family": r["family"], "count": r["c"]} for r in genera],
            "updatedAt": updated or "",
            "dbPath": str(DB_PATH.relative_to(ROOT)),
        }
    finally:
        conn.close()


def export_items():
    return list_items(limit=500, offset=0)[1]


def parse_upload(filename, blob):
    """把上传的文件解析成条目列表。支持 .json（数组 / {items:[...]}）与 .csv/.tsv。"""
    name = (filename or "").lower()
    if name.endswith(".json") or blob[:1] in (b"[", b"{"):
        data = json.loads(blob.decode("utf-8-sig"))
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise ValueError("JSON 需要是数组，或形如 {\"items\": [...]}")
        return items
    text = blob.decode("utf-8-sig")
    delim = "\t" if name.endswith(".tsv") else ","
    rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
    if not rows:
        raise ValueError("CSV 没有数据行（第一行需要是表头）")
    return rows


def import_upload(filename, blob, overwrite=True):
    items = parse_upload(filename, blob)
    ensure()
    conn = connect()
    try:
        res = _write_many(conn, items, overwrite=overwrite)
        res["total"] = len(items)
        return res
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description="珊瑚图鉴数据库（SQLite）管理")
    ap.add_argument("--stats", action="store_true", help="打印统计")
    ap.add_argument("--reload", action="store_true", help="用种子补齐/刷新（不覆盖用户改过的）")
    ap.add_argument("--backfill", action="store_true", help="用种子补齐库中为空的详情字段")
    ap.add_argument("--import", dest="import_file", default="", help="导入 JSON/CSV/TSV")
    ap.add_argument("--export", dest="export_file", default="", help="导出全部为 JSON")
    ap.add_argument("--no-overwrite", action="store_true", help="导入时只补缺失项")
    args = ap.parse_args()
    init(reload=args.reload, verbose=True)
    if args.backfill:
        print("已用种子补齐空字段 " + str(backfill_from_seed()) + " 处")
    if args.import_file:
        p = pathlib.Path(args.import_file)
        res = import_upload(p.name, p.read_bytes(), overwrite=not args.no_overwrite)
        print(json.dumps(res, ensure_ascii=False, indent=1))
    if args.export_file:
        out = pathlib.Path(args.export_file)
        out.write_text(json.dumps({"schema": 1, "items": export_items()},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已导出 {out}")
    if args.stats or not (args.import_file or args.export_file):
        s = {k: v for k, v in stats().items() if k != "generaList"}
        s["generaListTop"] = stats()["generaList"][:8]
        print(json.dumps(s, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
