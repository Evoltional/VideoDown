import os
import time
import json
from typing import Optional, Dict, Any, List
from PyQt5.QtCore import pyqtSignal, QObject


class LogEmitter(QObject):
    log_signal = pyqtSignal(str)  # type: ignore


class TaskLogger:
    """任务日志管理器，用于恢复未完成任务"""

    def __init__(self, logger_dir: str = "./logger"):
        self.logger_dir = logger_dir
        self.pending_tasks_file = os.path.join(logger_dir, "pending_tasks.json")
        os.makedirs(logger_dir, exist_ok=True)

    def log_task_start(self, task_id: str, url: str, download_dir: str,
                       task_type: str = "playlist", retry_count: int = 0) -> None:
        """记录任务开始"""
        try:
            tasks = self._load_tasks()
            tasks[task_id] = {
                "task_id": task_id,
                "url": url,
                "download_dir": download_dir,
                "task_type": task_type,
                "status": "pending",  # pending, running, paused, failed, completed
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "failed_videos": [],  # 存储失败视频的URL
                "completed_videos": [],  # 存储成功下载的视频URL
                "total_videos": 0,
                "retry_count": retry_count,  # 重试次数
                "last_error": None  # 上次错误信息
            }
            self._save_tasks(tasks)
        except Exception as e:
            print(f"记录任务开始失败: {str(e)}")

    def log_task_update(self, task_id: str, **kwargs) -> None:
        """更新任务信息"""
        try:
            tasks = self._load_tasks()
            if task_id in tasks:
                tasks[task_id].update(kwargs)
                tasks[task_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self._save_tasks(tasks)
        except Exception as e:
            print(f"更新任务失败: {str(e)}")

    def log_task_completed(self, task_id: str) -> None:
        """记录任务完成"""
        try:
            tasks = self._load_tasks()
            if task_id in tasks:
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self._save_tasks(tasks)
        except Exception as e:
            print(f"记录任务完成失败: {str(e)}")

    def log_task_failed(self, task_id: str, failed_urls: List[str], error: str = "") -> None:
        """记录任务失败（部分视频失败）"""
        try:
            tasks = self._load_tasks()
            if task_id in tasks:
                tasks[task_id]["status"] = "failed"

                tasks[task_id]["failed_videos"] = failed_urls
                tasks[task_id]["last_error"] = error
                tasks[task_id]["retry_count"] = tasks[task_id].get("retry_count", 0) + 1
                tasks[task_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self._save_tasks(tasks)
        except Exception as e:
            print(f"记录任务失败失败: {str(e)}")

    def add_failed_video(self, task_id: str, video_url: str) -> None:
        """添加失败视频到任务记录"""
        try:
            tasks = self._load_tasks()
            if task_id in tasks:
                if video_url not in tasks[task_id]["failed_videos"]:
                    tasks[task_id]["failed_videos"].append(video_url)
                    tasks[task_id]["status"] = "failed"
                    tasks[task_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    self._save_tasks(tasks)
        except Exception as e:
            print(f"添加失败视频失败: {str(e)}")

    def remove_task(self, task_id: str) -> None:
        """移除任务记录"""
        try:
            tasks = self._load_tasks()
            if task_id in tasks:
                del tasks[task_id]
                self._save_tasks(tasks)
        except Exception as e:
            print(f"移除任务失败: {str(e)}")

    def get_pending_tasks(self) -> Dict[str, Any]:
        """获取所有未完成任务"""
        try:
            tasks = self._load_tasks()
            # 过滤出未完成的任务
            pending_tasks = {k: v for k, v in tasks.items()
                             if v["status"] in ["pending", "running", "paused", "failed"]}
            return pending_tasks
        except Exception as e:
            print(f"获取未完成任务失败: {str(e)}")
            return {}

    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取特定任务信息"""
        try:
            tasks = self._load_tasks()
            return tasks.get(task_id)
        except Exception:
            return None

    def _load_tasks(self) -> Dict[str, Any]:
        """加载任务文件"""
        try:
            if os.path.exists(self.pending_tasks_file):
                with open(self.pending_tasks_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_tasks(self, tasks: Dict[str, Any]) -> None:
        """保存任务文件"""
        try:
            with open(self.pending_tasks_file, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存任务文件失败: {str(e)}")


def log_failure(logger_dir: str, filename: str, url: str, error: str = "") -> Optional[str]:
    """记录下载失败到日志文件"""
    try:
        # 创建日志文件路径（按日期）
        log_file = os.path.join(logger_dir, f"{time.strftime('%Y-%m-%d')}.log")
        # 日志内容
        log_content = (
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"下载失败: 文件名: {filename}, "
            f"URL: {url}, "
            f"错误: {error}\n"
        )
        # 写入日志文件（追加模式）
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_content)
    except Exception as e:
        return f"记录失败日志时出错: {str(e)}"
    return None