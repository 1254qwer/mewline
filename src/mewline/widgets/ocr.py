import subprocess
import traceback

# 1. 替换 pytesseract，引入 RapidOCR
from rapidocr import RapidOCR
from gi.repository import Gdk
from gi.repository import Gtk
from loguru import logger

from mewline import constants as cnst
from mewline.config import cfg
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.misc import check_tools_available
from mewline.utils.widget_utils import text_icon
from mewline.utils.window_manager import WindowManagerContext


class OCRWidget(ButtonWidget):
    """A widget that provides Optical Character Recognition functionality using RapidOCR.

    Left-click to select an area and copy recognized text to clipboard.
    """

    def __init__(self, **kwargs):
        super().__init__(name="ocr", **kwargs)
        self.config = cfg.modules.ocr
        
        # 2. 初始化 RapidOCR 引擎 (只会加载一次模型，极速响应)
        self.ocr_engine = RapidOCR()

        self.children = text_icon(
            self.config.icon, self.config.icon_size, style_classes="panel-text-icon"
        )

        self.connect("button-press-event", self.on_button_press)

        if self.config.tooltip:
            # 修改了提示词，因为去掉了右键菜单
            self.set_tooltip_text("Left click to OCR (Auto Multi-language)")

    def on_button_press(self, _, event):
        # 3. 去掉了右键菜单逻辑，只保留左键点击截图
        if event.button != 1:
            return

        try:
            if not self._check_prerequisites():
                return

            if (selection := self._get_selection_area()) is None:
                return

            if not self._capture_screenshot(selection):
                return

            if (text := self._extract_text_from_image()) is None:
                return

            self._handle_clipboard(text)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.debug(traceback.format_exc())
        finally:
            self._cleanup_temp_files()

    def _check_prerequisites(self):
        if check_tools_available(["slurp", "grim"]):
            return True
        logger.error("Required tools (slurp/grim) are not installed")
        return False

    def _get_selection_area(self, timeout=30):
        try:
            result = subprocess.run(
                ["slurp"], capture_output=True, text=True, timeout=timeout
            )
            if result.returncode == 1:
                return None
            if result.returncode != 0:
                logger.error(f"Slurp error [{result.returncode}]: {result.stderr.strip()}")
                return None
            if not (selection := result.stdout.strip()):
                return None
            return selection
        except subprocess.TimeoutExpired:
            logger.error("Area selection timed out")
            return None

    def _capture_screenshot(self, selection, timeout=10):
        path_to_img = cnst.APP_CACHE_DIRECTORY / "ocr.png"
        try:
            subprocess.run(
                ["grim", "-g", selection, str(path_to_img)],
                check=True, timeout=timeout,
            )
            return path_to_img if path_to_img.exists() else None
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to capture area: {e}")
        except subprocess.TimeoutExpired:
            logger.error("Screenshot capture timed out")
        return None

    # 4. 核心替换：使用 RapidOCR 提取文本
    def _extract_text_from_image(self):
        """Extract text from an image using RapidOCR (v3.0+ API)."""
        path_to_img = str(cnst.APP_CACHE_DIRECTORY / "ocr.png")

        try:
            # 新版 API 返回的是一个 RapidOCROutput (Dataclass) 对象
            output = self.ocr_engine(path_to_img)

            # 检查是否有识别结果 (如果未识别到，output 可能是 None，或者 txts 为空)
            if output is None or not output.txts:
                logger.warning("No text recognized in selected area")
                return None

            # output.txts 直接就是包含所有文本行的元组，如 ('正品促销', '极速发货')
            # 我们直接用换行符把它们拼成一段完整的字符串
            final_text = "\n".join(output.txts)
            
            # 耗时现在也变成了对象的属性
            logger.info(f"OCR completed in {output.elapse:.2f}s")
            return final_text

        except Exception as e:
            logger.error(f"RapidOCR Error: {e}")
            return None

    def _handle_clipboard(self, text):
        try:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(text, -1)
            clipboard.store()
            logger.info("Text successfully copied to clipboard")
            return True
        except Exception as e:
            logger.error(f"Clipboard error: {e}")
            return False

    def _cleanup_temp_files(self):
        path_to_img = cnst.APP_CACHE_DIRECTORY / "ocr.png"
        try:
            if path_to_img.exists():
                path_to_img.unlink()
        except OSError as e:
            logger.error(f"Failed to clean up temp file: {e}")

    # 彻底删除了原有的 show_language_menu, get_available_languages, get_combined_languages 等赘余方法