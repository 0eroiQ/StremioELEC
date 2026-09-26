# SPDX-License-Identifier: GPL-2.0-or-later
# StremioELEC built-in Nimbus baseline

PKG_NAME="skin.nimbus"
PKG_VERSION="0.1.43"
PKG_LICENSE="CC-BY-SA-4.0/GPL-2.0"
PKG_SITE="https://github.com/ivarbrandt/skin.nimbus"
PKG_URL="https://github.com/ivarbrandt/skin.nimbus/archive/refs/heads/main.tar.gz"
PKG_DEPENDS_TARGET="toolchain"
PKG_LONGDESC="Nimbus baseline skin for the StremioELEC native UI migration."
PKG_TOOLCHAIN="manual"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/kodi/addons/skin.nimbus
  cp -PR ./* ${INSTALL}/usr/share/kodi/addons/skin.nimbus/
}
