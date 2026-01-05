# ============================================
# BUILDOZER SPEC FILE FOR REX-BRAIN
# ============================================
# To build: buildozer android debug
# To deploy: buildozer android deploy run

[app]

# Title of your application
title = Rex Brain

# Package name (must be unique)
package.name = rexbrain

# Package domain (for android/ios)
package.domain = com.rexrobot

# Source code directory
source.dir = .

# Source files to include
source.include_exts = py,png,jpg,kv,atlas,yaml,txt

# Source files to exclude
source.exclude_exts = spec

# Source directories to exclude
source.exclude_dirs = tests, bin, venv, .git, __pycache__

# Application versioning
version = 0.1.0

# Application requirements
# Note: Using httpx + websockets for API calls (minimal deps)
requirements = python3,
    kivy==2.3.0,
    plyer,
    pyjnius,
    openssl,
    pyopenssl,
    numpy,
    pillow,
    pyyaml,
    certifi,
    idna,
    typing_extensions,
    sniffio,
    anyio,
    h11,
    httpcore,
    httpx,
    annotated_types,
    pydantic_core,
    pydantic,
    sqlalchemy,
    aiosqlite,
    websocket-client

# Custom source folders for requirements
# requirements.source.kivy = ../../kivy

# Presplash screen (displayed during loading)
# presplash.filename = %(source.dir)s/data/presplash.png

# Icon of the application
# icon.filename = %(source.dir)s/data/icon.png

# Supported orientations: landscape, portrait, all
orientation = landscape

# OSX Specific

# Application version on macOS
osx.python_version = 3
osx.kivy_version = 2.3.0

# Android Specific

# Android NDK version to use
android.ndk = 25b

# Android SDK version to use
android.sdk = 33

# Android API to use
android.api = 33

# Minimum API required
android.minapi = 26

# Android NDK API to use (usually same as minapi)
android.ndk_api = 26

# Android architecture to build for
# Options: armeabi-v7a, arm64-v8a, x86, x86_64
android.archs = arm64-v8a

# Skip these architectures
# android.skip_update = False

# Permissions
android.permissions = 
    INTERNET,
    ACCESS_NETWORK_STATE,
    ACCESS_WIFI_STATE,
    CHANGE_WIFI_STATE,
    CAMERA,
    RECORD_AUDIO,
    MODIFY_AUDIO_SETTINGS,
    WAKE_LOCK,
    FOREGROUND_SERVICE,
    VIBRATE,
    READ_EXTERNAL_STORAGE,
    WRITE_EXTERNAL_STORAGE

# Android features that need to be declared
# Note: android.features is deprecated, features are auto-detected from permissions
# android.features = android.hardware.camera, android.hardware.camera.autofocus

# Java classes to add to Android manifest
# android.add_jars = foo.jar,bar.jar

# Java files to add to the android project
# android.add_src = 

# AAR files to add
# android.add_aars =

# Gradle dependencies
# Note: WebRTC will be handled via Python aiortc or manual AAR
android.gradle_dependencies = androidx.core:core:1.6.0

# Android app theme
android.apptheme = @android:style/Theme.NoTitleBar

# Accept SDK license
android.accept_sdk_license = True

# Entry point of your app
# android.entrypoint = org.kivy.android.PythonActivity

# Full screen mode
fullscreen = 1

# Logcat filters to display
# android.logcat_filters = *:S python:D

# Copy library instead of building
# android.copy_libs = 1

# Android Whitelist (restrict storage access)
# android.whitelist = 

# Android Blacklist
# android.blacklist = 

# Android enable AndroidX support
android.enable_androidx = True

# iOS Specific
# (not used for this project)

# Services
# Services are defined as: name:entrypoint
# Disabled for now until service.py is created
# services = RexService:src/service.py:foreground

# Main Python file
# p4a.source_dir = 

# (str) The directory where python-for-android should look for your recipes
# p4a.local_recipes = 

# Bootstrap to use
# p4a.bootstrap = sdl2

# Port for debug server
# p4a.port = 

[buildozer]

# Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# Display warning if buildozer is run as root
warn_on_root = 1

# Path to build artifact storage (short path to avoid "name too long" error)
build_dir = /home/flore/.buildozer-rex

# Path to build output (keep in project for easy access)
bin_dir = ./bin

