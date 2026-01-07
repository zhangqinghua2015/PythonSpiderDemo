"""
V2RaySE 网站爬虫工具
用于自动化获取 V2Ray 节点配置信息

该脚本使用 Selenium 自动化浏览器操作，从 V2RaySE 网站获取节点配置信息，
并将其保存为 mihomo 格式的配置文件。

依赖安装命令
pip3 install selenium selenium-wire blinker==1.7.0 pyperclip setuptools webdriver-manager
"""

# 标准库导入
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
from urllib.parse import parse_qs

# 第三方库导入
import pyperclip  # 用于访问系统剪贴板
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire import webdriver

# 常量定义
NO_PASSWD_BUTTON_TEXT = "免密码进入"
NO_PASSWD_BUTTON_SELECTOR = "//*[@id=\"__nuxt\"]/div/main/div[1]/div/div[1]/div/div[2]/div/div[3]/button[1]"
WATCH_BUTTON_TEXT = "查看节点"
WATCH_BUTTON_SELECTOR = "//*[@id=\"reka-dialog-content-v-0-0-0-0-0\"]/div[2]/div/button"
WAIT_AFTER_NO_PASSWD = 13  # 秒
MAX_RETRIES = 1  # 最大重试次数

def init_driver_and_load_page(url, wait_time=30):
    """
    初始化浏览器驱动并加载指定网页
    
    Args:
        url (str): 要加载的网页URL
        wait_time (int): 页面加载超时时间（秒）
        
    Returns:
        webdriver.Chrome: 浏览器驱动实例，失败时返回None
    """
    driver = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="chrome-", dir="/tmp")
        print(f"使用临时用户目录：{temp_dir}")
        
        options = webdriver.ChromeOptions()
        # 核心：指定可写的用户数据目录
        options.add_argument(f"--user-data-dir={temp_dir}")
        # 解决Ubuntu权限问题
        options.add_argument("--no-sandbox")
        # 延长渲染器超时时间
        options.add_argument("--renderer-timeout=60")
        # 使用更灵活的页面加载策略
        options.page_load_strategy = 'eager'  # 等待DOM加载完成，不等待资源完全加载
        
        # 浏览器级别的广告拦截选项
        options.add_argument("--disable-popup-blocking")  # 禁用弹出窗口
        options.add_argument("--disable-notifications")  # 禁用通知
        options.add_argument("--disable-media-autoplay")  # 禁用媒体自动播放
        options.add_argument("--disable-background-timer-throttling")  # 禁用后台计时器节流
        
        # 禁用广告跟踪和分析
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        # 阻止第三方Cookie（广告常用的跟踪手段）
        options.add_argument("--disable-third-party-cookies")
        options.add_argument("--disable-site-isolation-trials")
        
        # 启用隐私沙箱（现代广告拦截）
        options.add_argument("--enable-features=PrivacySandboxSettings3")
        
        # CI环境强制启用无头模式
        if os.getenv("CI", "false").lower() == "true":
            options.add_argument("--headless=new")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            # 增加窗口大小，避免元素定位问题
            options.add_argument("--window-size=1280,720")
        
        driver = webdriver.Chrome(options=options)
        
        driver.maximize_window()  # 最大化窗口
        driver.set_page_load_timeout(wait_time)
        driver.get(url)
        print(f"✅ 成功加载网页：{url}")
        return driver
    except WebDriverException as e:
        print(f"❌ 网页加载失败：{str(e)}")
        if driver:
            driver.quit()
        return None


def execute_click(driver, click_selector, target_element=None, selector_type=By.CSS_SELECTOR, wait_time=10):
    """
    执行元素点击操作
    
    Args:
        driver: 浏览器驱动实例
        click_selector (str): 元素选择器
        target_element: 目标元素实例（可选）
        selector_type: 选择器类型，默认为CSS选择器
        wait_time (int): 等待超时时间（秒）
        
    Returns:
        bool: 点击成功返回True，失败返回False
    """
    if not driver:
        print(f"❌ 驱动实例为空，无法执行点击")
        return False
    
    try:
        wait = WebDriverWait(driver, wait_time)
        if not target_element:
            target_element = wait.until(
                EC.element_to_be_clickable((selector_type, click_selector))
            )
        
        target_element.click()
        print(f"✅ 成功点击元素：选择器={click_selector}")
        return True
    except (TimeoutException, NoSuchElementException, Exception) as e:
        msg = str(e)
        if "Other element would receive the click" in msg:
            print("⚠️  其他元素会接收点击，强制点击元素")
            try:
                driver.execute_script("arguments[0].click();", target_element)
                print(f"✅ 强制点击元素：选择器={target_element}")
                return True
            except Exception as js_error:
                print(f"❌ 强制点击元素失败：{str(js_error)}")
        else:
            print(f"❌ 点击失败：选择器={click_selector}，错误信息：{str(e)}")
        return False


def get_clipboard_content(wait_after_click=2, max_retries=3):
    """
    从系统剪贴板获取内容（优化版：兼容本地和CI环境，支持重试）
    
    Args:
        wait_after_click (int): 点击后等待复制完成的时间（秒）
        max_retries (int): 读取失败时的重试次数
        
    Returns:
        str: 剪贴板内容，失败时返回None
    """
    try:
        # 等待复制操作完成（CI环境建议延长至2-3秒）
        time.sleep(wait_after_click)
        
        # 检测CI环境
        is_ci = os.getenv("CI", "false").lower() == "true"
        
        # 重试机制：多次读取避免偶发失败
        for retry in range(max_retries):
            try:
                if is_ci:
                    # CI环境：使用xclip命令读取剪贴板
                    result = subprocess.run(
                        ["xclip", "-selection", "clipboard", "-o"],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    
                    if result.returncode == 0:
                        content = result.stdout.strip()
                        if content:
                            print(f"✅ CI环境：第{retry + 1}次读取剪贴板成功")
                            return content
                else:
                    # 本地环境：使用pyperclip读取剪贴板
                    content = pyperclip.paste().strip()
                    if content:
                        print(f"✅ 本地环境：第{retry + 1}次读取剪贴板成功")
                        return content
                
                # 若内容为空，等待后重试
                if retry < max_retries - 1:
                    time.sleep(1)
                    print(f"🔄 第{retry + 1}次读取为空，准备重试...")
                    
            except Exception as e:
                print(f"⚠️  第{retry + 1}次读取失败：{str(e)}")
                if retry < max_retries - 1:
                    time.sleep(1)
        
        print("❌ 所有重试均失败，剪贴板内容为空或无法读取")
        return None
        
    except Exception as e:
        print(f"❌ 剪贴板操作整体失败：{str(e)}")
        return None


def simulate_mouse_hover(driver, target_selector, selector_type=By.CSS_SELECTOR, wait_time=10):
    """
    模拟鼠标悬停在目标元素上
    
    Args:
        driver: Selenium浏览器驱动实例
        target_selector (str): 目标元素的选择器
        selector_type: 选择器类型，默认为CSS选择器
        wait_time (int): 等待元素加载的最大时间（秒）
        
    Returns:
        WebElement: 目标元素实例（悬停成功）或None（失败）
    """
    try:
        # 等待目标元素可见且可交互
        target_element = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((selector_type, target_selector))
        )
        
        # 初始化ActionChains，模拟鼠标悬停
        actions = ActionChains(driver)
        actions.move_to_element(target_element).perform()  # 执行悬停动作
        print(f"✅ 已成功将鼠标悬停在元素上（选择器：{target_selector}）")
        return target_element
        
    except TimeoutException:
        print(f"❌ 超时错误：等待{wait_time}秒后未找到目标元素")
        return None
    except NoSuchElementException:
        print(f"❌ 元素未找到：选择器={target_selector}")
        return None
    except Exception as e:
        print(f"❌ 悬停操作失败：{str(e)}")
        return None


def find_parent_by_child_text(driver, child_text, parent_tag=None, exact_match=True, wait_time=10):
    """
    通过子元素的文本定位其父元素
    
    Args:
        driver: Selenium浏览器驱动
        child_text (str): 子元素包含的文本
        parent_tag (str): 父元素的标签名（可选，如'div'、'li'，不指定则匹配所有标签）
        exact_match (bool): 是否精确匹配文本（True=完全一致，False=包含即可）
        wait_time (int): 等待元素加载的时间（秒）
        
    Returns:
        WebElement: 父元素实例或None（未找到）
    """
    try:
        # 构建XPath表达式：先定位子元素，再取父元素
        if exact_match:
            # 精确匹配文本
            child_xpath = f"//*[text()='{child_text}']"
        else:
            # 模糊匹配（包含文本）
            child_xpath = f"//*[contains(text(), '{child_text}')]"
        
        # 拼接父元素XPath（parent::* 表示任意标签的父元素，可指定标签如parent::div）
        if parent_tag:
            parent_xpath = f"{child_xpath}/parent::{parent_tag}"
        else:
            parent_xpath = f"{child_xpath}/parent::*"  # 不限制父元素标签
        
        # 等待父元素出现并返回
        parent_element = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.XPATH, parent_xpath))
        )
        print(f"✅ 找到子元素文本为'{child_text}'的父元素（XPath：{parent_xpath}）")
        return parent_element
        
    except TimeoutException:
        print(f"❌ 超时：未找到子元素文本为'{child_text}'的父元素")
        return None
    except Exception as e:
        print(f"❌ 定位失败：{str(e)}")
        return None


def find_element_by_text(driver, text, exact_match=True, element_tag="*", wait_time=10):
    """
    通过文本内容直接查找元素
    
    Args:
        driver: Selenium浏览器驱动
        text (str): 要查找的文本内容
        exact_match (bool): 是否精确匹配文本（True=完全一致，False=包含即可）
        element_tag (str): 元素标签名（默认为'*'，匹配所有标签）
        wait_time (int): 等待元素加载的时间（秒）
        
    Returns:
        WebElement: 找到的元素实例或None（未找到）
    """
    try:
        # 构建XPath表达式
        if exact_match:
            # 精确匹配文本
            xpath = f"//{element_tag}[text()='{text}']"
        else:
            # 模糊匹配（包含文本）
            xpath = f"//{element_tag}[contains(text(), '{text}')]"
        
        # 等待元素出现并返回
        element = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        print(f"✅ 找到文本为'{text}'的元素（XPath：{xpath}）")
        return element
        
    except TimeoutException:
        print(f"❌ 超时：未找到文本为'{text}'的元素")
        return None
    except Exception as e:
        print(f"❌ 查找元素失败：{str(e)}")
        return None


def capture_post_with_selenium_wire(driver, button_selector, target_keyword, timeout=30):
    """
    使用 selenium-wire 捕获指定的 POST 请求
    
    Args:
        driver: Selenium 驱动实例
        button_selector (str): 触发请求的按钮选择器
        target_keyword (str): 请求 URL 中包含的关键字
        timeout (int): 捕获请求的超时时间（秒）
        
    Returns:
        dict: 请求信息字典或None（失败）
    """
    try:
        # 2. 等待按钮可点击并点击
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, button_selector))
        )
        button.click()
        print(f"✅ 已点击按钮：{button_selector}")
        
        # 3. 等待请求完成并筛选POST请求
        start_time = time.time()
        while time.time() - start_time < timeout:
            # 遍历所有请求
            for request in driver.requests:
                if request.method == "POST" and target_keyword in request.url:
                    # 解析请求体
                    body = request.body.decode("utf-8") if request.body else ""
                    parsed_body = {}
                    if body:
                        try:
                            parsed_body = json.loads(body)
                        except json.JSONDecodeError:
                            parsed_body = parse_qs(body)
                            parsed_body = {k: v[0] for k, v in parsed_body.items()}
                    
                    return {
                        "url": request.url,
                        "method": request.method,
                        "headers": dict(request.headers),
                        "body": parsed_body
                    }
            time.sleep(0.5)
        
        print(f"❌ 超时未捕获到POST请求（{timeout}秒）")
        return None
        
    except Exception as e:
        print(f"❌ 操作失败：{str(e)}")
        return None


def click_button_with_retry(driver, button_text, button_selector, max_retry=1, find_parent=True):
    """
    点击按钮的通用函数，支持重试机制
    
    Args:
        driver: 浏览器驱动实例
        button_text (str): 按钮文本
        button_selector (str): 按钮选择器
        max_retry (int): 最大重试次数
        find_parent (bool): 是否查找父元素，默认为True
        
    Returns:
        bool: 点击成功返回True，失败返回False
    """
    retry_count = 0
    while retry_count <= max_retry:
        try:
            # 根据find_parent参数决定查找方式
            button = None
            if find_parent:
                # 查找文本元素的父元素
                button = find_parent_by_child_text(driver, button_text, "button")
            else:
                # 直接查找文本元素本身
                button = find_element_by_text(driver, button_text, element_tag="button")
            
            # 使用execute_click函数执行点击
            if execute_click(driver, button_selector, button, selector_type=By.XPATH):
                return True
            
            print(f"🔄 未找到按钮 '{button_text}'，正在重试... (尝试 {retry_count+1}/{max_retry+1})")
            retry_count += 1
            
            # 如果不是最后一次重试，等待后继续
            if retry_count <= max_retry:
                time.sleep(5)  # 重试等待时间
        except Exception as e:
            print(f"⚠️  点击按钮 '{button_text}' 时发生异常: {e}")
            retry_count += 1
            if retry_count <= max_retry:
                time.sleep(5)
    
    return False


def full_copy_workflow(url, wait_after_click=1):
    """
    完整流程：加载网页 → 点击复制按钮 → 获取剪贴板内容
    
    Args:
        url (str): 要加载的网页URL
        wait_after_click (int): 点击后等待复制完成的时间（秒）
        
    Returns:
        str: 复制的内容或None（失败）
    """
    # 步骤1：加载网页
    driver = init_driver_and_load_page(url)
    if not driver:
        return None
    
    # 等待页面完全加载完成
    print("⏳ 等待页面所有资源加载完成...")
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    print("✅ 页面已完全加载")
    time.sleep(20)
    
    # 1、点击免密码进入按钮
    print("📌 正在点击'免密码进入'按钮...")
    if not click_button_with_retry(driver, NO_PASSWD_BUTTON_TEXT, NO_PASSWD_BUTTON_SELECTOR):
        print("❌ 点击'免密码进入'按钮失败")
        driver.quit()
        return None
    
    # 2、等待页面加载
    print(f"⏳ 等待 {WAIT_AFTER_NO_PASSWD} 秒让页面加载完成...")
    time.sleep(WAIT_AFTER_NO_PASSWD)
    
    # 3、点击查看节点按钮（支持重试机制）
    print("📌 准备点击'查看节点'按钮...")
    retry_count = 0
    click_watch_success = False
    
    while retry_count <= MAX_RETRIES and not click_watch_success:
        click_watch_success = click_button_with_retry(driver, WATCH_BUTTON_TEXT, WATCH_BUTTON_SELECTOR, find_parent=False)
        
        if click_watch_success:
            break
        elif retry_count < MAX_RETRIES:
            # 未找到"查看节点"按钮，重新点击"免密码进入"
            print("🔄 '查看节点'按钮未找到，正在重新点击'免密码进入'...")
            if not click_button_with_retry(driver, NO_PASSWD_BUTTON_TEXT, NO_PASSWD_BUTTON_SELECTOR):
                print("❌ 重新点击'免密码进入'按钮失败")
                driver.quit()
                return None
            
            print(f"⏳ 等待 {WAIT_AFTER_NO_PASSWD} 秒后再次尝试...")
            time.sleep(WAIT_AFTER_NO_PASSWD)
            retry_count += 1
        else:
            break
    
    if not click_watch_success:
        print("❌ 重试次数用尽，仍未找到'查看节点'按钮")
        driver.quit()
        return None
    
    time.sleep(4)
    # 4、点击全选
    select_all_button_selector = "#v-0-0-0-0-4"
    click_select_all = execute_click(driver, select_all_button_selector)
    if not click_select_all:
        driver.quit()
        return None
    
    time.sleep(1)
    # 5、点击操作
    operate_button_selector = "#reka-dropdown-menu-trigger-v-0-0-0-0-3"
    click_operate = execute_click(driver, operate_button_selector)
    if not click_operate:
        driver.quit()
        return None
    
    convert_div = find_parent_by_child_text(driver, "节点转换", "*/parent::button")
    # 6、点击转换
    convert_button_selector = "#" + convert_div.get_attribute("id")
    click_convert = simulate_mouse_hover(driver, convert_button_selector)
    if not click_convert:
        driver.quit()
        return None
    click_convert = execute_click(driver, convert_button_selector)
    if not click_convert:
        driver.quit()
        return None
    
    mihomo_button = find_parent_by_child_text(driver, "Mihomo", "*/parent::button")
    # 7、点击mihomo
    mihomo_button_selector = ""
    click_mihomo = execute_click(driver, mihomo_button_selector, target_element=mihomo_button)
    if not click_mihomo:
        driver.quit()
        return None
    
    # 8、等待10秒
    time.sleep(4)
        
    params = capture_post_with_selenium_wire(driver, button_selector="//button[text()='订阅']",
                                             target_keyword="/text/upload")
    clipboard_content = params['body'].get('text')
      
    # 关闭浏览器
    driver.quit()
    return clipboard_content


def save_result(result, file_name_prefix=""):
    """
    保存结果到文件
    
    Args:
        result (str): 要保存的内容
        file_name_prefix (str): 文件名前缀
    """
    # 输出结果
    if result:
        # print(f"\n📋 复制的内容为：\n{result}")
        result = (
            result.replace("  - GEOIP,CN,🎯 全球直连", "  - DOMAIN-KEYWORD,google,🚀 节点选择\n  - GEOIP,CN,🎯 全球直连")
            .replace('\n  - name: 🐟 漏网之鱼\n    type: select\n    proxies:',
                     '\n  - name: 🐟 漏网之鱼\n    type: select\n    proxies:\n      - DIRECT'))
        # print(f"📋 修改后的内容：\n{result}")
        # file_path = datetime.now().strftime('%Y%m%d%H') + "/" + file_name_prefix + "mihomo.yaml"
        file_path = file_name_prefix + "mihomo.yaml"
        # 1. 提取文件所在的目录路径
        dir_path = os.path.dirname(file_path)
        # 2. 若目录不存在，则递归创建（包括所有父目录）
        if dir_path and dir_path.strip() and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)  # exist_ok=True 避免目录已存在时的错误
            print(f"✅ 文件夹不存在，已自动创建：{dir_path}")
        with open(file_path, 'w') as f:
            f.write(result)
    else:
        print("❌ 复制失败")


if __name__ == "__main__":
    """
    主函数：执行完整的节点获取流程
    """
    # 配置参数（根据目标页面修改）
    target_url = "https://v2rayse.com/live-node"
    # 若按钮用XPath定位，可改为：
    # copy_button_selector = '//button[contains(text(), "复制")]'
    # selector_type = By.XPATH
    # 执行完整流程
    result = full_copy_workflow(url=target_url, wait_after_click=1.5)
    save_result(result, "live_")

    free_url = "https://v2rayse.com/free-node"
    result = full_copy_workflow(url=free_url, wait_after_click=1.5)
    save_result(result, "free_")
