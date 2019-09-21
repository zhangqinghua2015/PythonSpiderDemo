# -*- coding: utf-8 -*-
import requests  # 导入requests包
import re
import json
from bs4 import BeautifulSoup
import html2text as ht

articles = []


class Article:
    def __init__(self, title, _url):
        self.title = title
        self._url = _url

    def setContent(self, content):
        self.content = content

    def setNextUrl(self, nextUrl):
        self.nextUrl = nextUrl


def getNextArticalUrl(id):
    nexthtml = requests.get('https://www.cnblogs.com/happymeng/ajax/post/prevnext?postId=' + id, headers=headers)
    soup = BeautifulSoup(nexthtml.text, 'lxml')
    return soup.select('.p_n_p_prefix')[0].get('href')


if __name__ == "__main__":
    h = ht.HTML2Text()
    h.body_width = 0

    url = 'https://www.cnblogs.com/happymeng/p/10112343.html'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                             'Chrome/70.0.3538.110 Safari/537.36'}

    strhtml = requests.get(url, headers=headers)
    soup = BeautifulSoup(strhtml.text, 'lxml')
    data = soup.select('#cb_post_title_url')
    articleId = re.search('[0-9]+', re.search(r'cb_entryId = [0-9]+', str(soup.select('#mainContent > div > script:nth-child(4)')[0])).group()).group()

    article = Article(data[0].get_text(), data[0].get('href'))
    content = h.handle(str(soup.select("#cnblogs_post_body")[0]))
    article.setContent(content)
    article.setNextUrl(getNextArticalUrl(articleId))
    articles.append(article)
    print(json.dumps(article, default=lambda o: o.__dict__, ensure_ascii=False, sort_keys=True, indent=4))
# for item in data:
#     result = {
#         'title': item.get_text(),
#         'link': item.get('href'),
#         'ID': re.findall('\d+', item.get('href'))
#     }
# print(result)
