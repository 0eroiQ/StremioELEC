# SPDX-License-Identifier: GPL-2.0-or-later
# StremioELEC pinned portable service baseline

PKG_NAME="service.stremioelec.portable"
PKG_VERSION="0.3.5"
PKG_LICENSE="GPL-2.0-or-later"
PKG_SITE="https://github.com/0eroiQ/StremioELEC"
PKG_URL="https://raw.githubusercontent.com/0eroiQ/StremioELEC/portable-repository-test/service.stremioelec.portable/service.stremioelec.portable-0.3.5.zip"
PKG_DEPENDS_TARGET="toolchain"
PKG_LONGDESC="Pinned StremioELEC portable runtime used by the native Nimbus UI migration."
PKG_TOOLCHAIN="manual"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/kodi/addons
  unzip -q ${PKG_BUILD}/service.stremioelec.portable-0.3.5.zip -d ${INSTALL}/usr/share/kodi/addons
}
