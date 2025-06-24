# import os
# import random
# import sys
# import threading
# import time
# from typing import Optional, List
# from concurrent.futures import ThreadPoolExecutor, as_completed
# import requests
# from DrissionPage import ChromiumPage, ChromiumOptions
# from PyQt5.QtCore import Qt, pyqtSignal, QObject
# from PyQt5.QtGui import QFont
# from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
#                              QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox, QScrollArea, QFrame)
#
#
# class LogEmitter(QObject):
#     log_signal = pyqtSignal(str)  # type: ignore
#
#
# class CloudflareByPasser:
#     def __init__(self, driver: ChromiumPage, max_retries=-1, log_emitter: Optional[LogEmitter] = None):
#         self.driver = driver
#         self.max_retries = max_retries
#         self.log_emitter = log_emitter
#
#     def search_recursively_shadow_root_with_iframe(self, ele):
#         if ele.shadow_root:
#             first_child = ele.shadow_root.child()
#             if first_child and first_child.tag == "iframe":
#                 return first_child
#         else:
#             for child in ele.children():
#                 result = self.search_recursively_shadow_root_with_iframe(child)
#                 if result:
#                     return result
#         return None
#
#     def search_recursively_shadow_root_with_cf_input(self, ele):
#         if ele.shadow_root:
#             input_ele = ele.shadow_root.ele("tag:input")
#             if input_ele:
#                 return input_ele
#         else:
#             for child in ele.children():
#                 result = self.search_recursively_shadow_root_with_cf_input(child)
#                 if result:
#                     return result
#         return None
#
#     def locate_cf_button(self):
#         button = None
#         elves = self.driver.eles("tag:input")
#         for ele in elves:
#             if "name" in ele.attrs.keys() and "type" in ele.attrs.keys():
#                 if "turnstile" in ele.attrs["name"] and ele.attrs["type"] == "hidden":
#                     button = ele.parent().shadow_root.child()("tag:body").shadow_root("tag:input")
#                     break
#
#         if button:
#             return button
#         else:
#             ele = self.driver.ele("tag:body")
#             iframe = self.search_recursively_shadow_root_with_iframe(ele)
#             if iframe:
#                 button = self.search_recursively_shadow_root_with_cf_input(iframe("tag:body"))
#             return button
#
#     def log_message(self, message):
#         if self.log_emitter and hasattr(self.log_emitter, 'log_signal'):
#             self.log_emitter.log_signal.emit(message)  # type: ignore
#
#     def click_verification_button(self):
#         try:
#             button = self.locate_cf_button()
#             if button:
#                 self.log_message("验证按钮已找到，尝试点击...")
#                 button.click()
#             else:
#                 self.log_message("未找到验证按钮")
#         except Exception as e:
#             self.log_message(f"点击验证按钮时出错: {e}")
#
#     def is_bypassed(self):
#         try:
#             title = self.driver.title.lower()
#             return "just a moment" not in title
#         except Exception as e:
#             self.log_message(f"检查页面标题时出错: {e}")
#             return False
#
#     def bypass(self):
#         try_count = 0
#         while not self.is_bypassed():
#             if 0 < self.max_retries + 1 <= try_count:
#                 self.log_message("超过最大重试次数，绕过失败")
#                 break
#
#             self.log_message(f"尝试 {try_count + 1}: 尝试绕过Cloudflare验证...")
#             self.click_verification_button()
#
#             try_count += 1
#             # 使用条件等待替代固定等待
#             start_time = time.time()
#             while time.time() - start_time < 10:  # 最多等待10秒
#                 if self.is_bypassed():
#                     break
#                 time.sleep(0.5)  # 每0.5秒检查一次
#
#         if self.is_bypassed():
#             self.log_message("成功绕过Cloudflare验证")
#         else:
#             self.log_message("绕过Cloudflare失败")
#
#         return self.is_bypassed()
#
#
# def get_browser():
#     """创建并配置浏览器实例"""
#     options = ChromiumOptions().auto_port()
#     options.set_argument('--no-sandbox')
#     options.set_argument('--disable-gpu')
#     options.set_argument('--disable-dev-shm-usage')
#     options.set_argument('--disable-blink-features=AutomationControlled')
#     options.set_argument('--disable-infobars')
#     options.set_argument('--headless=new')  # 启用无头模式
#
#     # 设置用户代理
#     user_agents = [
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
#         "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
#         "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
#     ]
#     options.set_user_agent(random.choice(user_agents))
#
#     return ChromiumPage(addr_or_opts=options)
#
#
# class VideoDownloadThread(threading.Thread):
#     def __init__(self, list_url: str, log_emitter: Optional[LogEmitter] = None):
#         super().__init__()
#         self.task_frame = None
#         self.list_url = list_url
#         self.log_emitter = log_emitter
#         self.download_dir = "E:\Temp\Huawei Share\LF"
#         self.running = True
#         self.paused = False
#         self.pause_cond = threading.Condition(threading.Lock())
#         self.max_workers = 2  # 同时下载的最大视频数
#         os.makedirs(self.download_dir, exist_ok=True)
#         # 确保日志目录存在
#         self.logger_dir = "logger"
#         os.makedirs(self.logger_dir, exist_ok=True)
#
#     def log_message(self, message: str):
#         if self.log_emitter and hasattr(self.log_emitter, 'log_signal'):
#             self.log_emitter.log_signal.emit(message)  # type: ignore
#
#     def log_failure(self, filename: str, url: str, error: str = ""):
#         """记录下载失败到日志文件"""
#         try:
#             # 创建日志文件路径（按日期）
#             log_file = os.path.join(self.logger_dir, f"{time.strftime('%Y-%m-%d')}.log")
#             # 日志内容
#             log_content = (
#                 f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
#                 f"下载失败: 文件名: {filename}, "
#                 f"URL: {url}, "
#                 f"错误: {error}\n"
#             )
#             # 写入日志文件（追加模式）
#             with open(log_file, "a", encoding="utf-8") as f:
#                 f.write(log_content)
#         except Exception as e:
#             self.log_message(f"记录失败日志时出错: {str(e)}")
#
#     def pause(self):
#         """暂停下载任务"""
#         self.paused = True
#         self.log_message(f"下载任务已暂停: {self.list_url}")
#
#     def resume(self):
#         """继续下载任务"""
#         with self.pause_cond:
#             self.paused = False
#             self.pause_cond.notify()  # 唤醒等待的线程
#         self.log_message(f"下载任务已继续: {self.list_url}")
#
#     def stop(self):
#         """停止下载任务"""
#         self.running = False
#         with self.pause_cond:
#             self.paused = False
#             self.pause_cond.notify_all()  # 唤醒所有等待的线程
#         self.log_message(f"下载任务已停止: {self.list_url}")
#
#     def wait_if_paused(self):
#         """如果任务被暂停，则等待直到继续"""
#         with self.pause_cond:
#             while self.paused:
#                 self.pause_cond.wait()
#
#     def get_video_links(self) -> list[str] | None:
#         """获取列表页中的所有视频链接"""
#         self.log_message(f"正在从 {self.list_url} 获取视频列表...")
#         browser = None
#         links: List[str] = []
#         try:
#             browser = get_browser()
#             browser.get(self.list_url)
#
#             # 使用条件等待替代固定等待
#             start_time = time.time()
#             while time.time() - start_time < 30:  # 最多等待30秒
#                 # 检查是否被暂停
#                 self.wait_if_paused()
#                 if not self.running:
#                     return None
#
#                 # 检查播放列表是否已加载
#                 playlist = browser.ele('#playlist-scroll', timeout=1)
#                 if playlist:
#                     break
#                 time.sleep(1)  # 每1秒检查一次
#             else:
#                 self.log_message("等待播放列表加载超时")
#                 return None
#
#             # 获取所有视频链接
#             link_elements = playlist.eles('tag:a', timeout=10)
#             if link_elements:
#                 links = [a.attr('href') for a in link_elements if a.attr('href')]
#                 unique_links = list(set(links))
#                 self.log_message(f"找到 {len(unique_links)} 个唯一视频")
#                 links = unique_links
#         except Exception as e:
#             self.log_message(f"获取视频链接时出错: {str(e)}")
#         finally:
#             if browser:
#                 try:
#                     browser.quit()
#                 except Exception as e:
#                     self.log_message(f"关闭浏览器时出错: {str(e)}")
#         return links
#
#     def download_video(self, video_url: str) -> bool | None:
#         """下载单个视频，增加失败重试机制"""
#         if not self.running:
#             return False
#
#         # 重试机制 - 最多3次
#         max_retries = 3
#         retry_count = 0
#         success = False
#
#         while retry_count <= max_retries and not success and self.running:
#             retry_count += 1
#             self.log_message(f"尝试下载视频: {video_url} (尝试 {retry_count}/{max_retries + 1})")
#             try:
#                 success = self._download_video_attempt(video_url)
#                 if not success:
#                     self.log_message(f"第 {retry_count} 次下载失败，稍后重试...")
#                     time.sleep(2 + random.random() * 2)  # 随机延迟避免频繁请求
#             except Exception as e:
#                 self.log_message(f"下载过程中发生异常: {str(e)}")
#                 time.sleep(3)  # 异常后等待更长时间
#
#         if success:
#             self.log_message(f"成功下载视频: {video_url}")
#         else:
#             self.log_message(f"下载失败: {video_url} (超过最大重试次数)")
#
#         return success
#
#     def _download_video_attempt(self, video_url: str) -> bool:
#         """单个视频下载尝试"""
#         result = False
#         self.log_message(f"处理视频: {video_url}")
#         browser = get_browser()
#         try:
#             # 访问视频页面
#             browser.get(video_url)
#
#             # 使用条件等待替代固定等待
#             start_time = time.time()
#             while time.time() - start_time < 20:  # 最多等待20秒
#                 # 检查是否被暂停或停止
#                 self.wait_if_paused()
#                 if not self.running:
#                     return False
#
#                 # 检查下载按钮是否已加载
#                 download_btn = browser.ele('#downloadBtn', timeout=1)
#                 if download_btn:
#                     break
#                 time.sleep(1)  # 每1秒检查一次
#             else:
#                 self.log_message("等待下载按钮加载超时")
#                 return False
#
#             download_page_url = download_btn.attr('href')
#             if not download_page_url:
#                 self.log_message("下载按钮没有有效的链接")
#                 return False
#
#             self.log_message(f"找到下载页面: {download_page_url}")
#
#             # 访问下载页面
#             browser.get(download_page_url)
#
#             # 使用条件等待替代固定等待
#             start_time = time.time()
#             while time.time() - start_time < 30:  # 最多等待30秒
#                 # 检查是否被暂停或停止
#                 self.wait_if_paused()
#                 if not self.running:
#                     return False
#
#                 # 检查Cloudflare验证是否已完成
#                 if "just a moment" not in browser.title.lower():
#                     break
#                 time.sleep(1)  # 每1秒检查一次
#             else:
#                 self.log_message("等待Cloudflare验证完成超时")
#                 return False
#
#             # 定位下载链接
#             download_table = browser.ele('#content-div', timeout=10)
#             if not download_table:
#                 self.log_message("未找到下载表格")
#                 return False
#
#             # 获取第一个下载链接
#             download_link_ele = download_table.ele('xpath:.//tr[2]/td[5]/a', timeout=10)
#             if not download_link_ele:
#                 self.log_message("未找到下载链接元素")
#                 return False
#
#             video_url = download_link_ele.attr('data-url')
#             filename = download_link_ele.attr('download') + '.mp4'
#
#             if not video_url or not filename:
#                 self.log_message("未找到下载URL或文件名")
#                 return False
#
#             self.log_message(f"找到视频URL: {video_url}")
#             self.log_message(f"正在下载: {filename}")
#
#             # 下载视频
#             result = self.save_video(video_url, filename)  # 确保赋值
#         except Exception as e:
#             self.log_message(f"处理视频时出错: {str(e)}")
#             result = False
#         finally:
#             try:
#                 browser.quit()  # 安全关闭浏览器
#             except Exception as e:
#                 self.log_message(f"关闭浏览器时出错: {str(e)}")
#             return result  # 显式返回结果
#
#     def save_video(self, url: str, filename: str) -> bool:
#         """保存视频文件"""
#         filepath = ''
#         if not self.running:
#             return False
#
#         try:
#             headers = {
#                 'Referer': 'https://hanime1.me/',
#                 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
#             }
#
#             # 创建会话
#             session = requests.Session()
#             response = session.get(url, headers=headers, stream=True)
#             response.raise_for_status()
#
#             # 写入文件
#             filepath = os.path.join(self.download_dir, filename)
#             total_size = int(response.headers.get('content-length', 0))
#             downloaded = 0
#             last_percent = -1  # 记录上次报告的百分比
#
#             with open(filepath, 'wb') as f:
#                 for chunk in response.iter_content(chunk_size=8192):
#                     # 检查是否被暂停
#                     self.wait_if_paused()
#
#                     if not self.running:
#                         # 如果停止，删除部分下载的文件
#                         if os.path.exists(filepath):
#                             os.remove(filepath)
#                         return False
#
#                     if chunk:
#                         f.write(chunk)
#                         downloaded += len(chunk)
#                         if total_size > 0:
#                             percent = (downloaded / total_size) * 100
#                             # 仅当百分比变化超过1%时才更新
#                             if abs(percent - last_percent) > 1 or percent == 100:
#                                 self.log_message(f"下载进度: {filename} - {percent:.1f}%")
#                                 last_percent = percent
#
#             self.log_message(f"成功保存: {filepath}")
#             return True
#         except Exception as e:
#             error_msg = str(e)
#             self.log_message(f"下载失败: {error_msg}")
#             # 记录失败日志
#             self.log_failure(filename, url, error_msg)
#             # 删除部分下载的文件
#             if os.path.exists(filepath):
#                 os.remove(filepath)
#             return False
#
#     def run(self):
#         """运行下载任务"""
#         self.log_message(f"开始下载任务: {self.list_url}")
#         video_links = self.get_video_links()
#
#         if not video_links:
#             self.log_message("未找到视频链接")
#             return
#
#         self.log_message(f"找到 {len(video_links)} 个视频")
#
#         # 使用线程池并发下载视频
#         with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
#             # 创建下载任务
#             futures = []
#             for i, link in enumerate(video_links):
#                 # 检查是否被暂停
#                 self.wait_if_paused()
#
#                 if not self.running:
#                     self.log_message("下载任务已取消")
#                     break
#
#                 if 'search?query' in link:
#                     self.log_message(f"链接: {link} 不是视频链接，跳过")
#                     continue
#
#                 self.log_message(f"提交下载任务: 视频 {i + 1}/{len(video_links)}")
#                 future = executor.submit(self.download_video, link)
#                 futures.append(future)
#                 # 添加随机延迟避免请求过于密集
#                 time.sleep(random.uniform(0.5, 1.5))
#
#             # 等待所有任务完成
#             for i, future in enumerate(as_completed(futures)):
#                 # 检查是否被暂停
#                 self.wait_if_paused()
#
#                 if not self.running:
#                     # 取消所有未完成的任务
#                     for f in futures:
#                         if not f.done():
#                             f.cancel()
#                     self.log_message("下载任务已取消")
#                     break
#
#                 try:
#                     success = future.result()
#                     if success:
#                         self.log_message(f"视频 {i + 1} 下载成功")
#                     else:
#                         self.log_message(f"视频 {i + 1} 下载失败")
#                 except Exception as e:
#                     self.log_message(f"视频下载出错: {str(e)}")
#
#         self.log_message(f"下载任务完成: {self.list_url}")
#
#
# def update_task_status(task_frame: QFrame, status: str, color: str):
#     """更新任务状态显示"""
#     status_label = task_frame.findChild(QLabel, "status_label")
#     if status_label:
#         status_label.setText(f"状态: {status}")
#         status_label.setStyleSheet(f"color: {color};")
#
#     # 更新按钮状态
#     pause_btn = task_frame.findChild(QPushButton, "pause_btn")
#     resume_btn = task_frame.findChild(QPushButton, "resume_btn")
#
#     if status == "运行中":
#         if pause_btn: pause_btn.setEnabled(True)
#         if resume_btn: resume_btn.setEnabled(False)
#     elif status == "已暂停":
#         if pause_btn: pause_btn.setEnabled(False)
#         if resume_btn: resume_btn.setEnabled(True)
#     else:  # 等待中或队列中
#         if pause_btn: pause_btn.setEnabled(False)
#         if resume_btn: resume_btn.setEnabled(False)
#
#
# class HanimeDownloaderApp(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.status_bar = None
#         self.tasks_layout = None
#         self.tasks_container = None
#         self.log_area = None
#         self.tasks_scroll = None
#         self.url_input = None
#         self.stop_btn = None
#         self.download_btn = None
#         self.setWindowTitle("Hanime视频下载器")
#         self.setGeometry(100, 100, 800, 1100)
#         self.setStyleSheet("""
#             QMainWindow {
#                 background-color: #2c3e50;
#             }
#             QGroupBox {
#                 background-color: #34495e;
#                 border: 2px solid #3498db;
#                 border-radius: 10px;
#                 margin-top: 1ex;
#                 color: white;
#                 font-weight: bold;
#             }
#             QGroupBox::title {
#                 subcontrol-origin: margin;
#                 subcontrol-position: top center;
#                 padding: 0 5px;
#             }
#             QLabel {
#                 color: #ecf0f1;
#             }
#             QLineEdit {
#                 background-color: #2c3e50;
#                 color: #ecf0f1;
#                 border: 1px solid #3498db;
#                 border-radius: 5px;
#                 padding: 5px;
#                 min-height: 40px;  /* 添加这行设置高度 */
#             }
#             QPushButton {
#                 background-color: #3498db;
#                 color: white;
#                 border: none;
#                 border-radius: 5px;
#                 padding: 8px 16px;
#                 font-weight: bold;
#             }
#             QPushButton:hover {
#                 background-color: #2980b9;
#             }
#             QPushButton:pressed {
#                 background-color: #1c6ea4;
#             }
#             QPushButton:disabled {
#                 background-color: #7f8c8d;
#             }
#             QTextEdit {
#                 background-color: #2c3e50;
#                 color: #ecf0f1;
#                 border: 1px solid #3498db;
#                 border-radius: 5px;
#                 font-family: Consolas, Courier New;
#             }
#             QScrollArea {
#                 background-color: transparent;
#                 border: none;
#             }
#             QFrame {
#                 background-color: #34495e;
#                 border-radius: 5px;
#                 padding: 10px;
#                 border: 1px solid #3498db;
#             }
#             #tasks_container {
#                 background-color: #2c3e50;
#             }
#         """)
#
#         self.active_threads: List[VideoDownloadThread] = []
#         self.pending_tasks: List[dict] = []  # 等待队列
#         self.log_emitter = LogEmitter()
#         # 添加类型忽略注释解决静态检查问题
#         self.log_emitter.log_signal.connect(self.log_message)  # type: ignore
#         self.max_concurrent_tasks = 2  # 最大并发任务数
#
#         self.init_ui()
#
#     def init_ui(self):
#         """初始化用户界面"""
#         central_widget = QWidget()
#         self.setCentralWidget(central_widget)
#
#         main_layout = QVBoxLayout(central_widget)
#         main_layout.setSpacing(15)
#         main_layout.setContentsMargins(20, 20, 20, 20)
#
#         # 标题
#         title_label = QLabel("Hanime视频下载器")
#         title_label.setFont(QFont("Arial", 18, QFont.Bold))
#         title_label.setAlignment(Qt.AlignCenter)
#         title_label.setStyleSheet("color: #3498db; margin-bottom: 20px;")
#         main_layout.addWidget(title_label)
#
#         # 输入区域
#         input_group = QGroupBox("输入视频列表链接")
#         input_layout = QVBoxLayout(input_group)
#
#         self.url_input = QLineEdit()
#         self.url_input.setPlaceholderText("例如: https://hanime1.me/watch?v=????")
#         input_layout.addWidget(self.url_input)
#
#         button_layout = QHBoxLayout()
#         self.download_btn = QPushButton("开始下载")
#         self.download_btn.clicked.connect(self.start_download)  # type: ignore
#         button_layout.addWidget(self.download_btn)
#
#         self.stop_btn = QPushButton("停止所有下载")
#         self.stop_btn.clicked.connect(self.stop_all_downloads)  # type: ignore
#         self.stop_btn.setEnabled(False)
#         button_layout.addWidget(self.stop_btn)
#
#         input_layout.addLayout(button_layout)
#         main_layout.addWidget(input_group)
#
#         # 日志区域
#         log_group = QGroupBox("下载日志")
#         log_layout = QVBoxLayout(log_group)
#
#         self.log_area = QTextEdit()
#         self.log_area.setReadOnly(True)
#         log_layout.addWidget(self.log_area)
#
#         main_layout.addWidget(log_group)
#
#         # 活动任务区域
#         tasks_group = QGroupBox("活动下载任务")
#         tasks_layout = QVBoxLayout(tasks_group)
#
#         self.tasks_scroll = QScrollArea()
#         self.tasks_scroll.setWidgetResizable(True)
#         self.tasks_container = QWidget()
#         self.tasks_container.setObjectName("tasks_container")  # 添加对象名以便样式表选择
#         self.tasks_layout = QVBoxLayout(self.tasks_container)
#         self.tasks_layout.setAlignment(Qt.AlignTop)
#         self.tasks_layout.setSpacing(10)
#         self.tasks_layout.setContentsMargins(5, 5, 5, 5)
#
#         self.tasks_scroll.setWidget(self.tasks_container)
#         tasks_layout.addWidget(self.tasks_scroll)
#
#         main_layout.addWidget(tasks_group)
#
#         # 状态栏
#         self.status_bar = self.statusBar()
#         self.status_bar.showMessage("就绪")
#
#     def log_message(self, message: str):
#         """添加消息到日志区域"""
#         timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
#         self.log_area.append(f"[{timestamp}] {message}")
#         self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())
#
#     def start_download(self):
#         """开始新的下载任务"""
#         url = self.url_input.text().strip()
#         if not url:
#             self.log_message("请输入有效的URL")
#             return
#
#         self.url_input.clear()
#
#         # 创建任务显示框
#         task_frame = QFrame()
#         task_frame.setFrameShape(QFrame.StyledPanel)
#         task_frame.setObjectName(f"task_{time.time()}")  # 为任务框设置唯一标识
#         task_layout = QVBoxLayout(task_frame)
#
#         task_label = QLabel(f"任务: {url}")
#         task_label.setStyleSheet("color: #ecf0f1; font-weight: bold;")
#         task_layout.addWidget(task_label)
#
#         status_label = QLabel("状态: 等待中")
#         status_label.setStyleSheet("color: #f39c12;")
#         status_label.setObjectName("status_label")  # 设置对象名以便后续访问
#         task_layout.addWidget(status_label)
#
#         # 按钮布局
#         button_layout = QHBoxLayout()
#
#         pause_btn = QPushButton("暂停")
#         pause_btn.setObjectName("pause_btn")
#         pause_btn.clicked.connect(lambda: self.pause_task(task_frame))  # type: ignore
#         button_layout.addWidget(pause_btn)
#
#         resume_btn = QPushButton("继续")
#         resume_btn.setObjectName("resume_btn")
#         resume_btn.setEnabled(False)  # 初始时不可用
#         resume_btn.clicked.connect(lambda: self.resume_task(task_frame))  # type: ignore
#         button_layout.addWidget(resume_btn)
#
#         stop_btn = QPushButton("停止")
#         stop_btn.setObjectName("stop_btn")
#         stop_btn.clicked.connect(lambda: self.stop_task(task_frame))  # type: ignore
#         button_layout.addWidget(stop_btn)
#
#         task_layout.addLayout(button_layout)
#
#         self.tasks_layout.addWidget(task_frame)
#
#         # 检查当前活动任务数量
#         active_count = sum(1 for thread in self.active_threads if
#                            thread.is_alive() and not hasattr(thread, 'paused') or not thread.paused)
#
#         if active_count < self.max_concurrent_tasks:
#             # 立即启动任务
#             update_task_status(task_frame, "运行中", "#2ecc71")
#             self.start_download_task(url, task_frame)
#         else:
#             # 添加到等待队列
#             self.pending_tasks.append({
#                 "url": url,
#                 "frame": task_frame
#             })
#             self.log_message(f"任务已添加到队列，当前队列位置: {len(self.pending_tasks)}")
#             self.update_queue_status()
#
#         # 更新UI
#         self.stop_btn.setEnabled(True)
#
#     def start_download_task(self, url: str, task_frame: QFrame):
#         """启动下载线程"""
#         self.log_message(f"启动新下载任务: {url}")
#
#         # 创建新线程
#         thread = VideoDownloadThread(url, self.log_emitter)
#         thread.daemon = True
#         thread.task_frame = task_frame  # 将任务框与线程关联
#         self.active_threads.append(thread)
#
#         # 启动线程
#         thread.start()
#
#         # 监控线程完成
#         threading.Thread(target=self.monitor_thread, args=(thread, task_frame), daemon=True).start()
#
#     def monitor_thread(self, thread: VideoDownloadThread, task_frame: QFrame):
#         """监控线程状态并在完成后处理后续任务"""
#         # 使用超时机制避免永久阻塞
#         start_time = time.time()
#         while thread.is_alive() and time.time() - start_time < 1800:  # 30分钟超时
#             time.sleep(1)
#
#         if thread.is_alive():
#             self.log_message(f"任务超时: {thread.list_url}")
#             thread.stop()
#
#         # 更新UI
#         if thread in self.active_threads:
#             self.active_threads.remove(thread)
#
#         # 从界面移除任务框
#         task_frame.deleteLater()
#
#         # 启动下一个等待任务
#         self.start_next_task()
#
#     def start_next_task(self):
#         """启动下一个等待中的任务"""
#         if self.pending_tasks:
#             next_task = self.pending_tasks.pop(0)
#             url = next_task["url"]
#             task_frame = next_task["frame"]
#
#             # 更新状态
#             update_task_status(task_frame, "运行中", "#2ecc71")
#
#             # 启动任务
#             self.start_download_task(url, task_frame)
#
#             # 更新队列状态
#             self.update_queue_status()
#
#     def update_queue_status(self):
#         """更新队列中任务的状态显示"""
#         for i, task in enumerate(self.pending_tasks):
#             task_frame = task["frame"]
#             update_task_status(task_frame, f"队列中 ({i + 1})", "#f39c12")
#
#     def pause_task(self, task_frame: QFrame):
#         """暂停任务"""
#         # 找到对应的线程
#         for thread in self.active_threads:
#             if hasattr(thread, 'task_frame') and thread.task_frame == task_frame:
#                 thread.pause()
#                 update_task_status(task_frame, "已暂停", "#f39c12")
#                 self.log_message(f"任务已暂停: {thread.list_url}")
#                 break
#
#     def resume_task(self, task_frame: QFrame):
#         """继续任务"""
#         # 找到对应的线程
#         for thread in self.active_threads:
#             if hasattr(thread, 'task_frame') and thread.task_frame == task_frame:
#                 thread.resume()
#                 update_task_status(task_frame, "运行中", "#2ecc71")
#                 self.log_message(f"任务已继续: {thread.list_url}")
#                 break
#
#     def stop_task(self, task_frame: QFrame):
#         """停止单个任务"""
#         # 找到对应的线程
#         for thread in self.active_threads:
#             if hasattr(thread, 'task_frame') and thread.task_frame == task_frame:
#                 thread.stop()
#                 self.log_message(f"任务已停止: {thread.list_url}")
#
#                 # 从活动线程列表中移除
#                 self.active_threads.remove(thread)
#
#                 # 从界面移除任务框
#                 task_frame.deleteLater()
#
#                 # 如果是当前活动任务，启动下一个任务
#                 self.start_next_task()
#                 break
#         else:
#             # 如果任务在等待队列中
#             for task in self.pending_tasks:
#                 if task["frame"] == task_frame:
#                     self.pending_tasks.remove(task)
#                     self.log_message(f"已从队列中移除任务: {task['url']}")
#                     task_frame.deleteLater()
#                     self.update_queue_status()
#                     break
#
#     def stop_all_downloads(self):
#         """停止所有下载任务"""
#         # 停止所有活动线程
#         for thread in self.active_threads:
#             if hasattr(thread, 'stop'):
#                 thread.stop()
#                 self.log_message(f"已停止任务: {thread.list_url}")
#
#         # 清除所有等待任务
#         self.pending_tasks.clear()
#
#         # 清除所有任务显示
#         for i in reversed(range(self.tasks_layout.count())):
#             widget = self.tasks_layout.itemAt(i).widget()
#             if widget:
#                 widget.deleteLater()
#
#         # 重置状态
#         self.active_threads = []
#         self.stop_btn.setEnabled(False)
#         self.log_message("已停止所有下载任务")
#
#     def closeEvent(self, event):
#         """关闭窗口时停止所有线程"""
#         if self.active_threads or self.pending_tasks:
#             self.stop_all_downloads()
#             time.sleep(1)  # 给线程一点时间停止
#         event.accept()
#
#
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#
#     # 设置应用样式
#     app.setStyle("Fusion")
#
#     window = HanimeDownloaderApp()
#     window.show()
#
#     sys.exit(app.exec_())