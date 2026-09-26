# SPDX-License-Identifier: GPL-2.0-or-later
# StremioELEC pinned portable Core baseline

PKG_NAME="plugin.video.stremioelec"
PKG_VERSION="0.9.5"
PKG_LICENSE="GPL-2.0-or-later"
PKG_SITE="https://github.com/0eroiQ/StremioELEC"
PKG_URL="https://raw.githubusercontent.com/0eroiQ/StremioELEC/portable-repository-test/plugin.video.stremioelec/plugin.video.stremioelec-0.9.5.zip"
PKG_DEPENDS_TARGET="toolchain"
PKG_LONGDESC="Pinned StremioELEC Core baseline used by the native Nimbus UI migration."
PKG_TOOLCHAIN="manual"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/kodi/addons
  unzip -q ${PKG_BUILD}/plugin.video.stremioelec-0.9.5.zip -d ${INSTALL}/usr/share/kodi/addons
}
