import sqlite3
import os
import shutil
from config import DB_PATH, DB_SEED


def _db_has_products(path: str) -> bool:
    """DB 파일이 존재하고 products 데이터가 있으면 True.
    immutable=1 로 열어 read-only 파일시스템(Vercel /var/task/)에서도 안전하게 읽음.
    """
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    try:
        # immutable=1: SQLite가 -shm/-wal 파일 생성 시도를 하지 않음 (읽기 전용 FS 대응)
        uri = f"file:{path}?immutable=1"
        conn = sqlite3.connect(uri, uri=True)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='products'"
        ).fetchone()
        if not row:
            conn.close()
            return False
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        conn.close()
        return int(count) > 0
    except Exception:
        return False


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    # Vercel: 시드 DB → /tmp 복사 (데이터가 없을 때만 복사)
    if os.environ.get("VERCEL") and not _db_has_products(DB_PATH):
        if _db_has_products(DB_SEED):
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            shutil.copy2(DB_SEED, DB_PATH)
            print(f"[DB] 시드 복사 완료: {DB_SEED} → {DB_PATH}")
        else:
            print(f"[DB] 경고: 시드 DB에 데이터 없음 ({DB_SEED})")

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

            CREATE INDEX IF NOT EXISTS idx_price_model    ON price_history(model_no);
            CREATE INDEX IF NOT EXISTS idx_price_crawled  ON price_history(crawled_at);
            CREATE INDEX IF NOT EXISTS idx_comp_model     ON competitor_prices(model_no);
            CREATE INDEX IF NOT EXISTS idx_sub_active     ON subscription_products(is_active);
            CREATE INDEX IF NOT EXISTS idx_prod_category  ON products(category);
            CREATE INDEX IF NOT EXISTS idx_prod_url       ON products(product_url);
        """)
        # 기존 DB에 없을 수 있는 컬럼 안전 추가
        for col_sql in [
            "ALTER TABLE products ADD COLUMN review_count INTEGER DEFAULT 0",
            "ALTER TABLE products ADD COLUMN spec TEXT DEFAULT '{}'",
            "ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1",
            "ALTER TABLE products ADD COLUMN goods_no TEXT DEFAULT ''",
            # SQLite ALTER TABLE은 non-constant DEFAULT(CURRENT_TIMESTAMP) 미지원 → default 없이 추가
            "ALTER TABLE products ADD COLUMN last_seen_at DATETIME",
            # 인기도 순위 (e-himart WEIGHT 정렬 기반, 낮을수록 인기). 미수집 = NULL
            "ALTER TABLE products ADD COLUMN popularity_rank INTEGER",
        ]:
            try:
                conn.execute(col_sql)
            except Exception:
                pass  # 이미 존재하면 무시
        # is_active 인덱스
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prod_active ON products(is_active)")
        for col_sql in [
            "ALTER TABLE subscription_products ADD COLUMN care_plan TEXT",
            "ALTER TABLE subscription_products ADD COLUMN card_benefit_monthly INTEGER",
            "ALTER TABLE subscription_products ADD COLUMN goods_attrs TEXT DEFAULT '[]'",
            "ALTER TABLE subscription_products ADD COLUMN lotte_card_price INTEGER DEFAULT 0",
            "ALTER TABLE subscription_products ADD COLUMN hybrid_price INTEGER DEFAULT 0",
            "ALTER TABLE subscription_products ADD COLUMN cashback_amount INTEGER DEFAULT 0",
            "ALTER TABLE subscription_products ADD COLUMN benefit_desc TEXT DEFAULT ''",
            "ALTER TABLE subscription_products ADD COLUMN care_benefit TEXT DEFAULT ''",
            "ALTER TABLE subscription_products ADD COLUMN period_start TEXT DEFAULT ''",
            "ALTER TABLE subscription_products ADD COLUMN period_end TEXT DEFAULT ''",
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


def upsert_product(model_no, product_name, category, product_url, image_url,
                    spec="{}", goods_no="", is_active=1, popularity_rank=None):
    """popularity_rank: 이번 크롤에서 관측한 WEIGHT 순위(1부터). None이면 순위 비갱신.
    여러 키워드에서 등장 시 더 인기 있는 값(= 더 작은 순위)로만 갱신된다.
    """
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO products (model_no, product_name, category, product_url, image_url,
                                  spec, goods_no, is_active, last_seen_at, popularity_rank)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(model_no) DO UPDATE SET
                product_name = excluded.product_name,
                product_url  = excluded.product_url,
                image_url    = excluded.image_url,
                spec         = excluded.spec,
                goods_no     = excluded.goods_no,
                is_active    = excluded.is_active,
                last_seen_at = CURRENT_TIMESTAMP,
                -- 순위는 더 낮은(=더 인기) 값으로만 갱신 · 새 값이 NULL이면 유지
                popularity_rank = CASE
                    WHEN excluded.popularity_rank IS NULL THEN products.popularity_rank
                    WHEN products.popularity_rank IS NULL THEN excluded.popularity_rank
                    WHEN excluded.popularity_rank < products.popularity_rank THEN excluded.popularity_rank
                    ELSE products.popularity_rank
                END,
                updated_at   = CURRENT_TIMESTAMP
        """, (model_no, product_name, category, product_url, image_url, spec, goods_no, is_active, popularity_rank))


def update_popularity_rank(model_no: str, rank: int):
    """WEIGHT 정렬에서 관측한 순위를 기록. 더 작은(=더 인기) 값으로만 갱신."""
    if not model_no or not rank:
        return
    with get_conn() as conn:
        conn.execute("""
            UPDATE products
               SET popularity_rank = CASE
                   WHEN popularity_rank IS NULL THEN ?
                   WHEN ? < popularity_rank THEN ?
                   ELSE popularity_rank
               END,
               updated_at = CURRENT_TIMESTAMP
             WHERE model_no = ?
        """, (rank, rank, rank, model_no))


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
            p.review_count, p.spec, p.popularity_rank,
            l.original_price, l.sale_price, l.benefit_price, l.crawled_at,
            prev.benefit_price AS prev_benefit_price
        FROM products p
        JOIN latest l ON l.model_no = p.model_no AND l.rn = 1
        LEFT JOIN prev  ON prev.model_no = p.model_no AND prev.rn = 1
        WHERE p.is_active = 1
    """
    params = []
    if category:
        sql += " AND p.category = ?"
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


def get_alltime_lows(model_nos: list) -> dict:
    """여러 모델의 역대 최저가를 한 번의 쿼리로 조회 (N+1 방지)"""
    if not model_nos:
        return {}
    placeholders = ",".join("?" * len(model_nos))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT model_no, MIN(benefit_price) AS min_price FROM price_history"
            f" WHERE model_no IN ({placeholders}) GROUP BY model_no",
            model_nos,
        ).fetchall()
    return {row["model_no"]: row["min_price"] for row in rows}


def get_competitor_prices(model_nos: list) -> dict:
    """여러 모델의 최신 네이버 최저가를 한 번의 쿼리로 조회 (N+1 방지)"""
    if not model_nos:
        return {}
    placeholders = ",".join("?" * len(model_nos))
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT model_no, naver_price FROM competitor_prices
                WHERE (model_no, crawled_at) IN (
                    SELECT model_no, MAX(crawled_at) FROM competitor_prices
                    WHERE model_no IN ({placeholders}) GROUP BY model_no
                )""",
            model_nos,
        ).fetchall()
    return {row["model_no"]: row["naver_price"] for row in rows}


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


def mark_unseen_inactive(category: str, seen_model_nos: set):
    """이번 크롤링에서 발견되지 않은 상품을 판매중지(is_active=0)로 마킹.
    seen_model_nos: 이번 크롤에서 수집된 model_no 집합.
    """
    if not seen_model_nos:
        return 0
    with get_conn() as conn:
        # 해당 카테고리에서 이번에 안 보인 상품만 비활성화
        placeholders = ",".join("?" * len(seen_model_nos))
        cur = conn.execute(
            f"""UPDATE products SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE category = ? AND is_active = 1
                AND model_no NOT IN ({placeholders})""",
            [category] + list(seen_model_nos),
        )
        return cur.rowcount


def mark_product_inactive(model_no: str):
    """개별 상품 판매중지 처리"""
    with get_conn() as conn:
        conn.execute(
            "UPDATE products SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE model_no = ?",
            (model_no,)
        )


def get_inactive_count(category: str | None = None) -> int:
    """판매중지 상품 수 조회"""
    sql = "SELECT COUNT(*) AS c FROM products WHERE is_active = 0"
    params = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    with get_conn() as conn:
        return conn.execute(sql, params).fetchone()["c"]


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
               "contract_months", "install_fee", "image_url", "product_url", "notes", "is_active",
               "care_plan", "card_benefit_monthly", "lotte_card_price", "hybrid_price",
               "cashback_amount", "benefit_desc", "care_benefit", "period_start", "period_end"}
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
        if len(grouped[cat_key]) < 10:
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
