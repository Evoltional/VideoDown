import os
import time
from PyQt5.QtCore import pyqtSignal, QObject

class LogEmitter(QObject):
    log_signal = pyqtSignal(str)  # type: ignore

def log_failure(logger_dir: str, filename: str, url: str, error: str = ""):
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