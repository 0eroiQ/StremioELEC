# SPDX-License-Identifier: GPL-2.0-only
# Nimbus Helper compatibility package for the StremioELEC native UI baseline

PKG_NAME="script.nimbus.helper"
PKG_VERSION="0.0.52"
PKG_LICENSE="GPL-2.0-only"
PKG_SITE="https://github.com/ivarbrandt/script.nimbus.helper"
PKG_URL="https://github.com/ivarbrandt/script.nimbus.helper/archive/refs/heads/main.tar.gz"
PKG_DEPENDS_TARGET="toolchain"
PKG_LONGDESC="Nimbus Helper compatibility layer for the StremioELEC Nimbus baseline."
PKG_TOOLCHAIN="manual"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/kodi/addons/script.nimbus.helper
  cp -PR ./* ${INSTALL}/usr/share/kodi/addons/script.nimbus.helper/
}
