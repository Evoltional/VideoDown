import time
from typing import Optional

from ToolPart.Logger import LogEmitter


class CloudflareByPasser:
    def __init__(self, driver, max_retries=-1, log_emitter: Optional[LogEmitter] = None):
        self.driver = driver
        self.max_retries = max_retries
        self.log_emitter = log_emitter

    def search_recursively_shadow_root_with_iframe(self, ele):
        if ele.shadow_root:
            first_child = ele.shadow_root.child()
            if first_child and first_child.tag == "iframe":
                return first_child
        else:
            for child in ele.children():
                result = self.search_recursively_shadow_root_with_iframe(child)
                if result:
                    return result
        return None

    def search_recursively_shadow_root_with_cf_input(self, ele):
        if ele.shadow_root:
            input_ele = ele.shadow_root.ele("tag:input")
            if input_ele:
                return input_ele
        else:
            for child in ele.children():
                result = self.search_recursively_shadow_root_with_cf_input(child)
                if result:
                    return result
        return None

    def locate_cf_button(self):
        button = None
        elves = self.driver.eles("tag:input")
        for ele in elves:
            if "name" in ele.attrs.keys() and "type" in ele.attrs.keys():
                if "turnstile" in ele.attrs["name"] and ele.attrs["type"] == "hidden":
                    button = ele.parent().shadow_root.child()("tag:body").shadow_root("tag:input")
                    break

        if button:
            return button
        else:
            ele = self.driver.ele("tag:body")
            iframe = self.search_recursively_shadow_root_with_iframe(ele)
            if iframe:
                button = self.search_recursively_shadow_root_with_cf_input(iframe("tag:body"))
            return button

    def log_message(self, message):
        if self.log_emitter and hasattr(self.log_emitter, 'log_signal'):
            self.log_emitter.log_signal.emit(message)  # type: ignore

    def click_verification_button(self):
        try:
            button = self.locate_cf_button()
            if button:
                self.log_message("验证按钮已找到，尝试点击...")
                button.click()
            else:
                self.log_message("未找到验证按钮")
        except Exception as e:
            self.log_message(f"点击验证按钮时出错: {e}")

    def is_bypassed(self):
        try:
            title = self.driver.title.lower()
            return "just a moment" not in title
        except Exception as e:
            self.log_message(f"检查页面标题时出错: {e}")
            return False

    def bypass(self):
        try_count = 0
        while not self.is_bypassed():
            if 0 < self.max_retries + 1 <= try_count:
                self.log_message("超过最大重试次数，绕过失败")
                break

            self.log_message(f"尝试 {try_count + 1}: 尝试绕过Cloudflare验证...")
            self.click_verification_button()

            try_count += 1
            # 使用条件等待替代固定等待
            start_time = time.time()
            while time.time() - start_time < 10:  # 最多等待10秒
                if self.is_bypassed():
                    break
                time.sleep(0.5)  # 每0.5秒检查一次

        if self.is_bypassed():
            self.log_message("成功绕过Cloudflare验证")
        else:
            self.log_message("绕过Cloudflare失败")

        return self.is_bypassed()