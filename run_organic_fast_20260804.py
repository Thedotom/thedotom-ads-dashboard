import sys

sys.path.insert(0, r"D:\광고보고서\rank")
import shopping_organic_crawler as crawler

crawler.QUERY_DELAY = (5.0, 8.0)
raise SystemExit(crawler.main())
