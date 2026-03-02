# 本地魔改版 Mewline PKGBUILD
pkgname=mewline-local
pkgver=1.0.0
pkgrel=1
pkgdesc="😺 Elegant and extensible status bar (Local Modified Version)"
arch=('any')
url="https://github.com/meowrch/mewline"
license=('MIT')
depends=(
  'python' 'power-profiles-daemon' 'gnome-bluetooth-3.0' 'dart-sass'
  'gobject-introspection' 'gray-git' 'fabric-cli' 'tesseract'
  'tesseract-data-eng' 'tesseract-data-rus' 'cliphist' 'brightnessctl' 'ddcutil'
)
makedepends=('python-uv' 'python-virtualenv')
conflicts=('mewline' 'mewline-git')
provides=('mewline')
install=mewline.install
options=('!debug')

# 核心修改：置空 source，告诉 makepkg 不要去网上下载，直接用本地文件
source=()

package() {
  # 指定安装到系统的绝对路径
  local _dest="$pkgdir/opt/mewline"

  # 1. 创建目标目录
  install -d -m755 "$_dest"

  # 2. 从当前本地目录 (startdir) 精准拷贝所需代码，避开 makepkg 产生的垃圾文件
  cd "$startdir"
  cp -a assets docs src tests pyproject.toml uv.lock run.py README.md "$_dest/"

  # 3. 规范化创建虚拟环境
  export VIRTUAL_ENV="$_dest/.venv"
  python -m venv "$VIRTUAL_ENV"

  # 4. 使用 uv 在隔离环境中极速同步依赖
  cd "$_dest"
  uv sync --no-dev --frozen --compile-bytecode

  # 5. 创建全局启动脚本
  install -d -m755 "$pkgdir/usr/bin"
  cat << EOF > "$pkgdir/usr/bin/mewline"
#!/bin/sh
# 强制切换到工作目录，防止相对路径资源(如图片/CSS)找不到
cd /opt/mewline
exec .venv/bin/python run.py "\$@"
EOF
  chmod 755 "$pkgdir/usr/bin/mewline"

  # 6. 修复权限（Mewline 会在运行时动态改写 CSS，所以必须给写权限）
  chmod -R a+rwX "$_dest/src/mewline/styles"
}