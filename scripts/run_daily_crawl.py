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

    # WAL → DELETE 모드 전환 + 체크포인트
    # Vercel의 /var/task/ 는 읽기 전용 → WAL 모드면 .db-shm 생성 실패로 DB 열기 불가
    # GitHub Actions 커밋 전 반드시 DELETE 모드로 전환해야 Vercel에서 시드 DB 사용 가능
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.close()
        print(f"[DB] WAL→DELETE 모드 전환 + checkpoint 완료 → {DB_PATH}")
    except Exception as e:
        print(f"[DB] checkpoint/mode 전환 실패: {e}")


if __name__ == "__main__":
    main()
