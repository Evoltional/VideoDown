# Hanime视频下载器

这是一个使用Python编写的Hanime视频下载器，支持多线程下载。

## 前置条件

- Python 3.10 或更高版本
- PyQt5
- DrissionPage
- requests

## 功能特性

用户友好界面：直观的GUI设计，支持深色主题

批量下载：支持播放列表链接，自动获取所有视频链接

验证码绕过：内置Cloudflare验证码自动识别与绕过机制

多线程处理：支持后台下载任务，不阻塞主界面

下载管理：支持暂停/恢复/停止下载任务

进度监控：实时显示下载进度和日志信息

## 运行方法

```
python VideoDownLoad.py
```

## 使用说明
需确保网络能访问对应链接

需要本地Chrome浏览器

输入播放列表链接： 在输入框中粘贴hanime1.me播放列表URL

点击开始下载


### 补充
批量下载后推荐使用 [Organize](https://github.com/Evoltional/Organize) 对文件进行整理

绕过 Cloudflare TurnStile 部分参考自 [CloudflareBypassForScraping](https://github.com/sarperavci/CloudflareBypassForScraping)

## 许可证

本项目采用MIT许可证。

## 免责声明

本项目仅供学习和研究使用，请勿用于非法下载。用户需对使用本项目产生的一切后果负责。