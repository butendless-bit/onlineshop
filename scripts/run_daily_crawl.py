from pathlib import Path
import sys
import sqlite3

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from crawler import run_crawler, run_subscription_crawler
from database import init_db
from config import DB_PATH


def main() -> None:
    init_db()
    product_count = run_crawler()
    subscription_count = run_subscription_crawler()
    print(f"Product crawl saved: {product_count}")
    print(f"Subscription crawl saved: {subscription_count}")

    # WAL 체크포인트: 모든 WAL 데이터를 메인 DB 파일에 플러시
    # (GitHub Actions이 data/himart.db만 커밋하므로 반드시 필요)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        print(f"[DB] WAL checkpoint 완료 → {DB_PATH}")
    except Exception as e:
        print(f"[DB] WAL checkpoint 실패: {e}")


if __name__ == "__main__":
    main()
