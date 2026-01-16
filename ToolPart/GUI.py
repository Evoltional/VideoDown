import configparser
import os
import time
import uuid
from typing import List, Dict, Any

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox,
                             QScrollArea, QFrame, QFileDialog, QMessageBox)

from ToolPart.DownloadThread import VideoDownloadThread
from ToolPart.Logger import LogEmitter, TaskLogger


def update_task_status(task_frame: QFrame, status: str, color: str) -> None:
    """更新任务状态显示"""
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
        self.task_logger = TaskLogger()  # 任务日志管理器
        self.max_concurrent_tasks = 2  # 减少并发任务数

        # 加载配置文件
        self.config = configparser.ConfigParser()
        self.config_file = "./config.ini"
        self.download_dir = self.load_config()

        self.init_ui()
        self.restore_pending_tasks()  # 恢复未完成任务

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

    def restore_pending_tasks(self) -> None:
        """恢复未完成的任务"""
        try:
            # 获取所有待处理任务
            pending_tasks = self.task_logger.get_pending_tasks()
            self.log_message(f"找到 {len(pending_tasks)} 个未完成的任务")

            for task_info in pending_tasks:
                task_id = task_info["task_id"]
                url = task_info["url"]
                download_dir = task_info.get("download_dir", self.download_dir)
                status = task_info.get("status", "pending")
                task_type = task_info.get("task_type", "playlist")

                self.log_message(f"恢复任务: {url} (状态: {status}, 类型: {task_type})")

                # 创建任务显示框
                task_frame = QFrame()
                task_frame.setFrameShape(QFrame.StyledPanel)
                task_frame.setObjectName(task_id)
                task_frame.url = url
                task_layout = QVBoxLayout(task_frame)

                # 显示任务类型
                task_type_text = "播放列表" if task_type == "playlist" else "单视频"
                if status == "failed":
                    task_label_text = f"失败任务[{task_type_text}]: {url}"
                elif task_type == "playlist":
                    task_label_text = f"{url}"
                else:
                    task_label_text = f"视频: {url}"

                task_label = QLabel(task_label_text)
                task_label.setStyleSheet("color: #ecf0f1; font-weight: bold;")
                task_layout.addWidget(task_label)

                status_label = QLabel(f"状态: {status}")
                status_label.setObjectName("status_label")
                task_layout.addWidget(status_label)

                # 显示进度信息
                total_videos = task_info.get("total_videos", 0)
                completed_videos = len(task_info.get("completed_videos", []))
                failed_videos = len(task_info.get("failed_videos", []))

                progress_text = f"进度: {completed_videos}/{total_videos}"
                if failed_videos > 0:
                    progress_text += f" (失败: {failed_videos})"

                progress_label = QLabel(progress_text)
                progress_label.setStyleSheet("color: #95a5a6;")
                task_layout.addWidget(progress_label)

                # 按钮布局
                button_layout = QHBoxLayout()

                pause_btn = QPushButton("暂停")
                pause_btn.setObjectName("pause_btn")
                pause_btn.clicked.connect(lambda: self.pause_task(task_frame))  # type: ignore
                button_layout.addWidget(pause_btn)

                resume_btn = QPushButton("继续")
                resume_btn.setObjectName("resume_btn")
                resume_btn.clicked.connect(lambda: self.resume_task(task_frame))  # type: ignore
                button_layout.addWidget(resume_btn)

                stop_btn = QPushButton("停止")
                stop_btn.setObjectName("stop_btn")
                stop_btn.clicked.connect(lambda: self.stop_task(task_frame))  # type: ignore
                button_layout.addWidget(stop_btn)

                # 如果是失败任务，添加重新开始按钮
                if status == "failed":
                    retry_btn = QPushButton("重新开始")
                    retry_btn.setObjectName("retry_btn")
                    retry_btn.setStyleSheet("background-color: #e74c3c;")
                    retry_btn.clicked.connect(lambda: self.retry_task(task_frame))  # type: ignore
                    button_layout.addWidget(retry_btn)

                task_layout.addLayout(button_layout)
                self.tasks_layout.addWidget(task_frame)

                # 根据状态设置颜色和按钮状态
                if status == "paused":
                    status_label.setStyleSheet("color: #f39c12;")
                    pause_btn.setEnabled(False)
                    resume_btn.setEnabled(True)
                    # 添加到队列但不立即启动
                    self.pending_tasks.append({
                        "url": url,
                        "frame": task_frame,
                        "task_id": task_id,
                        "task_type": task_type,
                        "status": "paused"
                    })
                elif status == "failed":
                    status_label.setStyleSheet("color: #e74c3c;")
                    pause_btn.setEnabled(False)
                    resume_btn.setEnabled(False)
                    # 失败任务添加到队列末尾，状态为paused
                    self.pending_tasks.append({
                        "url": url,
                        "frame": task_frame,
                        "task_id": task_id,
                        "task_type": task_type,
                        "status": "paused"  # 失败任务以暂停状态加入队列
                    })
                else:  # running or pending
                    color = "#2ecc71" if status == "running" else "#f39c12"
                    status_label.setStyleSheet(f"color: {color};")
                    pause_btn.setEnabled(status == "running")
                    resume_btn.setEnabled(False)
                    # 添加到等待队列
                    self.pending_tasks.append({
                        "url": url,
                        "frame": task_frame,
                        "task_id": task_id,
                        "task_type": task_type,
                        "status": "pending"
                    })

                self.log_message(f"任务已添加到队列: {url}")

            if self.pending_tasks:
                self.stop_btn.setEnabled(True)
                self.update_queue_status()

                # 启动队列中的任务
                self.start_next_task()

        except Exception as e:
            self.log_message(f"恢复任务失败: {str(e)}")

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

        # 创建输入框和粘贴按钮的水平布局
        url_input_layout = QHBoxLayout()

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("例如: https://hanime1.me/watch?v=????")
        url_input_layout.addWidget(self.url_input, 1)  # 添加拉伸因子1，让输入框占据更多空间

        # 添加粘贴按钮
        paste_btn = QPushButton("粘贴")
        paste_btn.setFixedWidth(100)  # 设置固定宽度
        paste_btn.clicked.connect(self.paste_clipboard)  # type: ignore
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

    def paste_clipboard(self) -> None:
        """粘贴剪贴板内容到输入框"""
        try:
            # 导入剪贴板模块
            from PyQt5.QtWidgets import QApplication

            # 获取剪贴板内容
            clipboard = QApplication.clipboard()
            text = clipboard.text().strip()

            if text:
                self.url_input.setText(text)
                self.log_message(f"已粘贴剪贴板内容: {text[:50]}{'...' if len(text) > 50 else ''}")
            else:
                self.log_message("剪贴板为空或内容不是文本")

        except Exception as e:
            self.log_message(f"粘贴失败: {str(e)}")

    def log_message(self, message: str) -> None:
        """添加消息到日志区域"""
        if message.startswith("[TITLE_UPDATE]|||"):
            parts = message.split("|||")
            if len(parts) >= 3:
                task_id = parts[1]
                playlist_title = parts[2]
                self.update_task_title(task_id, playlist_title)
        else:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            self.log_area.append(f"[{timestamp}] {message}")
            # 自动滚动到底部
            self.log_area.verticalScrollBar().setValue(
                self.log_area.verticalScrollBar().maximum()
            )

    def update_task_title(self, task_id: str, playlist_title: str) -> None:
        """更新任务标题显示播放列表名称"""
        task_frame = self.findChild(QFrame, task_id)
        if task_frame:
            url = getattr(task_frame, 'url', '未知URL')
            task_label = task_frame.findChild(QLabel)
            if task_label:
                task_label.setText(f"{playlist_title} ({url})")

    def start_download(self) -> None:
        """开始新的下载任务"""
        url = self.url_input.text().strip()
        if not url:
            self.log_message("请输入有效的URL")
            return

        self.url_input.clear()

        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 记录任务开始
        self.task_logger.log_task_start(task_id, url, self.download_dir)

        # 创建任务显示框
        task_frame = QFrame()
        task_frame.setFrameShape(QFrame.StyledPanel)
        task_frame.setObjectName(task_id)
        task_frame.url = url
        task_layout = QVBoxLayout(task_frame)

        task_label = QLabel(f"{url}")
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
                "task_id": task_id,
                "task_type": "playlist",
                "status": "pending"
            })
            self.log_message(f"任务已添加到队列，当前队列位置: {len(self.pending_tasks)}")
            self.update_queue_status()

        self.stop_btn.setEnabled(True)

    def start_download_task(self, url: str, task_frame: QFrame, task_id: str, is_retry: bool = False) -> None:
        """启动下载线程"""
        self.log_message(f"启动新下载任务: {url}")
        self.log_message(f"下载路径: {self.download_dir}")

        # 更新任务状态为运行中
        self.task_logger.update_task_status(task_id, "running")

        thread = VideoDownloadThread(url, self.download_dir, task_id, self.task_logger, is_retry)
        thread.task_frame = task_frame
        thread.task_id = task_id

        # 连接信号
        thread.log_signal.connect(self.log_message)
        thread.finished_signal.connect(self.on_download_finished)

        self.active_threads.append(thread)

        update_task_status(task_frame, "运行中", "#2ecc71")
        thread.start()

    def on_download_finished(self, task_id: str, failed_urls: List[str]) -> None:
        """下载完成处理"""
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

        # 获取任务信息
        task_info = self.task_logger.get_task_info(task_id)
        if not task_info:
            # 如果任务信息不存在，说明任务已完成并被删除
            self.log_message(f"任务 {task_id} 已完成并从记录中删除")
            if task_frame and task_frame.parent():
                task_frame.deleteLater()

            # 启动下一个任务
            self.start_next_task()
            return

        task_type = task_info.get("task_type", "playlist")
        status = task_info.get("status", "completed")

        # 从界面移除任务框（如果是播放列表任务且已完成）
        if status == "completed" and task_type == "playlist":
            self.log_message(f"任务 {task_id} 完成")
            if task_frame and task_frame.parent():
                task_frame.deleteLater()
        elif status == "failed":
            self.log_message(f"任务 {task_id} 失败，有 {len(failed_urls)} 个失败视频")

            # 更新任务显示
            if task_frame:
                # 更新状态标签
                status_label = task_frame.findChild(QLabel, "status_label")
                if status_label:
                    status_label.setText("状态: 失败")
                    status_label.setStyleSheet("color: #e74c3c;")

                # 更新进度信息
                completed_videos = len(task_info.get("completed_videos", []))
                total_videos = task_info.get("total_videos", 0)

                # 查找进度标签
                for widget in task_frame.children():
                    if isinstance(widget, QLabel) and widget.text().startswith("进度:"):
                        widget.setText(f"进度: {completed_videos}/{total_videos} (失败: {len(failed_urls)})")
                        break

                # 添加重新开始按钮
                button_layout = task_frame.findChild(QHBoxLayout)
                if button_layout:
                    # 移除现有的重新开始按钮（如果有）
                    for i in reversed(range(button_layout.count())):
                        item = button_layout.itemAt(i)
                        if item and item.widget():
                            widget = item.widget()
                            if widget.objectName() == "retry_btn":
                                button_layout.removeWidget(widget)
                                widget.deleteLater()

                    # 添加新的重新开始按钮
                    retry_btn = QPushButton("重新开始")
                    retry_btn.setObjectName("retry_btn")
                    retry_btn.setStyleSheet("background-color: #e74c3c;")
                    retry_btn.clicked.connect(lambda: self.retry_task(task_frame))  # type: ignore
                    button_layout.addWidget(retry_btn)
        else:
            self.log_message(f"任务 {task_id} 状态: {status}")

        # 启动下一个等待任务
        self.start_next_task()

    def start_next_task(self) -> None:
        """启动下一个等待中的任务"""
        if self.pending_tasks:
            # 查找第一个状态不是"paused"的任务
            for i, task in enumerate(self.pending_tasks):
                if task.get("status") != "paused":
                    next_task = self.pending_tasks.pop(i)
                    update_task_status(next_task["frame"], "运行中", "#2ecc71")
                    self.start_download_task(next_task["url"], next_task["frame"], next_task["task_id"])
                    self.update_queue_status()
                    return

    def update_queue_status(self) -> None:
        """更新队列中任务的状态显示"""
        for i, task in enumerate(self.pending_tasks):
            if task.get("status") == "paused":
                update_task_status(task["frame"], "已暂停", "#f39c12")
            else:
                update_task_status(task["frame"], f"队列中 ({i + 1})", "#f39c12")

    def pause_task(self, task_frame: QFrame) -> None:
        """暂停任务"""
        task_id = task_frame.objectName()

        # 首先检查任务是否在活动线程中
        found_in_active = False
        for thread in self.active_threads:
            if hasattr(thread, 'task_frame') and thread.task_frame == task_frame:
                thread.pause()
                update_task_status(task_frame, "已暂停", "#f39c12")
                self.log_message(f"任务已暂停: {thread.list_url}")

                # 更新任务状态
                task_id = thread.task_id
                if self.task_logger:
                    self.task_logger.update_task_status(task_id, "paused")

                # 更新pending_tasks中的状态
                for task in self.pending_tasks:
                    if task["frame"] == task_frame:
                        task["status"] = "paused"
                        break
                found_in_active = True
                break

        # 如果不在活动线程中，说明这是一个队列中的任务
        if not found_in_active:
            # 在pending_tasks中找到这个任务
            for task in self.pending_tasks:
                if task["frame"] == task_frame and task.get("status") != "paused":
                    # 更新状态
                    update_task_status(task_frame, "已暂停", "#f39c12")
                    task["status"] = "paused"

                    # 更新任务日志
                    if self.task_logger:
                        self.task_logger.update_task_status(task["task_id"], "paused")

                    self.log_message(f"任务已暂停: {task['url']}")
                    break

    def resume_task(self, task_frame: QFrame) -> None:
        """继续任务"""
        task_id = task_frame.objectName()

        # 首先检查任务是否在活动线程中
        found_in_active = False
        for thread in self.active_threads:
            if hasattr(thread, 'task_frame') and thread.task_frame == task_frame:
                thread.resume()
                update_task_status(task_frame, "运行中", "#2ecc71")
                self.log_message(f"任务已继续: {thread.list_url}")

                # 更新任务状态
                task_id = thread.task_id
                if self.task_logger:
                    self.task_logger.update_task_status(task_id, "running")

                # 更新pending_tasks中的状态
                for task in self.pending_tasks:
                    if task["frame"] == task_frame:
                        task["status"] = "running"
                        break
                found_in_active = True
                break

        # 如果不在活动线程中，说明这是一个暂停的队列任务
        if not found_in_active:
            # 在pending_tasks中找到这个任务
            for task in self.pending_tasks:
                if task["frame"] == task_frame and task.get("status") == "paused":
                    # 更新状态
                    update_task_status(task_frame, "运行中", "#2ecc71")
                    task["status"] = "running"

                    # 更新任务日志
                    if self.task_logger:
                        self.task_logger.update_task_status(task["task_id"], "running")

                    self.log_message(f"任务已恢复: {task['url']}")

                    # 检查当前活动任务数量
                    active_count = sum(1 for thread in self.active_threads
                                       if thread.isRunning() and not getattr(thread, 'paused', False))

                    # 如果并发数允许，立即启动这个任务
                    if active_count < self.max_concurrent_tasks:
                        # 从pending_tasks中移除并立即启动
                        self.pending_tasks.remove(task)
                        self.start_download_task(task["url"], task["frame"], task["task_id"])
                    else:
                        # 保持在队列中，但状态为运行中
                        self.log_message("并发任务数已达上限，任务保持在队列中")
                        update_task_status(task_frame, "队列中", "#f39c12")

                    self.update_queue_status()
                    break

    def retry_task(self, task_frame: QFrame) -> None:
        """重新开始失败的任务"""
        task_id = task_frame.objectName()

        # 获取任务信息
        task_info = self.task_logger.get_task_info(task_id)
        if not task_info:
            self.log_message(f"任务信息不存在: {task_id}")
            return

        url = task_info["url"]
        task_type = task_info.get("task_type", "playlist")

        self.log_message(f"重新开始任务: {url} (类型: {task_type})")

        # 清空任务状态
        cleared_task_info = self.task_logger.clear_task_status(task_id)
        if not cleared_task_info:
            self.log_message("清空任务状态失败")
            return

        # 生成新的任务ID（或者使用原ID但清空状态）
        # 这里我们使用原ID，但状态已清空

        # 更新界面显示
        task_frame.url = url

        # 更新任务标签
        task_label = task_frame.findChild(QLabel)
        if task_label:
            if task_type == "playlist":
                task_label.setText(f"{url}")
            else:
                task_label.setText(f"视频: {url}")

        # 更新状态标签
        status_label = task_frame.findChild(QLabel, "status_label")
        if status_label:
            status_label.setText("状态: 已暂停")
            status_label.setStyleSheet("color: #f39c12;")

        # 移除重新开始按钮
        retry_btn = task_frame.findChild(QPushButton, "retry_btn")
        if retry_btn:
            retry_btn.deleteLater()

        # 启用继续按钮
        resume_btn = task_frame.findChild(QPushButton, "resume_btn")
        if resume_btn:
            resume_btn.setEnabled(True)

        # 更新pending_tasks中的状态
        for task in self.pending_tasks:
            if task["frame"] == task_frame:
                task["status"] = "paused"
                break

        self.log_message(f"任务已重置，可以点击继续按钮开始下载")

    def stop_task(self, task_frame: QFrame) -> None:
        """停止单个任务"""
        task_id = task_frame.objectName()

        # 停止活动线程中的任务
        for thread in self.active_threads:
            if hasattr(thread, 'task_frame') and thread.task_frame == task_frame:
                thread.stop()
                if thread.isRunning():
                    thread.wait(5000)  # 等待线程停止
                self.log_message(f"任务已停止: {thread.list_url}")

                # 移除任务记录
                task_id = thread.task_id
                self.task_logger.remove_task(task_id)

                if thread in self.active_threads:
                    self.active_threads.remove(thread)
                if task_frame and task_frame.parent():
                    task_frame.deleteLater()

                # 从pending_tasks中移除
                self.pending_tasks = [t for t in self.pending_tasks if t["frame"] != task_frame]

                self.start_next_task()
                return

        # 停止等待队列中的任务
        for task in self.pending_tasks:
            if task["frame"] == task_frame:
                self.pending_tasks.remove(task)
                self.log_message(f"已从队列中移除任务: {task['url']}")

                # 移除任务记录
                task_id = task["task_id"]
                self.task_logger.remove_task(task_id)

                if task_frame and task_frame.parent():
                    task_frame.deleteLater()
                self.update_queue_status()
                return

    def stop_all_downloads(self) -> None:
        """停止所有下载任务"""
        # 停止所有活动线程
        for thread in self.active_threads[:]:  # 使用副本遍历
            try:
                if thread.isRunning():
                    thread.stop()
                    thread.wait(5000)  # 等待5秒让线程停止
                self.log_message(f"已停止任务: {thread.list_url}")

                # 更新任务状态为暂停
                task_id = thread.task_id
                self.task_logger.update_task_status(task_id, "paused")
            except Exception as e:
                self.log_message(f"停止任务时出错: {str(e)}")

        # 更新所有等待任务的状态为暂停
        for task in self.pending_tasks:
            if task.get("status") != "paused":
                task["status"] = "paused"
                update_task_status(task["frame"], "已暂停", "#f39c12")
                self.task_logger.update_task_status(task["task_id"], "paused")

        # 清除活动线程列表
        self.active_threads.clear()
        self.stop_btn.setEnabled(False)
        self.log_message("已停止所有下载任务，任务状态已保存")

    def change_download_path(self) -> None:
        """更改下载路径"""
        new_path = QFileDialog.getExistingDirectory(
            self,
            "选择下载目录",
            self.download_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if new_path:
            self.download_dir = new_path
            self.download_path_label.setText(f"当前下载路径: {self.download_dir}")
            self.save_config()
            self.log_message(f"下载路径已更新为: {self.download_dir}")

    def closeEvent(self, event) -> None:
        """关闭窗口时停止所有线程"""
        if self.active_threads or self.pending_tasks:
            reply = QMessageBox.question(
                self,
                "确认退出",
                "有任务正在运行，确定要退出吗？未完成的任务将自动保存，下次启动时恢复。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 更新所有活动任务状态为暂停
                for thread in self.active_threads:
                    if thread.isRunning():
                        task_id = thread.task_id
                        self.task_logger.update_task_status(task_id, "paused")
                        thread.stop()

                # 更新所有等待任务状态为暂停
                for task in self.pending_tasks:
                    if task.get("status") != "paused":
                        self.task_logger.update_task_status(task["task_id"], "paused")

                # 等待线程停止
                time.sleep(2)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()