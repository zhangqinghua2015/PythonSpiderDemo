# -*- coding: utf-8 -*-
import requests  # 导入requests包
import re
import json
from bs4 import BeautifulSoup
import html2text as ht
import pymysql
import datetime

articles = []
h = ht.HTML2Text()
h.body_width = 0
url = 'https://www.cnblogs.com/happymeng/category/1361874.html'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/70.0.3538.110 Safari/537.36'}


class Article:
    def __init__(self, title, _url):
        self.title = title
        self._url = _url
        self.cnblogId = int(re.findall('\d+', _url)[0])

    def setContent(self, content):
        self.content = content


def getArticle(_url):
    # print('getArticle start: '+datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    strhtml = requests.get(_url, headers=headers)
    soup = BeautifulSoup(strhtml.text, 'lxml')
    data = soup.select('#cb_post_title_url')
    article = Article(data[0].get_text(), data[0].get('href'))
    content = h.handle(str(soup.select("#cnblogs_post_body")[0]))
    article.setContent(content)
    # print('getArticle end: '+datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    return article


def sortKey(s):
    # 排序关键字匹配
    # 匹配开头数字序号
    if s:
        try:
            c = re.findall('\d+', re.findall('^Python爬虫入门教程 \d+-', s.title)[0])[0]
        except:
            c = -1
        return int(c)


if __name__ == "__main__":

    strhtml = requests.get(url, headers=headers)
    soup = BeautifulSoup(strhtml.text, 'lxml')
    data = soup.select('.entrylistItemTitle')

    for a in data:
        article = getArticle(a.get('href'))
        articles.append(article)

    articles.sort(key=sortKey, reverse=False)

    conn = pymysql.connect(host="", port=3306, user="", password="", db="",
                           charset="utf8mb4")
    cursor = conn.cursor()
    try:
        for article in articles:
            sql = 'insert into cnblog_article(`cnblog_id`, `title`, `url`, `content`) values(%d, \'%s\', \'%s\', \'%s\') '% (
                article.cnblogId, article.title, article._url, pymysql.escape_string(article.content)) +\
                  'on duplicate key update title=values(title),url=values(url), content=values(content)'
            print(sql)
            cursor.execute(sql)
    except Exception as e:
        print(e)
        raise e
    finally:
        cursor.close()
    conn.commit()
    # print(json.dumps(articles, default=lambda o: o.__dict__, ensure_ascii=False, sort_keys=True, indent=4))
# for item in data:
#     result = {
#         'title': item.get_text(),
#         'link': item.get('href'),
#         'ID': re.findall('\d+', item.get('href'))
#     }
# print(result)
