import configparser
import os
import time
import uuid
from typing import List, Dict, Any

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox,
                             QScrollArea, QFrame, QFileDialog, QMessageBox,
                             QApplication)

from ToolPart.DownloadThread import VideoDownloadThread
from ToolPart.Logger import LogEmitter


def update_task_status(task_frame: QFrame, status: str, color: str) -> None:
    """更新任务状态显示"""
    if not task_frame:
        return

    status_label = task_frame.findChild(QLabel, "status_label")
    if status_label:
        status_label.setText(f"状态: {status}")
        status_label.setStyleSheet(f"color: {color};")

    # 更新按钮状态
    pause_btn = task_frame.findChild(QPushButton, "pause_btn")
    resume_btn = task_frame.findChild(QPushButton, "resume_btn")

    if status == "运行中":
        if pause_btn:
            pause_btn.setEnabled(True)
        if resume_btn:
            resume_btn.setEnabled(False)
    elif status == "已暂停":
        if pause_btn:
            pause_btn.setEnabled(False)
        if resume_btn:
            resume_btn.setEnabled(True)
    else:  # 等待中或队列中
        if pause_btn:
            pause_btn.setEnabled(False)
        if resume_btn:
            resume_btn.setEnabled(False)


class HanimeDownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.status_bar = None
        self.tasks_layout = None
        self.tasks_container = None
        self.log_area = None
        self.tasks_scroll = None
        self.url_input = None
        self.stop_btn = None
        self.download_btn = None
        self.download_path_label = None
        self.setWindowTitle("Hanime视频下载器")
        self.setGeometry(100, 100, 800, 1100)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2c3e50;
            }
            QGroupBox {
                background-color: #34495e;
                border: 2px solid #3498db;
                border-radius: 10px;
                margin-top: 1ex;
                color: white;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
            QLabel {
                color: #ecf0f1;
            }
            QLineEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #3498db;
                border-radius: 5px;
                padding: 5px;
                min-height: 40px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1c6ea4;
            }
            QPushButton:disabled {
                background-color: #7f8c8d;
            }
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #3498db;
                border-radius: 5px;
                font-family: Consolas, Courier New;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QFrame {
                background-color: #34495e;
                border-radius: 5px;
                padding: 10px;
                border: 1px solid #3498db;
            }
            #tasks_container {
                background-color: #2c3e50;
            }
        """)

        self.active_threads: List[VideoDownloadThread] = []
        self.pending_tasks: List[Dict[str, Any]] = []  # 等待队列
        self.log_emitter = LogEmitter()
        self.max_concurrent_tasks = 2  # 减少并发任务数

        # 加载配置文件
        self.config = configparser.ConfigParser()
        self.config_file = "./config.ini"
        self.download_dir = self.load_config()

        self.init_ui()

        # 在 init_ui() 之后连接信号
        self.log_emitter.log_signal.connect(self.log_message)  # type: ignore

    def load_config(self) -> str:
        """加载配置文件，返回下载路径"""
        default_dir = os.path.join(os.getcwd(), "downloads")

        if os.path.exists(self.config_file):
            self.config.read(self.config_file, encoding='utf-8')
            return self.config.get('Settings', 'DownloadDir', fallback=default_dir)

        # 如果配置文件不存在，创建默认配置
        os.makedirs(default_dir, exist_ok=True)
        return default_dir

    def save_config(self) -> None:
        """保存配置到文件"""
        self.config['Settings'] = {'DownloadDir': self.download_dir}
        with open(self.config_file, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)  # type: ignore

    def init_ui(self) -> None:
        """初始化用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel("Hanime视频下载器")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #3498db; margin-bottom: 20px;")
        main_layout.addWidget(title_label)

        # 下载路径设置区域
        path_group = QGroupBox("下载路径设置")
        path_layout = QVBoxLayout(path_group)

        path_control_layout = QHBoxLayout()
        self.download_path_label = QLabel(f"当前下载路径: {self.download_dir}")
        self.download_path_label.setStyleSheet("color: #ecf0f1;")
        path_control_layout.addWidget(self.download_path_label)

        change_path_btn = QPushButton("更改路径")
        change_path_btn.clicked.connect(self.change_download_path)  # type: ignore
        path_control_layout.addWidget(change_path_btn)

        path_layout.addLayout(path_control_layout)
        main_layout.addWidget(path_group)

        # 输入区域
        input_group = QGroupBox("输入视频列表链接")
        input_layout = QVBoxLayout(input_group)

        # 修改：添加URL输入行，包含输入框和粘贴按钮
        url_input_layout = QHBoxLayout()

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("例如: https://hanime1.me/watch?v=????")
        url_input_layout.addWidget(self.url_input)

        # 添加粘贴按钮
        paste_btn = QPushButton("📋 粘贴")
        paste_btn.setMaximumWidth(100)
        paste_btn.setToolTip("粘贴剪贴板中的URL")
        paste_btn.clicked.connect(self.safe_paste_url)  # type: ignore
        url_input_layout.addWidget(paste_btn)

        input_layout.addLayout(url_input_layout)

        button_layout = QHBoxLayout()
        self.download_btn = QPushButton("开始下载")
        self.download_btn.clicked.connect(self.start_download)  # type: ignore
        button_layout.addWidget(self.download_btn)

        self.stop_btn = QPushButton("停止所有下载")
        self.stop_btn.clicked.connect(self.stop_all_downloads)  # type: ignore
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)

        input_layout.addLayout(button_layout)
        main_layout.addWidget(input_group)

        # 日志区域
        log_group = QGroupBox("下载日志")
        log_layout = QVBoxLayout(log_group)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area)

        main_layout.addWidget(log_group)

        # 活动任务区域
        tasks_group = QGroupBox("活动下载任务")
        tasks_layout = QVBoxLayout(tasks_group)

        self.tasks_scroll = QScrollArea()
        self.tasks_scroll.setWidgetResizable(True)
        self.tasks_container = QWidget()
        self.tasks_container.setObjectName("tasks_container")
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setAlignment(Qt.AlignTop)
        self.tasks_layout.setSpacing(10)
        self.tasks_layout.setContentsMargins(5, 5, 5, 5)

        self.tasks_scroll.setWidget(self.tasks_container)
        tasks_layout.addWidget(self.tasks_scroll)

        main_layout.addWidget(tasks_group)

        # 状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪")

    def safe_paste_url(self) -> None:
        """安全地粘贴剪贴板内容到URL输入框"""
        try:
            # 使用 QTimer.singleShot 确保在事件循环中执行
            QTimer.singleShot(0, self._do_paste_url)
        except Exception as e:
            print(f"粘贴错误: {e}")

    def _do_paste_url(self) -> None:
        """实际执行粘贴操作"""
        try:
            clipboard = QApplication.clipboard()
            if not clipboard:
                return

            # 获取剪贴板内容
            mime_data = clipboard.mimeData()
            if mime_data and mime_data.hasText():
                text = mime_data.text().strip()
                if text:
                    # 安全地设置文本
                    if self.url_input:
                        self.url_input.setText(text)
                        self.url_input.setFocus()
                        self.url_input.selectAll()
                        self.log_message(f"已粘贴剪贴板内容到输入框")
        except Exception as e:
            print(f"粘贴操作出错: {e}")
            # 尝试备选方法
            try:
                import pyperclip
                text = pyperclip.paste().strip()
                if text and self.url_input:
                    self.url_input.setText(text)
                    self.url_input.setFocus()
                    self.url_input.selectAll()
                    self.log_message(f"已使用备选方法粘贴")
            except:
                pass

    def log_message(self, message: str) -> None:
        """添加消息到日志区域"""
        try:
            if message.startswith("[TITLE_UPDATE]|||"):
                parts = message.split("|||")
                if len(parts) >= 3:
                    task_id = parts[1]
                    playlist_title = parts[2]
                    self.update_task_title(task_id, playlist_title)
            elif message.startswith("[FAILED_TASKS]|||"):
                parts = message.split("|||")
                if len(parts) >= 3:
                    task_id = parts[1]
                    failed_urls = parts[2:]
                    self.handle_failed_tasks(task_id, failed_urls)
            else:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                if self.log_area:
                    self.log_area.append(f"[{timestamp}] {message}")
                    # 安全地滚动到底部
                    scrollbar = self.log_area.verticalScrollBar()
                    if scrollbar:
                        scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            print(f"日志记录出错: {e}")

    def update_task_title(self, task_id: str, playlist_title: str) -> None:
        """更新任务标题显示播放列表名称"""
        try:
            task_frame = self.findChild(QFrame, task_id)
            if task_frame:
                url = getattr(task_frame, 'url', '未知URL')
                task_label = task_frame.findChild(QLabel)
                if task_label:
                    task_label.setText(f"任务: {url}  {playlist_title}")
        except Exception as e:
            print(f"更新任务标题出错: {e}")

    def start_download(self) -> None:
        """开始新的下载任务"""
        try:
            if not self.url_input:
                return

            url = self.url_input.text().strip()
            if not url:
                self.log_message("请输入有效的URL")
                return

            self.url_input.clear()

            # 创建任务显示框
            task_frame = QFrame()
            task_frame.setFrameShape(QFrame.StyledPanel)
            task_id = str(uuid.uuid4())
            task_frame.setObjectName(task_id)
            task_frame.url = url
            task_layout = QVBoxLayout(task_frame)

            task_label = QLabel(f"任务: {url}")
            task_label.setStyleSheet("color: #ecf0f1; font-weight: bold;")
            task_layout.addWidget(task_label)

            status_label = QLabel("状态: 等待中")
            status_label.setStyleSheet("color: #f39c12;")
            status_label.setObjectName("status_label")
            task_layout.addWidget(status_label)

            # 按钮布局
            button_layout = QHBoxLayout()

            pause_btn = QPushButton("暂停")
            pause_btn.setObjectName("pause_btn")
            pause_btn.clicked.connect(lambda: self.pause_task(task_frame))  # type: ignore
            button_layout.addWidget(pause_btn)

            resume_btn = QPushButton("继续")
            resume_btn.setObjectName("resume_btn")
            resume_btn.setEnabled(False)
            resume_btn.clicked.connect(lambda: self.resume_task(task_frame))  # type: ignore
            button_layout.addWidget(resume_btn)

            stop_btn = QPushButton("停止")
            stop_btn.setObjectName("stop_btn")
            stop_btn.clicked.connect(lambda: self.stop_task(task_frame))  # type: ignore
            button_layout.addWidget(stop_btn)

            task_layout.addLayout(button_layout)

            if self.tasks_layout:
                self.tasks_layout.addWidget(task_frame)

            # 检查当前活动任务数量
            active_count = sum(1 for thread in self.active_threads
                               if thread.isRunning() and not getattr(thread, 'paused', False))

            if active_count < self.max_concurrent_tasks:
                update_task_status(task_frame, "运行中", "#2ecc71")
                self.start_download_task(url, task_frame, task_id)
            else:
                self.pending_tasks.append({
                    "url": url,
                    "frame": task_frame,
                    "task_id": task_id
                })
                self.log_message(f"任务已添加到队列，当前队列位置: {len(self.pending_tasks)}")
                self.update_queue_status()

            if self.stop_btn:
                self.stop_btn.setEnabled(True)

        except Exception as e:
            print(f"启动下载出错: {e}")
            self.log_message(f"启动下载出错: {str(e)}")

    def start_download_task(self, url: str, task_frame: QFrame, task_id: str) -> None:
        """启动下载线程"""
        try:
            self.log_message(f"启动新下载任务: {url}")
            self.log_message(f"下载路径: {self.download_dir}")

            thread = VideoDownloadThread(url, self.download_dir, task_id)
            thread.task_frame = task_frame
            thread.task_id = task_id

            # 连接信号
            thread.log_signal.connect(self.log_message)
            thread.finished_signal.connect(self.on_download_finished)

            self.active_threads.append(thread)

            if task_id.startswith("failed_retry_"):
                update_task_status(task_frame, "运行中", "#2ecc71")
            else:
                active_count = sum(1 for t in self.active_threads if t.isRunning())
                if active_count <= self.max_concurrent_tasks:
                    update_task_status(task_frame, "运行中", "#2ecc71")
                else:
                    update_task_status(task_frame, "队列中", "#f39c12")

            thread.start()

        except Exception as e:
            print(f"启动下载线程出错: {e}")
            self.log_message(f"启动下载线程出错: {str(e)}")

    def on_download_finished(self, task_id: str, failed_urls: List[str]) -> None:
        """下载完成处理"""
        try:
            # 查找对应的线程和任务框
            thread = None
            task_frame = None

            for t in self.active_threads:
                if t.task_id == task_id:
                    thread = t
                    task_frame = t.task_frame
                    break

            if thread and thread in self.active_threads:
                self.active_threads.remove(thread)

            # 从界面移除任务框
            if task_frame and task_frame.parent():
                task_frame.deleteLater()

            # 处理失败的任务
            if failed_urls:
                self.log_message(f"任务 {task_id} 完成，有 {len(failed_urls)} 个失败视频")
                self.handle_failed_tasks(task_id, failed_urls)
            else:
                self.log_message(f"任务 {task_id} 完成")

            # 启动下一个等待任务
            self.start_next_task()

        except Exception as e:
            print(f"下载完成处理出错: {e}")

    def handle_failed_tasks(self, task_id: str, failed_urls: List[str]) -> None:
        """处理失败的任务，将其以暂停状态重新加入队列"""
        try:
            if not failed_urls:
                return

            task_frame = self.findChild(QFrame, task_id)
            if not task_frame:
                return

            original_url = getattr(task_frame, 'url', '')
            if not original_url:
                return

            for i, video_url in enumerate(failed_urls):
                new_task_id = f"{task_id}_failed_{i}"

                failed_frame = QFrame()
                failed_frame.setFrameShape(QFrame.StyledPanel)
                failed_frame.setObjectName(new_task_id)
                failed_frame.url = video_url
                failed_layout = QVBoxLayout(failed_frame)

                task_label = QLabel(f"失败重试: {video_url}")
                task_label.setStyleSheet("color: #ecf0f1; font-weight: bold;")
                failed_layout.addWidget(task_label)

                status_label = QLabel("状态: 已暂停")
                status_label.setStyleSheet("color: #f39c12;")
                status_label.setObjectName("status_label")
                failed_layout.addWidget(status_label)

                button_layout = QHBoxLayout()

                pause_btn = QPushButton("暂停")
                pause_btn.setObjectName("pause_btn")
                pause_btn.setEnabled(False)
                pause_btn.clicked.connect(lambda: self.pause_task(failed_frame))  # type: ignore
                button_layout.addWidget(pause_btn)

                resume_btn = QPushButton("继续")
                resume_btn.setObjectName("resume_btn")
                resume_btn.setEnabled(True)
                resume_btn.clicked.connect(lambda: self.resume_task(failed_frame))  # type: ignore
                button_layout.addWidget(resume_btn)

                stop_btn = QPushButton("停止")
                stop_btn.setObjectName("stop_btn")
                stop_btn.clicked.connect(lambda: self.stop_task(failed_frame))  # type: ignore
                button_layout.addWidget(stop_btn)

                failed_layout.addLayout(button_layout)
                if self.tasks_layout:
                    self.tasks_layout.addWidget(failed_frame)

                self.pending_tasks.append({
                    "url": video_url,
                    "frame": failed_frame,
                    "task_id": new_task_id
                })

            self.log_message(f"已将 {len(failed_urls)} 个失败视频以暂停状态加入下载队列")
            self.update_queue_status()

        except Exception as e:
            print(f"处理失败任务出错: {e}")

    def start_next_task(self) -> None:
        """启动下一个等待中的任务"""
        try:
            if self.pending_tasks:
                next_task = self.pending_tasks.pop(0)
                self.start_download_task(next_task["url"], next_task["frame"], next_task["task_id"])
                self.update_queue_status()
        except Exception as e:
            print(f"启动下一个任务出错: {e}")

    def update_queue_status(self) -> None:
        """更新队列中任务的状态显示"""
        try:
            for i, task in enumerate(self.pending_tasks):
                update_task_status(task["frame"], f"队列中 ({i + 1})", "#f39c12")
        except Exception as e:
            print(f"更新队列状态出错: {e}")

    def pause_task(self, task_frame: QFrame) -> None:
        """暂停任务"""
        try:
            for thread in self.active_threads:
                if hasattr(thread, 'task_frame') and thread.task_frame == task_frame:
                    thread.pause()
                    update_task_status(task_frame, "已暂停", "#f39c12")
                    self.log_message(f"任务已暂停: {thread.list_url}")
                    break
        except Exception as e:
            print(f"暂停任务出错: {e}")

    def resume_task(self, task_frame: QFrame) -> None:
        """继续任务"""
        try:
            for thread in self.active_threads:
                if hasattr(thread, 'task_frame') and thread.task_frame == task_frame:
                    thread.resume()
                    update_task_status(task_frame, "运行中", "#2ecc71")
                    self.log_message(f"任务已继续: {thread.list_url}")
                    break
        except Exception as e:
            print(f"继续任务出错: {e}")

    def stop_task(self, task_frame: QFrame) -> None:
        """停止单个任务"""
        try:
            # 停止活动线程中的任务
            for thread in self.active_threads:
                if hasattr(thread, 'task_frame') and thread.task_frame == task_frame:
                    thread.stop()
                    if thread.isRunning():
                        thread.wait(5000)  # 等待线程停止
                    self.log_message(f"任务已停止: {thread.list_url}")
                    if thread in self.active_threads:
                        self.active_threads.remove(thread)
                    if task_frame and task_frame.parent():
                        task_frame.deleteLater()
                    self.start_next_task()
                    return

            # 停止等待队列中的任务
            for task in self.pending_tasks:
                if task["frame"] == task_frame:
                    self.pending_tasks.remove(task)
                    self.log_message(f"已从队列中移除任务: {task['url']}")
                    if task_frame and task_frame.parent():
                        task_frame.deleteLater()
                    self.update_queue_status()
                    return
        except Exception as e:
            print(f"停止单个任务出错: {e}")

    def stop_all_downloads(self) -> None:
        """停止所有下载任务"""
        try:
            # 停止所有活动线程
            for thread in self.active_threads[:]:  # 使用副本遍历
                try:
                    if thread.isRunning():
                        thread.stop()
                        thread.wait(5000)  # 等待5秒让线程停止
                    self.log_message(f"已停止任务: {thread.list_url}")
                except Exception as e:
                    self.log_message(f"停止任务时出错: {str(e)}")

            # 清除所有等待任务
            self.pending_tasks.clear()

            # 清除所有任务显示
            if self.tasks_layout:
                for i in reversed(range(self.tasks_layout.count())):
                    widget = self.tasks_layout.itemAt(i).widget()
                    if widget:
                        widget.deleteLater()

            # 重置状态
            self.active_threads.clear()
            if self.stop_btn:
                self.stop_btn.setEnabled(False)
            self.log_message("已停止所有下载任务")
        except Exception as e:
            print(f"停止所有下载任务出错: {e}")

    def change_download_path(self) -> None:
        """更改下载路径"""
        try:
            new_path = QFileDialog.getExistingDirectory(
                self,
                "选择下载目录",
                self.download_dir,
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )

            if new_path:
                self.download_dir = new_path
                if self.download_path_label:
                    self.download_path_label.setText(f"当前下载路径: {self.download_dir}")
                self.save_config()
                self.log_message(f"下载路径已更新为: {self.download_dir}")
        except Exception as e:
            print(f"更改下载路径出错: {e}")

    def closeEvent(self, event) -> None:
        """关闭窗口时停止所有线程"""
        try:
            if self.active_threads or self.pending_tasks:
                reply = QMessageBox.question(
                    self,
                    "确认退出",
                    "有任务正在运行，确定要退出吗？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    self.stop_all_downloads()
                    time.sleep(2)  # 给线程更多时间停止
                    event.accept()
                else:
                    event.ignore()
            else:
                event.accept()
        except Exception as e:
            print(f"关闭事件出错: {e}")
            event.accept()