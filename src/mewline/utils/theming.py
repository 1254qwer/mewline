import re
from pathlib import Path

from fabric import Application
from fabric.utils import exec_shell_command
from loguru import logger

import mewline.constants as cnst
from mewline.errors.settings import ExecutableNotFoundError
from mewline.utils.misc import executable_exists


# 匹配顶层 SCSS 变量声明，例如：$name: value;
# 仅匹配行首定义的变量（不处理嵌套作用域变量）
_SCSS_VAR_RE = re.compile(
    r"^\$([a-zA-Z0-9_-]+)\s*:\s*(.+?)\s*;",
    re.MULTILINE
)


def _parse_scss_vars(content: str) -> dict[str, str]:
    """
    解析 SCSS 文件内容，提取所有顶层变量声明。

    返回格式：
        {
            "var_name": "value",
            ...
        }
    """
    return {
        m.group(1): m.group(2)
        for m in _SCSS_VAR_RE.finditer(content)
    }


def process_and_apply_css(app: Application):
    """
    编译主 SCSS 文件并应用到应用程序。

    流程：
    1. 检查系统中是否存在 sass 可执行文件
    2. 编译 SCSS 为 CSS
    3. 将生成的 CSS 设置为应用样式表
    """

    # 如果未安装 sass，则抛出异常并终止流程
    if not executable_exists("sass"):
        raise ExecutableNotFoundError("sass")

    logger.info("[Main] 正在编译 CSS")

    # 调用 sass 命令行工具编译样式
    exec_shell_command(
        f"sass {cnst.MAIN_STYLE} {cnst.COMPILED_STYLE} --no-source-map"
    )

    logger.info("[Main] CSS 应用完成")

    # 将编译后的 CSS 文件应用到应用程序
    app.set_stylesheet_from_file(cnst.COMPILED_STYLE)


def copy_theme(path: Path):
    """
    合并默认主题变量与用户自定义变量，并写入 theme.scss。

    规则：
    - 用户主题文件中的变量优先级高于默认主题
    - 用户未定义的变量自动回退到默认主题值
    - 这样可以保证当默认主题新增变量时，旧主题仍然可正常工作

    示例：
    如果默认主题新增 $privacy-dot-color，
    而用户主题未定义该变量，则自动继承默认值。
    """

    # 如果指定的是 default，则强制使用默认主题路径
    if path.stem == "default":
        path = cnst.DEFAULT_THEME_STYLE

    # 如果主题文件不存在，回退到默认主题
    if not path.exists():
        logger.warning(
            f"警告：主题文件 '{path}' 未找到，使用默认主题。"
        )
        path = cnst.DEFAULT_THEME_STYLE

    try:
        # 读取默认主题变量
        with open(cnst.DEFAULT_THEME_STYLE) as f:
            default_vars = _parse_scss_vars(f.read())

        user_vars: dict[str, str] = {}

        # 如果用户选择的不是默认主题，则解析用户主题变量
        if path != cnst.DEFAULT_THEME_STYLE:
            with open(path) as f:
                user_vars = _parse_scss_vars(f.read())

        # 合并变量：
        # 后面的字典会覆盖前面的字典（用户变量优先）
        merged = {**default_vars, **user_vars}

        # 写入最终 theme.scss 文件
        with open(cnst.THEME_STYLE, "w") as f:
            for name, value in merged.items():
                f.write(f"${name}: {value};\n")

        logger.info(f"[THEME] 主题 '{path}' 应用成功。")

    except FileNotFoundError:
        logger.error(f"错误：主题文件 '{path}' 未找到。")
        exit(1)