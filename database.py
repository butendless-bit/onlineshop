import sqlite3
import os
import shutil
from config import DB_PATH, DB_SEED


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    # Vercel: 시드 DB를 /tmp로 복사 (쓰기 가능 경로)
    if os.environ.get("VERCEL") and not os.path.exists(DB_PATH):
        if os.path.exists(DB_SEED):
            shutil.copy2(DB_SEED, DB_PATH)

    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                model_no    TEXT NOT NULL UNIQUE,
                product_name TEXT NOT NULL,
                category    TEXT NOT NULL,
                product_url TEXT,
                image_url   TEXT,
                review_count INTEGER DEFAULT 0,
                spec        TEXT DEFAULT '{}',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                model_no       TEXT NOT NULL,
                original_price INTEGER,
                sale_price     INTEGER,
                benefit_price  INTEGER,
                crawled_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (model_no) REFERENCES products(model_no)
            );

            CREATE TABLE IF NOT EXISTS competitor_prices (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                model_no    TEXT NOT NULL,
                naver_price INTEGER,
                crawled_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS subscription_products (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name         TEXT NOT NULL,
                model_no             TEXT,
                category             TEXT,
                monthly_fee          INTEGER NOT NULL,
                contract_months      INTEGER DEFAULT 36,
                install_fee          INTEGER DEFAULT 0,
                image_url            TEXT,
                product_url          TEXT,
                notes                TEXT,
                is_active            INTEGER DEFAULT 1,
                care_plan            TEXT,
                card_benefit_monthly INTEGER,
                goods_attrs          TEXT DEFAULT '[]',
                created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_price_model   ON price_history(model_no);
            CREATE INDEX IF NOT EXISTS idx_price_crawled ON price_history(crawled_at);
            CREATE INDEX IF NOT EXISTS idx_comp_model    ON competitor_prices(model_no);
            CREATE INDEX IF NOT EXISTS idx_sub_active    ON subscription_products(is_active);
        """)
        # review_count 컬럼 — 기존 DB에 없을 수 있으므로 안전하게 추가
        try:
            conn.execute("ALTER TABLE products ADD COLUMN review_count INTEGER DEFAULT 0")
        except Exception:
            pass  # 이미 존재하면 무시
        try:
            conn.execute("ALTER TABLE products ADD COLUMN spec TEXT DEFAULT '{}'")
        except Exception:
            pass  # 이미 존재하면 무시
        for col_sql in [
            "ALTER TABLE subscription_products ADD COLUMN care_plan TEXT",
            "ALTER TABLE subscription_products ADD COLUMN card_benefit_monthly INTEGER",
            "ALTER TABLE subscription_products ADD COLUMN goods_attrs TEXT DEFAULT '[]'",
        ]:
            try:
                conn.execute(col_sql)
            except Exception:
                pass
        # model_no 유니크 인덱스 (크롤링 upsert에 필요)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sub_model_no
            ON subscription_products(model_no) WHERE model_no IS NOT NULL
        """)
    print(f"[DB] 초기화 완료 → {DB_PATH}")


def upsert_product(model_no, product_name, category, product_url, image_url, spec="{}"):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO products (model_no, product_name, category, product_url, image_url, spec)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(model_no) DO UPDATE SET
                product_name = excluded.product_name,
                product_url  = excluded.product_url,
                image_url    = excluded.image_url,
                spec         = excluded.spec,
                updated_at   = CURRENT_TIMESTAMP
        """, (model_no, product_name, category, product_url, image_url, spec))


def insert_price(model_no, original_price, sale_price, benefit_price):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO price_history (model_no, original_price, sale_price, benefit_price)
            VALUES (?, ?, ?, ?)
        """, (model_no, original_price, sale_price, benefit_price))


def get_latest_prices(category=None):
    """각 모델의 가장 최근 가격 1건 + 어제 가격 조회"""
    sql = """
        WITH latest AS (
            SELECT ph.*,
                   ROW_NUMBER() OVER (PARTITION BY ph.model_no ORDER BY ph.crawled_at DESC) AS rn
            FROM price_history ph
        ),
        prev AS (
            SELECT ph.*,
                   ROW_NUMBER() OVER (PARTITION BY ph.model_no ORDER BY ph.crawled_at DESC) AS rn
            FROM price_history ph
            WHERE date(ph.crawled_at) < date('now')
        )
        SELECT
            p.model_no, p.product_name, p.category, p.product_url, p.image_url,
            p.review_count, p.spec,
            l.original_price, l.sale_price, l.benefit_price, l.crawled_at,
            prev.benefit_price AS prev_benefit_price
        FROM products p
        JOIN latest l ON l.model_no = p.model_no AND l.rn = 1
        LEFT JOIN prev  ON prev.model_no = p.model_no AND prev.rn = 1
    """
    params = []
    if category:
        sql += " WHERE p.category = ?"
        params.append(category)

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_alltime_low(model_no):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MIN(benefit_price) AS min_price FROM price_history WHERE model_no = ?",
            (model_no,)
        ).fetchone()
    return row["min_price"] if row else None


def get_status():
    with get_conn() as conn:
        last = conn.execute(
            "SELECT MAX(crawled_at) AS last FROM price_history"
        ).fetchone()["last"]
        total = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
    return {"last_crawled": last, "total_products": total}


def update_review_count(model_no: str, review_count: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE products SET review_count = ? WHERE model_no = ?",
            (review_count, model_no)
        )


def upsert_competitor_price(model_no: str, naver_price: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO competitor_prices (model_no, naver_price) VALUES (?, ?)",
            (model_no, naver_price)
        )


def get_competitor_price(model_no: str) -> int | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT naver_price FROM competitor_prices
               WHERE model_no = ? ORDER BY crawled_at DESC LIMIT 1""",
            (model_no,)
        ).fetchone()
    return row["naver_price"] if row else None


# ── 구독상품 CRUD ──────────────────────────────────────────────────────────────

def get_subscription_products(active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM subscription_products"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY created_at DESC"
    with get_conn() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def add_subscription_product(product_name, model_no, category, monthly_fee,
                              contract_months, install_fee, image_url, product_url, notes) -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO subscription_products
              (product_name, model_no, category, monthly_fee, contract_months,
               install_fee, image_url, product_url, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (product_name, model_no, category, monthly_fee, contract_months,
              install_fee, image_url, product_url, notes))
        return cur.lastrowid


def update_subscription_product(sub_id: int, **fields) -> bool:
    allowed = {"product_name", "model_no", "category", "monthly_fee",
               "contract_months", "install_fee", "image_url", "product_url", "notes", "is_active"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return False
    cols = ", ".join(f"{k} = ?" for k in sets)
    vals = list(sets.values()) + [sub_id]
    with get_conn() as conn:
        conn.execute(
            f"UPDATE subscription_products SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            vals
        )
    return True


def delete_subscription_product(sub_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM subscription_products WHERE id = ?", (sub_id,))


def upsert_subscription_from_crawl(product_name, model_no, category,
                                   monthly_fee, image_url, product_url,
                                   contract_months=None, care_plan=None,
                                   card_benefit_monthly=None, goods_attrs="[]"):
    """크롤링으로 발견된 구독상품 — model_no 기준으로 upsert"""
    vals = (product_name, model_no, category, monthly_fee, image_url, product_url,
            contract_months or 60, care_plan, card_benefit_monthly, goods_attrs)
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT id FROM subscription_products WHERE model_no = ?", (model_no,)
        ).fetchone()
        if exists:
            conn.execute("""
                UPDATE subscription_products SET
                    product_name         = ?,
                    category             = ?,
                    monthly_fee          = ?,
                    image_url            = ?,
                    product_url          = ?,
                    contract_months      = ?,
                    care_plan            = ?,
                    card_benefit_monthly = ?,
                    goods_attrs          = ?,
                    updated_at           = CURRENT_TIMESTAMP
                WHERE model_no = ?
            """, (product_name, category, monthly_fee, image_url, product_url,
                  contract_months or 60, care_plan, card_benefit_monthly, goods_attrs,
                  model_no))
        else:
            conn.execute("""
                INSERT INTO subscription_products
                  (product_name, model_no, category, monthly_fee, image_url, product_url,
                   contract_months, care_plan, card_benefit_monthly, goods_attrs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, vals)


def get_subscription_recommendations(category: str | None = None) -> dict:
    """카테고리별 구독상품 TOP 5 (월 요금 기준)"""
    from config import CATEGORIES

    sql = """
        SELECT * FROM subscription_products
        WHERE is_active = 1 AND monthly_fee > 0
    """
    params = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY monthly_fee ASC"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    items = [dict(r) for r in rows]

    # 카테고리별로 그룹핑 후 TOP 5
    from collections import defaultdict
    grouped: dict[str, list] = defaultdict(list)
    for item in items:
        cat_key = item.get("category") or "etc"
        if len(grouped[cat_key]) < 5:
            grouped[cat_key].append(item)

    if category:
        cat_name = CATEGORIES.get(category, {}).get("name", category)
        return {
            "category_key":  category,
            "category_name": cat_name,
            "items":         grouped.get(category, []),
        }

    result = {}
    for key, meta in CATEGORIES.items():
        if grouped.get(key):
            result[key] = {
                "category_key":  key,
                "category_name": meta["name"],
                "items":         grouped[key],
            }
    return result
