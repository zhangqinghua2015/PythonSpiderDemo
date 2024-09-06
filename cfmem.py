import requests
from bs4 import BeautifulSoup

url = 'https://www.cfmem.com/search/label/free'  # 替换为你想爬取的网页地址
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')

# 假设我们要获取所有的链接
links = soup.find_all('a',{'rel':'bookmark'})
for link in links:
    print(link.get('href'))

response = requests.get(links[0].get('href'))
soup = BeautifulSoup(response.text, 'html.parser')
links = soup.find_all('span',{'face':'Raleway, Arial, sans-serif'})

v_type_names = ['ray', 'clash', 'mihomo', 'singbox']
for link in links:
    text = link.text
    arr = text.split('->')
    print(arr)
    response = requests.get(arr[1].strip())
    file_type = arr[1][arr[1].rindex('.'):len(arr[1])]

    for v_type_name in v_type_names:
        if v_type_name in arr[0].lower():
            with open(v_type_name + file_type, 'w') as f:
                f.write(response.text)

