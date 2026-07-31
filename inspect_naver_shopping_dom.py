from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import urllib.parse
import time

options = Options()
options.add_argument("--headless=new")
options.add_argument("--lang=ko-KR")
options.add_argument("--window-size=1440,3000")
driver = webdriver.Chrome(options=options)
driver.get(
    "https://m.search.naver.com/search.naver?where=m&query="
    + urllib.parse.quote("돌답례품")
)
time.sleep(3)
elements = driver.find_elements("css selector", "[href*='11562165854']")
print("matches", len(elements))
for index, element in enumerate(elements[:10]):
    print(
        index,
        element.tag_name,
        element.get_attribute("class"),
        element.get_attribute("href"),
        element.text[:80],
    )
target = elements[-1]
li = target.find_element("xpath", "ancestor::li[1]")
ul = li.find_element("xpath", "..")
children = ul.find_elements("xpath", "./li")
print("SHOPPING_RANK", children.index(li) + 1, "OF", len(children))
node = target
for depth in range(8):
    node = node.find_element("xpath", "..")
    print("PARENT", depth + 1, node.tag_name, node.get_attribute("class"))
all_links = driver.find_elements("css selector", "a[href*=\'smartstore.naver.com\'][href*=\'/products/\']")
seen = []
for link in all_links:
    href = link.get_attribute("href") or ""
    product_id = href.split("/products/")[-1].split("?")[0]
    if product_id and product_id not in seen:
        seen.append(product_id)
print("unique smartstore products", len(seen), "target position", seen.index("11562165854") + 1)
print(seen[:30])
driver.quit()
