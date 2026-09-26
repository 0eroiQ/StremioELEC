# SPDX-License-Identifier: GPL-2.0-or-later
# StremioELEC built-in Nimbus baseline

PKG_NAME="skin.nimbus"
PKG_VERSION="0.1.43"
PKG_LICENSE="CC-BY-SA-4.0/GPL-2.0"
PKG_SITE="https://github.com/ivarbrandt/skin.nimbus"
PKG_URL="https://github.com/ivarbrandt/skin.nimbus/archive/refs/heads/main.tar.gz"
PKG_DEPENDS_TARGET="toolchain script.nimbus.helper"
PKG_LONGDESC="Nimbus baseline skin for the StremioELEC native UI migration."
# The Stremio Core remains a video plugin internally; Nimbus opens its real plugin root.
# Portable is exposed separately under Programs.
PKG_TOOLCHAIN="manual"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/kodi/addons/skin.nimbus
  cp -PR ./* ${INSTALL}/usr/share/kodi/addons/skin.nimbus/

  # Phase 1 bridge: keep upstream Nimbus intact and add a hidden, callable
  # Stremio Core anchor. Later Home rows will target concrete Core routes.
  HOME_XML="${INSTALL}/usr/share/kodi/addons/skin.nimbus/xml/Home.xml"
  if [ -f "${HOME_XML}" ]; then
    sed -i '/<controls>/a\
        <control type="button" id="9400">\
          <description>StremioELEC Core bridge</description>\
          <visible>false</visible>\
          <onclick>ActivateWindow(Videos,plugin://plugin.video.stremioelec/,return)</onclick>\
        </control>' "${HOME_XML}"
  fi
}
