# 整合所有ts文件，保存为mp4格式
import os

file_list_shell_name = 'filelist.sh'
file_list_shell = '#!/bin/bash\n' \
                  'dir=$1\n' \
                  'cd "$dir"\n' \
                  'for i in `ls`\n' \
                  'do\n' \
                  '    if [ -f "$i" ]; then\n' \
                  '        echo "file \'$i\'" >> file.txt\n' \
                  '    fi\n' \
                  'done'


def ts_to_mp4(video_dir, video_title):
    print("开始合并... : " + video_dir)
    root = video_dir
    mp4_dir = video_dir + '/mp4'
    ts_dir = video_dir + '/ts'
    file_txt = ts_dir + '/file.txt'

    os.chdir(root)
    if not os.path.exists(mp4_dir):
        os.mkdir(mp4_dir)

    # 生成脚本
    with open(video_dir + '/' + file_list_shell_name, 'wb') as f:
        f.write(file_list_shell.rstrip(b'\0'))
        f.close()

    # 执行脚本将ts文件名集合写入txt
    os.system('cd "%s" && sh filelist.sh \'%s\'' % (video_dir, ts_dir))

    # 指定输出文件名称
    save_mp4_file = mp4_dir + '/' + video_title + '.mp4'
    # 调取系统命令使用ffmpeg将ts合成mp4文件
    cmd = 'ffmpeg -f concat -i \'%s\' -c copy \'%s\'' % (file_txt, save_mp4_file)
    #print("cmd: " + cmd)
    os.system(cmd)
    print("结束合并... : " + video_dir)


if __name__ == '__main__':
    video_dir = input("请输入视频根目录：")
    video_title = input("请输入视频名称：")
    # 合并ts为mp4
    ts_to_mp4(video_dir, video_title)