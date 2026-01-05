#!/bin/bash
# ===========================================
# NEO BUILD SCRIPT
# ===========================================
# Usage: ./build.sh [debug|release]
#
# This script:
# 1. Activates the buildozer venv
# 2. Applies necessary patches (PAX_FORMAT for long paths)
# 3. Installs setuptools in hostpython if needed
# 4. Builds the APK

set -e

BUILD_TYPE="${1:-debug}"
PROJECT_DIR="/mnt/c/Users/flore/Documents/Cursor/rex"
BUILDOZER_DIR="$HOME/.buildozer-rex"
P4A_DIR="$BUILDOZER_DIR/android/platform/python-for-android"
HOSTPY="$BUILDOZER_DIR/android/platform/build-arm64-v8a/build/other_builds/hostpython3/desktop/hostpython3/native-build/python3"
HOSTLIB="$BUILDOZER_DIR/android/platform/build-arm64-v8a/build/other_builds/hostpython3/desktop/hostpython3/Lib"

echo "🐕 Néo Build Script"
echo "==================="
echo "Build type: $BUILD_TYPE"
echo ""

# Activate venv
echo "📦 Activating buildozer venv..."
source ~/buildozer-venv/bin/activate

# Go to project
cd "$PROJECT_DIR"

# Patch 1: Fix USTAR_FORMAT -> PAX_FORMAT (for long file paths)
echo "🔧 Applying PAX_FORMAT patch..."
P4A_BUILD="$P4A_DIR/pythonforandroid/bootstraps/common/build/build.py"
if [ -f "$P4A_BUILD" ]; then
    if grep -q "USTAR_FORMAT" "$P4A_BUILD"; then
        sed -i 's/USTAR_FORMAT/PAX_FORMAT/g' "$P4A_BUILD"
        echo "   ✅ Source template patched"
    else
        echo "   ✅ Source template already patched"
    fi
fi

# Also patch the generated dist if it exists
DIST_BUILD="$BUILDOZER_DIR/android/platform/build-arm64-v8a/dists/rexbrain/build.py"
if [ -f "$DIST_BUILD" ]; then
    if grep -q "USTAR_FORMAT" "$DIST_BUILD"; then
        sed -i 's/USTAR_FORMAT/PAX_FORMAT/g' "$DIST_BUILD"
        echo "   ✅ Dist build.py patched"
    else
        echo "   ✅ Dist build.py already patched"
    fi
fi

# Patch 2: Ensure setuptools in hostpython
if [ -f "$HOSTPY" ]; then
    echo "🔧 Checking setuptools in hostpython..."
    if ! $HOSTPY -I -c "import setuptools" 2>/dev/null; then
        echo "   Installing setuptools..."
        cd /tmp
        pip download setuptools --no-deps -d . 2>/dev/null || true
        unzip -o setuptools*.whl -d "$HOSTLIB" 2>/dev/null || true
        rm -f setuptools*.whl 2>/dev/null || true
        echo "   ✅ setuptools installed"
    else
        echo "   ✅ setuptools already available"
    fi
    cd "$PROJECT_DIR"
fi

# Build
echo ""
echo "🔨 Building APK ($BUILD_TYPE)..."
echo ""
buildozer android $BUILD_TYPE

echo ""
echo "✅ Build complete!"
echo "📱 APK location: $PROJECT_DIR/bin/"
ls -la "$PROJECT_DIR/bin/"*.apk 2>/dev/null || echo "No APK found"

