# pip3 install selenium
# pip3 install pyperclip
# pip3 install setuptools
# pip3 install webdriver-manager
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains  # 用于鼠标操作
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, WebDriverException
)
# import undetected_chromedriver as uc
import pyperclip  # 用于访问系统剪贴板
import time
import tempfile


# 1. 初始化驱动并加载网页
def init_driver_and_load_page(url, wait_time=10):
    driver = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="chrome-", dir="/tmp")
        print(f"使用临时用户目录：{temp_dir}")
        options = webdriver.ChromeOptions()
        # 核心：指定可写的用户数据目录
        options.add_argument(f"--user-data-dir={temp_dir}")
        # 解决Ubuntu权限问题
        options.add_argument("--no-sandbox")
        # 禁用共享内存（CI环境可能限制）
        options.add_argument("--disable-dev-shm-usage")
        # 无头模式（CI环境无GUI）
        options.add_argument("--headless=new")
        # 禁用GPU加速
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)
        # options = uc.ChromeOptions()
        # options.add_argument("--no-sandbox")
        # options.add_argument("--disable-dev-shm-usage")
        # driver = uc.Chrome(options=options)
        driver.maximize_window()  # 最大化窗口，避免
        driver.set_page_load_timeout(wait_time)
        driver.get(url)
        print(f"✅ 成功加载网页：{url}")
        return driver
    except WebDriverException as e:
        print(f"❌ 网页加载失败：{str(e)}")
        if driver:
            driver.quit()
        return None


# 2. 执行点击操作（可用于点击复制按钮）
def execute_click(driver, click_selector, target_element=None, selector_type=By.CSS_SELECTOR, wait_time=5):
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
        msg = str(e.msg)
        if "Other element would receive the click" in msg:
            print("⚠️  其他元素会接收点击，请手动关闭广告")
            try:
                driver.execute_script("arguments[0].click();", target_element)
                print(f"✅ 强制点击元素：选择器={click_selector}")
                return True
            except Exception as e:
                print(f"❌ 强制点击元素失败：{str(e)}")
        print(f"❌ 点击失败：选择器={click_selector}，错误信息：{str(e)}")
        return False


# 3. 从剪贴板获取内容（点击复制按钮后调用）
def get_clipboard_content(wait_after_click=1):
    """
    从系统剪贴板获取内容
    :param wait_after_click: 点击后等待复制完成的时间（秒）
    :return: 剪贴板内容（str）/ None（失败）
    """
    try:
        # 等待复制操作完成（根据页面响应速度调整）
        time.sleep(wait_after_click)

        # 读取剪贴板
        content = pyperclip.paste()
        if content:
            print("✅ 成功读取剪贴板内容")
            return content
        else:
            print("❌ 剪贴板内容为空，可能复制未完成")
            return None
    except Exception as e:
        print(f"❌ 读取剪贴板失败：{str(e)}")
        return None

# 鼠标悬停
def simulate_mouse_hover(driver, target_selector, selector_type=By.CSS_SELECTOR, wait_time=5):
    """
    模拟鼠标悬停在目标元素上
    :param driver: Selenium浏览器驱动实例
    :param target_selector: 目标元素的选择器
    :param selector_type: 选择器类型（默认CSS，可改为By.XPATH等）
    :param wait_time: 等待元素加载的最大时间（秒）
    :return: 目标元素实例（悬停成功）/ None（失败）
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


def find_parent_by_child_text(driver, child_text, parent_tag=None, exact_match=True, wait_time=5):
    """
    通过子元素的文本定位其父元素
    :param driver: Selenium浏览器驱动
    :param child_text: 子元素包含的文本
    :param parent_tag: 父元素的标签名（可选，如'div'、'li'，不指定则匹配所有标签）
    :param exact_match: 是否精确匹配文本（True=完全一致，False=包含即可）
    :param wait_time: 等待元素加载的时间（秒）
    :return: 父元素实例 / None（未找到）
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

# 关闭广告
def close_ad_popup(driver, wait_time=5):
    ad_close_selectors = [
        (By.CSS_SELECTOR, "#dismiss-button"),
        (By.XPATH, "//*[@id=\"dismiss-button\"]"),
        (By.XPATH, "//div[contains(text(), '关闭')]"),
        (By.XPATH, "//button[contains(text(), '关闭')]"),
        (By.XPATH, "//span[contains(text(), '关闭')]"),
        (By.XPATH, "//i[contains(@class, 'close') or contains(@class, 'icon-close')]"),
        (By.CSS_SELECTOR, ".ad-close, .popup-close, .close-btn"),
        (By.XPATH, "//div[contains(@class, 'ad-popup')]//button[last()]"),
        (By.XPATH, "//div[contains(@class, 'modal')]//span[contains(@class, 'close')]")
    ]

    try:
        for selector_type, selector in ad_close_selectors:
            if execute_click(driver, selector, selector_type, wait_time=2):
                time.sleep(1)  # 关闭后缓冲1秒
                return True
        print("ℹ️  未检测到广告弹窗，继续执行")
        return True
    except Exception as e:
        print(f"⚠️  广告关闭异常：{str(e)}，继续后续操作")
        return True

# 完整流程：加载网页 → 点击复制按钮 → 获取剪贴板内容
def full_copy_workflow(url, wait_after_click=1):
    # 步骤1：加载网页
    driver = init_driver_and_load_page(url)
    if not driver:
        return None

    time.sleep(2)
    no_passwd_button_selector = "//*[@id=\"__nuxt\"]/div/main/div[1]/div/div[1]/div/div[2]/div/div[3]/button[1]"
    # 1、点击免进
    click_no_passwd = execute_click(driver, no_passwd_button_selector, selector_type=By.XPATH)
    if not click_no_passwd:
        driver.quit()
        return None

    # 2、等待20秒
    time.sleep(13)

    # close_ad_popup(driver)
    # ad_button_selector = "/html/body/ins[2]/div[1]//ins/span/svg"
    # click_ad = execute_click(driver, ad_button_selector, selector_type=By.XPATH)
    # if not click_ad:
    #     driver.quit()
    #     return None

    # 3、点击查看
    watch_button_selector = "//*[@id=\"reka-dialog-content-v-0-0-0-0-0\"]/div[2]/div/button"
    click_watch = execute_click(driver, watch_button_selector, selector_type=By.XPATH)
    if not click_watch:
        driver.quit()
        return None

    time.sleep(2)
    # 4、点击全选
    select_all_button_selector = "#v-0-0-0-0-4"
    click_select_all = execute_click(driver, select_all_button_selector)
    if not click_select_all:
        driver.quit()
        return None

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
    time.sleep(12)

    # 9、点击复制按钮
    copy_button_selector = "//button[text()='复制']"
    click_success = execute_click(driver, copy_button_selector, selector_type=By.XPATH)
    if not click_success:
        driver.quit()
        return None

    # 10、获取剪贴板内容
    clipboard_content = get_clipboard_content(wait_after_click)

    # 关闭浏览器
    driver.quit()
    return clipboard_content


# 示例使用
if __name__ == "__main__":
    # 配置参数（根据目标页面修改）
    target_url = "https://v2rayse.com/live-node"
    # 若按钮用XPath定位，可改为：
    # copy_button_selector = '//button[contains(text(), "复制")]'
    # selector_type = By.XPATH
    # 执行完整流程
    result = full_copy_workflow(url=target_url, wait_after_click=1.5)

    # 输出结果
    if result:
        print(f"\n📋 复制的内容为：\n{result}")
        result = (result.replace("  - GEOIP,CN,🎯 全球直连", "  - DOMAIN-KEYWORD,google,🚀 节点选择\n  - GEOIP,CN,🎯 全球直连")
                  .replace('\n  - name: 🐟 漏网之鱼\n    type: select\n    proxies:', '\n  - name: 🐟 漏网之鱼\n    type: select\n    proxies:\n      - DIRECT'))
        print(f"📋 修改后的内容：\n{result}")
        with open(datetime.now().strftime('%Y%m%d%H')+"/mihomo.yaml", 'w') as f:
            f.write(result)
    else:
        print("❌ 复制失败")