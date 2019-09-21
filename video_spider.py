import datetime
import json
import os
import sys

import requests
from bs4 import BeautifulSoup
import re

from Crypto.Cipher import AES

headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 8_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, '
                         'like Gecko) Version/8.0 Mobile/12B410 Safari/600.1.4'}


# 字符（十六进制）转ASCII码
def hex_to_ascii(h):
    d = int(h, 16)  # 转成十进制
    return chr(d)  # 转成ASCII码


def aes_decode(data, key):
    """AES解密
    :param key:  密钥（16.32）一般16的倍数
    :param data:  要解密的数据
    :return:  处理好的数据
    """
    iv = data[0:16]
    data = data[16:]
    cryptor = AES.new(key, AES.MODE_CBC, iv)
    plain_text = cryptor.decrypt(data)
    return plain_text.rstrip(b'\0')  # .decode("utf-8")


# 从得到的html代码中获取m3u8链接（不同网站有区别）
def get_m3u8_url1(http_s):
    ret1 = http_s.find("unescape")
    ret2 = http_s.find(".m3u8")
    ret3 = http_s.find("http", ret1, ret2)  # "unescape"和".m3u8"之间找"http"
    m3u8_url_1 = http_s[ret3: ret2 + 5]  # 未解码的m3u8链接
    # 下面对链接进行解码
    while True:
        idx = m3u8_url_1.find('%')
        if idx != -1:
            m3u8_url_1 = m3u8_url_1.replace(m3u8_url_1[idx:idx + 3], hex_to_ascii(m3u8_url_1[idx + 1:idx + 3]))
        else:
            break
    return m3u8_url_1


# 获取第二层m3u8链接
def get_m3u8_url2(m3u8_url_1):
    r1 = requests.get(m3u8_url_1)
    r1.raise_for_status()
    text = r1.text
    idx = find_lastchr(text, '\n')
    key = text[idx + 1:]  # 得到第一层m3u8中的key
    idx = find_lastchr(m3u8_url_1, '/')
    m3u8_url_2 = m3u8_url_1[:idx + 1] + key  # 组成第二层的m3u8链接
    return m3u8_url_2


# 下载m3u8文件
def get_m3u8_file(m3u8_url, filename):
    try:
        r = requests.get(m3u8_url, headers=headers)
        f = open(filename, "w", encoding="utf-8")  # 这里要改成utf-8编码，不然默认gbk
        f.write(r.text)
        f.close()
        print("创建ts列表文件成功: " + filename)
    except Exception as e:
        print("爬取失败: " + filename)
        raise e


def find_lastchr(s, c):
    ls = []
    sum = 0
    while True:
        i = s.find(c)
        if i != -1:
            s = s[i + 1:]
            ls.append(i)
        else:
            break
    for i in range(len(ls)):
        sum += (ls[i] + 1)
    return sum - 1


# 获得密钥url
def get_key_url(filename, m3u8_url):
    f = open(filename, "r")
    line = " "  # line不能为空，不然进不去下面的循环
    idx = find_lastchr(m3u8_url, '/')
    while line:
        line = f.readline()
        if line.__contains__('EXT-X-KEY'):
            return m3u8_url[:idx + 1] + str(re.findall('".*"', line)[0]).replace('"', '')
    return ''


# 提取ts列表文件的内容，逐个拼接ts的url，形成list
def get_play_list(filename, m3u8_url):
    ls = []
    f = open(filename, "r")
    line = " "  # line不能为空，不然进不去下面的循环
    idx = find_lastchr(m3u8_url, '/')
    while line:
        line = f.readline()
        if line != '' and line[0] != '#':
            line = m3u8_url[:idx + 1] + line
            ls.append(line[:-1])  # 去掉'\n'
    return ls


# 批量下载ts文件
def load_ts(video_ts_dir, ls, key):
    root = video_ts_dir
    length = len(ls)
    try:
        if not os.path.exists(root):
            os.mkdir(root)
        start = datetime.datetime.now().timestamp()
        for i in range(length):
            ts_file_name = root + '/' + str(i).zfill(8) + ".ts"
            request_fail = True
            request_fail_times = 0
            while request_fail:
                try:
                    req_start = datetime.datetime.now().timestamp()
                    r = requests.get(ls[i], headers=headers, timeout=30)
                    with open(ts_file_name, 'wb') as f:
                        f.write(aes_decode(r.content, key))
                        f.close()
                        print(ts_file_name + " --> OK ( {} / {} ){:.2f}%, 耗时 {} ms".format(i, length, i * 100 / length, int(datetime.datetime.now().timestamp()) - int(req_start)))
                        request_fail = False
                except Exception as e:
                    print(e)
                    request_fail_times = request_fail_times + 1
                    print(ts_file_name + " --> ERROR ( {} times )".format(request_fail_times))
        print("全部ts下载完毕, 耗时" + str(int(datetime.datetime.now().timestamp()) - int(start)) + " ms : " + ts_file_name)
    except Exception as e:
        print("批量下载失败: " + path)
        raise e


# 整合所有ts文件，保存为mp4格式
def ts_to_mp4(video_dir, video_title):
    print("开始合并... : " + video_dir)
    root = video_dir
    mp4_dir = video_dir + '/mp4'
    ts_dir = video_dir + '/ts'

    os.chdir(root)
    if not os.path.exists(mp4_dir):
        os.mkdir(mp4_dir)
    # os.system("cp -R" + path + "/ts *.ts " + video_title + ".mp4")
    # os.system("mv " + video_title + ".mp4 {}".format(mp4_dir))

    # 对文件进行排序并将排序后的ts文件路径放入列表中
    path_list = os.listdir(ts_dir)
    path_list.sort()
    li = [os.path.join(ts_dir, filename) for filename in path_list]
    # 将ts路径并合成一个字符参数
    ts_files = '|'.join(li)
    # print(ts_files)

    # 指定输出文件名称
    save_mp4_file = mp4_dir + '/' + video_title + '.mp4'
    # 调取系统命令使用ffmpeg将ts合成mp4文件
    cmd = 'ffmpeg -i "concat:%s" -acodec copy -vcodec copy -absf aac_adtstoasc %s' % (ts_files, save_mp4_file)
    os.system(cmd)
    print("结束合并... : " + video_dir)


#
# def download_file(url, path):
#     with requests.get(url, headers=headers, stream=True) as r:
#         chunk_size = 1024
#         content_size = int(r.headers['content-length'])
#         print '下载开始'
#         with open(path, "wb") as f:
#             for chunk in r.iter_content(chunk_size=chunk_size):
#                 f.write(chunk)

# 后台执行可使用下面方式接收参数
# nohup python - u video_download.py https://xxxxx /root/video >> services.log 2 > & 1
# url = sys.args[1]
# path = sys.args[2]
if __name__ == '__main__':
    url = input('请输入地址：')
    path = input('请输入保存路径：')
    if path == '':
        path = '~/'

    htmlRsp = requests.get(url, headers=headers)
    soup = BeautifulSoup(htmlRsp.text, 'lxml')
    # 获取视频标题
    video_title = soup.select('.article-title')[0].get_text()
    # 获取m3u8链接，不同网站需要做不同的解析处理
    m3u8_url = str(re.findall('https.*m3u8', str(soup.select('.article-content > div')[0].get('data-item')))[0]).replace('\\', '')
    # 检查是否双层m3u8链接
    if m3u8_url.__contains__('unescape'):
        m3u8_url = get_m3u8_url2(get_m3u8_url1(m3u8_url))
    # print(m3u8_url)

    # 设置视频保存路径、m3u8文件名
    video_dir = path + '/' + video_title
    m3u8_file_name = video_dir + '/index.m3u8'
    os.chdir(path)
    if not os.path.exists(video_dir):
        os.mkdir(video_dir)
    # 获取m3u8文件
    get_m3u8_file(m3u8_url, m3u8_file_name)
    # 获取key
    key_url = get_key_url(m3u8_file_name, m3u8_url)
    key = requests.get(key_url, headers=headers).content
    # 获取ts文件url集合
    ts_list = get_play_list(m3u8_file_name, m3u8_url)
    # print(json.dumps(tsList, default=lambda o: o.__dict__, ensure_ascii=False, sort_keys=True, indent=4))
    # 下载ts文件
    load_ts(video_dir + "/ts", ts_list, key)
    # 合并ts为mp4
    ts_to_mp4(video_dir, video_title)
