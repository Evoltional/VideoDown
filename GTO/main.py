import sys
from PyQt5.QtWidgets import QApplication

from GTO.UIPart.gui import HanimeDownloaderApp


def main():
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle("Fusion")

    window = HanimeDownloaderApp()
    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()