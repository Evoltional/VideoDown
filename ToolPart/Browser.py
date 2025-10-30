import random
from DrissionPage import ChromiumPage, ChromiumOptions

def get_browser():
    """创建并配置浏览器实例"""
    options = ChromiumOptions().auto_port()
    options.set_argument('--no-sandbox')
    options.set_argument('--disable-gpu')
    options.set_argument('--disable-dev-shm-usage')
    options.set_argument('--disable-blink-features=AutomationControlled')
    options.set_argument('--disable-infobars')
    options.set_argument('--disable-extensions')
    options.set_argument('--disable-plugins')
    options.set_argument('--disable-background-timer-throttling')
    options.set_argument('--disable-backgrounding-occluded-windows')
    options.set_argument('--disable-renderer-backgrounding')
    options.set_argument('--memory-pressure-off')
    options.set_argument('--max_old_space_size=1024')
    # options.set_argument('--headless=new')  # 根据需求启用无头模式

    # 设置用户代理
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    ]
    options.set_user_agent(random.choice(user_agents))

    return ChromiumPage(addr_or_opts=options)