import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
import requests
from ToolPart.Browser import get_browser
from ToolPart.Logger import LogEmitter, log_failure


class VideoDownloadThread(threading.Thread):
    def __init__(self, list_url: str, download_dir: str, log_emitter: Optional[LogEmitter] = None):
        super().__init__()
        self.task_frame = None
        self.task_id = None  # 新增：任务ID
        self.list_url = list_url
        self.log_emitter = log_emitter
        self.download_dir = download_dir  # 使用传入的下载路径
        self.running = True
        self.paused = False
        self.pause_cond = threading.Condition(threading.Lock())
        self.max_workers = 2  # 同时下载的最大视频数
        os.makedirs(self.download_dir, exist_ok=True)
        # 确保日志目录存在
        self.logger_dir = "./logger"
        os.makedirs(self.logger_dir, exist_ok=True)

        # 定义非法字符的正则表达式模式
        self.illegal_chars_pattern = re.compile(r'[\\/*?:"<>|]')

    def sanitize_filename(self, filename: str) -> str:
        """清洗文件名，移除非法字符"""
        # 移除非法字符
        clean_name = self.illegal_chars_pattern.sub('_', filename)

        # 移除开头和结尾的空白
        clean_name = clean_name.strip()

        # 如果文件名过长，截断到合理长度
        max_length = 200  # 大多数文件系统的最大文件名长度
        if len(clean_name) > max_length:
            # 保留扩展名
            name_part, ext = os.path.splitext(clean_name)
            name_part = name_part[:max_length - len(ext)]
            clean_name = name_part + ext

        # 确保文件名不为空
        if not clean_name:
            clean_name = "unnamed_video"

        return clean_name

    def log_message(self, message: str):
        if self.log_emitter and hasattr(self.log_emitter, 'log_signal'):
            self.log_emitter.log_signal.emit(message)  # type: ignore

    def pause(self):
        """暂停下载任务"""
        self.paused = True
        self.log_message(f"下载任务已暂停: {self.list_url}")

    def resume(self):
        """继续下载任务"""
        with self.pause_cond:
            self.paused = False
            self.pause_cond.notify()  # 唤醒等待的线程
        self.log_message(f"下载任务已继续: {self.list_url}")

    def stop(self):
        """停止下载任务"""
        self.running = False
        with self.pause_cond:
            self.paused = False
            self.pause_cond.notify_all()  # 唤醒所有等待的线程
        self.log_message(f"下载任务已停止: {self.list_url}")

    def wait_if_paused(self):
        """如果任务被暂停，则等待直到继续"""
        with self.pause_cond:
            while self.paused:
                self.pause_cond.wait()

    def get_video_links(self) -> tuple[list[str] | None, str | None] | None:
        """获取列表页中的所有视频链接和播放列表标题"""
        self.log_message(f"正在从 {self.list_url} 获取视频列表...")
        browser = None
        links: list[str] | None = None  # 修改1: 初始化为None
        playlist_title: str | None = None  # 修改2: 初始化为None
        try:
            browser = get_browser()
            browser.get(self.list_url)

            # 使用条件等待替代固定等待
            start_time = time.time()
            while time.time() - start_time < 30:  # 最多等待30秒
                # 检查是否被暂停
                self.wait_if_paused()
                if not self.running:
                    return None, None

                # 检查播放列表是否已加载
                playlist = browser.ele('#playlist-scroll', timeout=1)
                if playlist:
                    break
                time.sleep(1)  # 每1秒检查一次
            else:
                self.log_message("等待播放列表加载超时")
                return None, None

            # 获取播放列表标题
            try:
                title_element = browser.ele('xpath://*[@id="video-playlist-wrapper"]/div[1]/h4[1]', timeout=5)
                if title_element:
                    playlist_title = title_element.text.strip()
                    self.log_message(f"播放列表标题: {playlist_title}")

                    # 发送特殊消息更新UI中的任务标题
                    if hasattr(self, 'task_id'):
                        self.log_message(f"[TITLE_UPDATE]|||{self.task_id}|||{playlist_title}")
                else:
                    self.log_message("未找到播放列表标题")
            except Exception as e:
                self.log_message(f"获取播放列表标题时出错: {str(e)}")

            # 获取所有视频链接
            link_elements = playlist.eles('tag:a', timeout=10)
            if link_elements:
                found_links = [a.attr('href') for a in link_elements if a.attr('href')]
                unique_links = list(set(found_links))
                self.log_message(f"找到 {len(unique_links)} 个唯一视频")
                links = unique_links
        except Exception as e:
            self.log_message(f"获取视频链接时出错: {str(e)}")
            links, playlist_title = None, None  # 修改3: 出错时返回None
        finally:
            if browser:
                try:
                    browser.quit()
                except Exception as e:
                    self.log_message(f"关闭浏览器时出错: {str(e)}")
        return links, playlist_title  # 类型现在符合声明

    def download_video(self, video_url: str) -> bool | None:
        """下载单个视频，增加失败重试机制"""
        if not self.running:
            return False

        # 重试机制 - 最多3次
        max_retries = 3
        retry_count = 0
        success = False
        last_error = None  # 存储最后一次错误信息
        filename = None  # 存储文件名（如果有）

        while retry_count <= max_retries and not success and self.running:
            retry_count += 1
            self.log_message(f"尝试下载视频: {video_url} (尝试 {retry_count}/{max_retries + 1})")
            try:
                # 返回成功状态和可能的错误信息
                success, error, file = self._download_video_attempt(video_url)
                if not success:
                    last_error = error  # 保存错误信息
                    self.log_message(f"第 {retry_count} 次下载失败，稍后重试...")
                    time.sleep(2 + random.random() * 2)  # 随机延迟避免频繁请求
                else:
                    filename = file  # 保存成功的文件名
            except Exception as e:
                last_error = str(e)
                self.log_message(f"下载过程中发生异常: {str(e)}")
                time.sleep(3)  # 异常后等待更长时间

        if success:
            self.log_message(f"成功下载视频: {video_url}")
            return True
        else:
            # 所有重试都失败后记录一次日志
            self.log_message(f"下载失败: {video_url} (超过最大重试次数)")
            if last_error and filename:
                # 记录失败日志时也使用清洗后的文件名
                log_failure(self.logger_dir, filename, video_url, last_error)
            elif last_error:
                # 如果没有获取到文件名，使用视频URL作为文件名标识
                log_failure(self.logger_dir, video_url, video_url, last_error)
            return False

    def _download_video_attempt(self, video_url: str) -> tuple[bool, str, str | None]:
        """单个视频下载尝试，返回（是否成功，错误信息，文件名）"""
        self.log_message(f"处理视频: {video_url}")
        browser = get_browser()
        filename = None
        try:
            # 访问视频页面
            browser.get(video_url)

            # 使用条件等待替代固定等待
            start_time = time.time()
            while time.time() - start_time < 20:  # 最多等待20秒
                # 检查是否被暂停或停止
                self.wait_if_paused()
                if not self.running:
                    return False, "任务已停止", None

                # 检查下载按钮是否已加载
                download_btn = browser.ele('#downloadBtn', timeout=1)
                if download_btn:
                    break
                time.sleep(1)  # 每1秒检查一次
            else:
                error_msg = "等待下载按钮加载超时"
                self.log_message(error_msg)
                return False, error_msg, None

            download_page_url = download_btn.attr('href')
            if not download_page_url:
                error_msg = "下载按钮没有有效的链接"
                self.log_message(error_msg)
                return False, error_msg, None

            self.log_message(f"找到下载页面: {download_page_url}")

            # 访问下载页面
            browser.get(download_page_url)

            # 使用条件等待替代固定等待
            start_time = time.time()
            while time.time() - start_time < 30:  # 最多等待30秒
                # 检查是否被暂停或停止
                self.wait_if_paused()
                if not self.running:
                    return False, "任务已停止", None

                # 检查Cloudflare验证是否已完成
                if "just a moment" not in browser.title.lower():
                    break
                time.sleep(1)  # 每1秒检查一次
            else:
                error_msg = "等待Cloudflare验证完成超时"
                self.log_message(error_msg)
                return False, error_msg, None

            # 定位下载链接
            download_table = browser.ele('#content-div', timeout=10)
            if not download_table:
                error_msg = "未找到下载表格"
                self.log_message(error_msg)
                return False, error_msg, None

            # 获取第一个下载链接
            download_link_ele = download_table.ele('xpath:.//tr[2]/td[5]/a', timeout=10)
            if not download_link_ele:
                error_msg = "未找到下载链接元素"
                self.log_message(error_msg)
                return False, error_msg, None

            video_download_url = download_link_ele.attr('data-url')
            raw_filename = download_link_ele.attr('download') + '.mp4'

            # 清洗文件名
            filename = self.sanitize_filename(raw_filename)
            self.log_message(f"原始文件名: {raw_filename} -> 清洗后: {filename}")

            # 检查文件是否已存在
            filepath = os.path.join(self.download_dir, filename)
            if os.path.exists(filepath) and os.path.isfile(filepath):
                self.log_message(f"文件已存在，跳过下载: {filename}")
                return True, "文件已存在，跳过下载", filename
            # =====================

            if not video_download_url or not filename:
                error_msg = "未找到下载URL或文件名"
                self.log_message(error_msg)
                return False, error_msg, None

            self.log_message(f"找到视频URL: {video_download_url}")
            self.log_message(f"正在下载: {filename}")

            # 下载视频
            success, error = self.save_video(video_download_url, filename)
            return success, error, filename
        except Exception as e:
            error_msg = f"处理视频时出错: {str(e)}"
            self.log_message(error_msg)
            return False, error_msg, filename
        finally:
            try:
                browser.quit()  # 安全关闭浏览器
            except Exception as e:
                self.log_message(f"关闭浏览器时出错: {str(e)}")

    def save_video(self, url: str, filename: str) -> tuple[bool, str]:
        """保存视频文件，返回（是否成功，错误信息）"""
        # 再次清洗文件名以确保安全
        clean_filename = self.sanitize_filename(filename)
        filepath = ''
        if not self.running:
            return False, "任务已停止"

        try:
            headers = {
                'Referer': 'https://hanime1.me/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            # 最终检查（防止并发场景）
            if os.path.exists(filepath) and os.path.isfile(filepath):
                self.log_message(f"文件已存在，跳过下载: {clean_filename}")
                return True, "文件已存在，跳过下载"

            # 创建会话
            session = requests.Session()
            response = session.get(url, headers=headers, stream=True)
            response.raise_for_status()

            # 写入文件
            filepath = os.path.join(self.download_dir, clean_filename)
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            last_percent = -1  # 记录上次报告的百分比

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    # 检查是否被暂停
                    self.wait_if_paused()

                    if not self.running:
                        # 如果停止，删除部分下载的文件
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        return False, "任务已停止"

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            # 仅当百分比变化超过1%时才更新
                            if abs(percent - last_percent) > 1 or percent == 100:
                                self.log_message(f"下载进度: {clean_filename} - {percent:.1f}%")
                                last_percent = percent

            self.log_message(f"成功保存: {filepath}")
            return True, ""
        except Exception as e:
            error_msg = str(e)
            self.log_message(f"下载失败: {clean_filename} - {error_msg}")
            # 删除部分下载的文件
            if os.path.exists(filepath):
                os.remove(filepath)
            return False, error_msg

    def run(self):
        """运行下载任务"""
        self.log_message(f"开始下载任务: {self.list_url}")
        video_links, playlist_title = self.get_video_links()

        if not video_links:
            self.log_message("未找到视频链接")
            return

        self.log_message(f"找到 {len(video_links)} 个视频")

        # 用于收集失败的任务
        failed_downloads = []

        # 使用线程池并发下载视频
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 创建下载任务
            futures = []
            for i, link in enumerate(video_links):
                # 检查是否被暂停
                self.wait_if_paused()

                if not self.running:
                    self.log_message("下载任务已取消")
                    break

                if 'search?query' in link:
                    self.log_message(f"链接: {link} 不是视频链接，跳过")
                    continue

                self.log_message(f"提交下载任务: 视频 {i + 1}/{len(video_links)}")
                future = executor.submit(self.download_video, link)
                futures.append(future)
                # 添加随机延迟避免请求过于密集
                time.sleep(random.uniform(0.5, 1.5))

            # 等待所有任务完成
            for i, future in enumerate(as_completed(futures)):
                # 检查是否被暂停
                self.wait_if_paused()

                if not self.running:
                    # 取消所有未完成的任务
                    for f in futures:
                        if not f.done():
                            f.cancel()
                    self.log_message("下载任务已取消")
                    break

                try:
                    success = future.result()
                    if success:
                        self.log_message(f"视频 {i + 1} 下载成功")
                    else:
                        self.log_message(f"视频 {i + 1} 下载失败")
                        # 记录失败的任务
                        failed_downloads.append(video_links[i])
                except Exception as e:
                    self.log_message(f"视频下载出错: {str(e)}")
                    # 记录失败的任务
                    failed_downloads.append(video_links[i])

        # 如果有失败的任务，发送特殊格式的消息
        if failed_downloads and self.running:
            failed_urls = "|||".join(failed_downloads)
            self.log_message(f"[FAILED_TASKS]|||{self.task_id}|||{failed_urls}")

        self.log_message(f"下载任务完成: {self.list_url}")