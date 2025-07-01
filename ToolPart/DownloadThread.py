import os
import random
import threading
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List

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

    def get_video_links(self) -> tuple[list[str] | None, str | None]:
        """获取列表页中的所有视频链接和播放列表标题"""
        self.log_message(f"正在从 {self.list_url} 获取视频列表...")
        browser = None
        links: List[str] = []
        playlist_title = ""
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
                links = [a.attr('href') for a in link_elements if a.attr('href')]
                unique_links = list(set(links))
                self.log_message(f"找到 {len(unique_links)} 个唯一视频")
                links = unique_links
        except Exception as e:
            self.log_message(f"获取视频链接时出错: {str(e)}")
        finally:
            if browser:
                try:
                    browser.quit()
                except Exception as e:
                    self.log_message(f"关闭浏览器时出错: {str(e)}")
        return links, playlist_title

    def download_video(self, video_url: str) -> bool | None:
        """下载单个视频，增加失败重试机制"""
        if not self.running:
            return False

        # 重试机制 - 最多3次
        max_retries = 3
        retry_count = 0
        success = False

        while retry_count <= max_retries and not success and self.running:
            retry_count += 1
            self.log_message(f"尝试下载视频: {video_url} (尝试 {retry_count}/{max_retries + 1})")
            try:
                success = self._download_video_attempt(video_url)
                if not success:
                    self.log_message(f"第 {retry_count} 次下载失败，稍后重试...")
                    time.sleep(2 + random.random() * 2)  # 随机延迟避免频繁请求
            except Exception as e:
                self.log_message(f"下载过程中发生异常: {str(e)}")
                time.sleep(3)  # 异常后等待更长时间

        if success:
            self.log_message(f"成功下载视频: {video_url}")
        else:
            self.log_message(f"下载失败: {video_url} (超过最大重试次数)")

        return success

    def _download_video_attempt(self, video_url: str) -> bool:
        """单个视频下载尝试"""
        result = False
        self.log_message(f"处理视频: {video_url}")
        browser = get_browser()
        try:
            # 访问视频页面
            browser.get(video_url)

            # 使用条件等待替代固定等待
            start_time = time.time()
            while time.time() - start_time < 20:  # 最多等待20秒
                # 检查是否被暂停或停止
                self.wait_if_paused()
                if not self.running:
                    return False

                # 检查下载按钮是否已加载
                download_btn = browser.ele('#downloadBtn', timeout=1)
                if download_btn:
                    break
                time.sleep(1)  # 每1秒检查一次
            else:
                self.log_message("等待下载按钮加载超时")
                return False

            download_page_url = download_btn.attr('href')
            if not download_page_url:
                self.log_message("下载按钮没有有效的链接")
                return False

            self.log_message(f"找到下载页面: {download_page_url}")

            # 访问下载页面
            browser.get(download_page_url)

            # 使用条件等待替代固定等待
            start_time = time.time()
            while time.time() - start_time < 30:  # 最多等待30秒
                # 检查是否被暂停或停止
                self.wait_if_paused()
                if not self.running:
                    return False

                # 检查Cloudflare验证是否已完成
                if "just a moment" not in browser.title.lower():
                    break
                time.sleep(1)  # 每1秒检查一次
            else:
                self.log_message("等待Cloudflare验证完成超时")
                return False

            # 定位下载链接
            download_table = browser.ele('#content-div', timeout=10)
            if not download_table:
                self.log_message("未找到下载表格")
                return False

            # 获取第一个下载链接
            download_link_ele = download_table.ele('xpath:.//tr[2]/td[5]/a', timeout=10)
            if not download_link_ele:
                self.log_message("未找到下载链接元素")
                return False

            video_url = download_link_ele.attr('data-url')
            filename = download_link_ele.attr('download') + '.mp4'

            if not video_url or not filename:
                self.log_message("未找到下载URL或文件名")
                return False

            self.log_message(f"找到视频URL: {video_url}")
            self.log_message(f"正在下载: {filename}")

            # 下载视频
            result = self.save_video(video_url, filename)  # 确保赋值
        except Exception as e:
            self.log_message(f"处理视频时出错: {str(e)}")
            result = False
        finally:
            try:
                browser.quit()  # 安全关闭浏览器
            except Exception as e:
                self.log_message(f"关闭浏览器时出错: {str(e)}")
            return result  # 显式返回结果

    def save_video(self, url: str, filename: str) -> bool:
        """保存视频文件"""
        filepath = ''
        if not self.running:
            return False

        try:
            headers = {
                'Referer': 'https://hanime1.me/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            # 创建会话
            session = requests.Session()
            response = session.get(url, headers=headers, stream=True)
            response.raise_for_status()

            # 写入文件
            filepath = os.path.join(self.download_dir, filename)
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
                        return False

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            # 仅当百分比变化超过1%时才更新
                            if abs(percent - last_percent) > 1 or percent == 100:
                                self.log_message(f"下载进度: {filename} - {percent:.1f}%")
                                last_percent = percent

            self.log_message(f"成功保存: {filepath}")
            return True
        except Exception as e:
            error_msg = str(e)
            self.log_message(f"下载失败: {error_msg}")
            # 记录失败日志
            log_failure(self.logger_dir, filename, url, error_msg)
            # 删除部分下载的文件
            if os.path.exists(filepath):
                os.remove(filepath)
            return False

    def run(self):
        """运行下载任务"""
        self.log_message(f"开始下载任务: {self.list_url}")
        video_links, playlist_title = self.get_video_links()

        if not video_links:
            self.log_message("未找到视频链接")
            return

        self.log_message(f"找到 {len(video_links)} 个视频")

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
                except Exception as e:
                    self.log_message(f"视频下载出错: {str(e)}")

        self.log_message(f"下载任务完成: {self.list_url}")