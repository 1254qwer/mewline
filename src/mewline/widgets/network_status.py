import subprocess
from threading import Lock

from fabric.utils import exec_shell_command_async
from gi.repository import GLib
from loguru import logger
import os

import mewline.constants as cnst
from mewline.config import cfg
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.widget_utils import text_icon


class NetworkStatus(ButtonWidget):
    """用于显示 Wi-Fi 连接状态的控件。"""

    def __init__(self, **kwargs):
        # 初始化父类按钮组件，名称为 wifi-status
        super().__init__(name="wifi-status", **kwargs)

        # 读取电源/系统模块配置（根据项目结构）
        self.config = cfg.modules.power

        # 用于防止并发更新的锁
        self._update_lock = Lock()

        # 设置鼠标悬浮提示文本
        self.set_tooltip_text("Wi-Fi 状态")

        # 先显示一个加载中的图标
        self._set_loading_icon()

        # 初始化时立即异步更新一次图标
        self._async_update_icon()

        # 点击按钮时打开网络设置界面
        self.connect(
            "clicked",
            lambda *_: exec_shell_command_async(
                cnst.kb_di_open.format(module="network")
            ),
        )

        # 每 3 秒自动刷新一次网络状态
        GLib.timeout_add_seconds(3, self._async_update_icon)

    def _set_loading_icon(self):
        """设置临时加载图标。"""
        self.children = text_icon(
            "󱛄",  # 加载图标
            "16px",
            style_classes="panel-text-icon",
        )

    def _async_update_icon(self):
        """
        启动异步更新图标逻辑。
        通过线程获取网络状态，避免阻塞主线程（GTK UI线程）。
        """
        # 如果当前已有更新任务在执行，则跳过本次刷新
        if self._update_lock.locked():
            return False

        # 加锁后创建新线程执行更新
        with self._update_lock:
            GLib.Thread.new(None, self._update_icon_thread)

        # 返回 True 让 GLib 定时器继续调用
        return True

    def _update_icon_thread(self):
        """
        子线程中执行：
        1. 获取当前网络状态
        2. 如果是 Wi-Fi 已连接，则获取信号强度
        3. 通过 idle_add 回到主线程更新 UI
        """
        try:
            state = self._get_wifi_state()
            signal = self._get_signal_strength() if state == "connected" else 0

            # 在主线程中更新图标（GTK 不允许子线程直接操作 UI）
            GLib.idle_add(self._apply_icon_update, state, signal)

        except Exception as e:
            logger.error(f"更新 Wi-Fi 状态失败: {e}")
            GLib.idle_add(self._set_error_icon)

    def _apply_icon_update(self, state: str, signal: int):
        """
        在主线程中应用图标更新。
        根据连接状态和信号强度选择不同图标。
        """
        if state == "connected":
            # 根据信号强度分级
            if signal > 75:
                icon = "󰤨"  # 信号满格
            elif signal > 50:
                icon = "󰤥"
            elif signal > 25:
                icon = "󰤢"
            else:
                icon = "󰤟"
        elif state == "ethernet":
            icon = "󰈀"  # 有线网络图标
        else:
            icon = "󰤮"  # 未连接图标

        # 更新图标组件
        self.children = text_icon(
            icon,
            "16px",
            style_classes="panel-text-icon",
        )

    def _set_error_icon(self):
        """设置错误状态图标。"""
        self.children = text_icon(
            "󱚼",
            "16px",
            style_classes="panel-text-icon error",
        )

    def _get_wifi_state(self) -> str:
        """
        获取当前网络状态（在子线程中运行）。
        返回值：
            "connected"     -> Wi-Fi 已连接
            "ethernet"      -> 有线网络已连接
            "disconnected"  -> 未连接
            "disabled"      -> Wi-Fi 已关闭
        """
        try:
            # 查询 Wi-Fi 无线电是否开启
            radio_result = subprocess.run(
                ["nmcli", "-f", "WIFI", "radio"],
                capture_output=True,
                text=True,
                check=True,
                # 强制英文输出，避免不同语言导致解析错误
                env=dict(os.environ, LC_ALL="C")
            )
            radio_state = radio_result.stdout.strip()

            # 如果 Wi-Fi 未开启
            if "enabled" not in radio_state:
                return "disabled"

            # 查询所有网络设备状态
            device_result = subprocess.run(
                ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"],
                capture_output=True,
                text=True,
                check=True,
                env=dict(os.environ, LC_ALL="C")
            )
            active_connection = device_result.stdout

            # 解析输出
            for line in active_connection.splitlines():
                if not line.strip():
                    continue

                device, dev_type, state = line.split(":")

                # Wi-Fi 已连接
                if dev_type == "wifi" and state == "connected":
                    return "connected"

                # 有线网络已连接
                elif dev_type == "ethernet" and state == "connected":
                    return "ethernet"

            # 没有找到已连接设备
            return "disconnected"

        except subprocess.CalledProcessError as e:
            logger.error(f"获取网络状态失败: {e.stderr}")
            raise

    def _get_signal_strength(self) -> int:
        """
        获取当前 Wi-Fi 信号强度（0-100）。
        仅在 Wi-Fi 已连接时调用。
        """
        try:
            wifi_result = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SIGNAL", "device", "wifi"],
                capture_output=True,
                text=True,
                check=True,
                env=dict(os.environ, LC_ALL="C")
            )
            output = wifi_result.stdout

            # 查找 ACTIVE 为 yes 的那一行
            for line in output.splitlines():
                if not line.strip():
                    continue

                active, signal = line.split(":")
                if active == "yes":
                    return int(signal)

            return 0

        except subprocess.CalledProcessError as e:
            logger.error(f"获取信号强度失败: {e.stderr}")
            raise