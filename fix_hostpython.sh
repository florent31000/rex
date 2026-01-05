#!/bin/bash
HOSTPY="$HOME/.buildozer-rex/android/platform/build-arm64-v8a/build/other_builds/hostpython3/desktop/hostpython3/native-build/python3"
HOSTLIB="$HOME/.buildozer-rex/android/platform/build-arm64-v8a/build/other_builds/hostpython3/desktop/hostpython3/native-build/Lib"

if [ -f "$HOSTPY" ]; then
    echo "Testing if setuptools is importable..."
    if $HOSTPY -c 'import setuptools; print("setuptools OK:", setuptools.__version__)' 2>/dev/null; then
        echo "setuptools already available!"
    else
        echo "setuptools not found, installing..."
        
        # Install directly into the hostpython Lib directory
        $HOSTPY -m pip install --target="$HOSTLIB" setuptools
        
        # Verify
        $HOSTPY -c 'import setuptools; print("setuptools installed:", setuptools.__version__)'
    fi
else
    echo "hostpython not found at: $HOSTPY"
fi

