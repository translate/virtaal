# Settings for `dmgbuild` (https://dmgbuild.readthedocs.io/), used by
# devsupport/packaging/macos/build_dmg.sh and the build-macos-app CI job to
# turn dist/Virtaal.app into a real, drag-to-Applications .dmg installer.
#
# The background's arrow runs between icon_locations; move them together.
# dmgbuild combines the @2x.png beside it into a HiDPI .tiff. window_rect
# is the background's 600x440 plus the title bar.
files = ["dist/Virtaal.app"]
symlinks = {"Applications": "/Applications"}
hide_extensions = ["Virtaal.app"]

volume_icon = "devsupport/mac-bundle/icons/VolumeIcon_virtaal.icns"
background = "devsupport/mac-bundle/virtaal_DMG_background.png"
window_rect = ((200, 120), (600, 462))

icon_size = 108
icon_locations = {
    "Virtaal.app": (130, 150),
    "Applications": (470, 150),
}
