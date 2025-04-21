#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---

# !!! IMPORTANT: Set the path to your Android NDK installation !!!
# Example: export NDK_ROOT="/Users/your_user/Library/Android/sdk/ndk/25.1.8937393"
# Example: export NDK_ROOT="/home/user/Android/Sdk/ndk/25.1.8937393"
# Example: export NDK_ROOT="C:/Users/user/AppData/Local/Android/Sdk/ndk/25.1.8937393" # (Use Git Bash/WSL on Windows)
# NDK_ROOT=

# Check if NDK_ROOT is set and valid
if [ -z "$NDK_ROOT" ]; then
    echo "Error: NDK_ROOT environment variable is not set."
    echo "Please set it to the path of your Android NDK installation."
    exit 1
fi
if [ ! -d "$NDK_ROOT" ]; then
    echo "Error: NDK_ROOT directory not found: $NDK_ROOT"
    exit 1
fi

# Android Build Settings
MIN_API_LEVEL=21 # Minimum Android API level (e.g., 21 for Android 5.0)
# Define the Android ABIs (Architectures) you want to build for
ABIS_TO_BUILD=("arm64-v8a" "armeabi-v7a" "x86_64" "x86") # Common choices for Unity

# Source and Output Directories
ESPEAK_NG_SOURCE_DIR="espeak-ng" # Relative path to the espeak-ng source code directory
OUTPUT_DIR="android_libs" # Directory to store the final .so files, organized by ABI

# Check if espeak-ng source directory exists
if [ ! -d "$ESPEAK_NG_SOURCE_DIR" ]; then
    echo "Error: espeak-ng source directory not found: $ESPEAK_NG_SOURCE_DIR"
    echo "Make sure you run this script from the parent directory of '$ESPEAK_NG_SOURCE_DIR'."
    exit 1
fi

# NDK CMake Toolchain File
CMAKE_TOOLCHAIN_FILE="$NDK_ROOT/build/cmake/android.toolchain.cmake"
if [ ! -f "$CMAKE_TOOLCHAIN_FILE" ]; then
    echo "Error: Android NDK CMake toolchain file not found at: $CMAKE_TOOLCHAIN_FILE"
    exit 1
fi

# Get the number of processor cores for parallel builds
BUILD_CORES=$(nproc || sysctl -n hw.ncpu || echo 2) # Linux || macOS || Fallback

# --- Build Process ---

echo "Starting Android build for espeak-ng..."
echo "NDK Root: $NDK_ROOT"
echo "Target ABIs: ${ABIS_TO_BUILD[@]}"
echo "Min API Level: $MIN_API_LEVEL"
echo "Output Directory: $OUTPUT_DIR"
echo "Using $BUILD_CORES cores for building."
echo "-------------------------------------------------"

ORIGINAL_DIR=$(pwd)
cd "$ESPEAK_NG_SOURCE_DIR"

# Loop through each ABI and build
for ABI in "${ABIS_TO_BUILD[@]}"; do
    echo ""
    echo "#####################################################"
    echo "# Building for ABI: $ABI"
    echo "#####################################################"

    BUILD_DIR="build-android-$ABI"
    INSTALL_DIR="_install-android-$ABI" # Temporary install prefix for this ABI
    FINAL_ABI_OUTPUT_DIR="$ORIGINAL_DIR/$OUTPUT_DIR/$ABI" # Final destination

    # Clean potential previous build artifacts for this specific ABI
    echo "Cleaning previous build directories..."
    rm -rf "$BUILD_DIR"
    rm -rf "$INSTALL_DIR"

    # Configure espeak-ng using CMake with NDK toolchain
    echo "Configuring CMake for $ABI..."
    cmake -B "$BUILD_DIR" \
        -G "Ninja" \
        -DCMAKE_TOOLCHAIN_FILE="$CMAKE_TOOLCHAIN_FILE" \
        -DANDROID_ABI="$ABI" \
        -DANDROID_NATIVE_API_LEVEL="$MIN_API_LEVEL" \
        -DCMAKE_INSTALL_PREFIX="$INSTALL_DIR" \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=ON \
        -DENABLE_TESTS=OFF \
        -DENABLE_KLATT=OFF `# Optionally disable Klatt if only standard voices needed` \
        -DCOMPILE_INTONATIONS=OFF `# Optionally disable intonation compilation` \
        -DCMAKE_VERBOSE_MAKEFILE=OFF `# Set to ON for detailed build logs` \
        . # Use current directory (espeak-ng source)

    # Build the library
    echo "Building shared library for $ABI..."
    cmake --build "$BUILD_DIR" --config Release --parallel $BUILD_CORES

    # Install the library to the temporary install directory
    echo "Installing library for $ABI..."
    cmake --install "$BUILD_DIR"

    # Create the final output directory for this ABI
    mkdir -p "$FINAL_ABI_OUTPUT_DIR"

    # Find and copy the shared library (.so)
    LIB_PATH="$INSTALL_DIR/lib/libespeak-ng.so"
    if [ -f "$LIB_PATH" ]; then
        echo "Copying $LIB_PATH to $FINAL_ABI_OUTPUT_DIR/"
        cp "$LIB_PATH" "$FINAL_ABI_OUTPUT_DIR/"
    else
        echo "Error: Could not find compiled library at $LIB_PATH"
        # Attempt to find it elsewhere in install dir (less standard)
        find "$INSTALL_DIR" -name libespeak-ng.so -exec cp {} "$FINAL_ABI_OUTPUT_DIR/" \;
        if [ ! -f "$FINAL_ABI_OUTPUT_DIR/libespeak-ng.so" ]; then
             echo "Error: Failed to find and copy libespeak-ng.so for $ABI."
             exit 1
        fi
         echo "Warning: Library found at non-standard location within $INSTALL_DIR and copied."
    fi

    echo "Successfully built and copied library for $ABI."
    echo "-------------------------------------------------"

done

cd "$ORIGINAL_DIR" # Go back to the starting directory

echo ""
echo "#####################################################"
echo "# Android build process completed."
echo "# Shared libraries (.so) should be in the '$OUTPUT_DIR' directory,"
echo "# organized by ABI:"
ls -R "$OUTPUT_DIR"
echo "#####################################################"
echo ""
echo "Next steps:"
echo "1. Copy the '$OUTPUT_DIR' directory contents into your Unity project:"
echo "   UnityProject/Assets/Plugins/Android/libs/<ABI>/libespeak-ng.so"
echo "   (e.g., Assets/Plugins/Android/libs/arm64-v8a/libespeak-ng.so)"
echo "2. Remember to bundle the 'espeak-ng-data' directory in Unity's StreamingAssets."
echo "3. Implement P/Invoke C# bindings to call functions from libespeak-ng.so."

exit 0