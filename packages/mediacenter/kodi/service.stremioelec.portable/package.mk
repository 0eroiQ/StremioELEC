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

  # Native UI migration: expose Portable under Kodi Programs while preserving
  # its startup service extension. This keeps the known-good runtime intact
  # and adds a user-facing executable entry for StremioELEC.
  ADDON_XML="${INSTALL}/usr/share/kodi/addons/service.stremioelec.portable/addon.xml"
  if [ -f "${ADDON_XML}" ] && ! grep -q 'xbmc.python.pluginsource' "${ADDON_XML}"; then
    sed -i '/<extension point="xbmc.addon.metadata">/i\
    <extension point="xbmc.python.pluginsource" library="default.py">\
        <provides>executable</provides>\
    </extension>' "${ADDON_XML}"
  fi
}
