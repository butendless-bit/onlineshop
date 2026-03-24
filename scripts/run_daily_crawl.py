from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from crawler import run_crawler, run_subscription_crawler
from database import init_db


def main() -> None:
    init_db()
    product_count = run_crawler()
    subscription_count = run_subscription_crawler()
    print(f"Product crawl saved: {product_count}")
    print(f"Subscription crawl saved: {subscription_count}")


if __name__ == "__main__":
    main()
