[app]

# (str) Title of your application
title = Müşteri Takip

# (str) Package name
package.name = musteritakip

# (str) Package domain (needed for android/ios packaging)
package.domain = org.musteritakip

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas

# (str) Application versioning
version = 1.0

# (list) Application requirements
requirements = python3,kivy

# (str) Supported orientation
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Android architectures to build for
android.archs = arm64-v8a, armeabi-v7a

# (bool) Automatically accept Android SDK licenses
android.accept_sdk_license = True

# (int) Android minimum SDK version (Android 5.0+)
android.minapi = 21

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 1
