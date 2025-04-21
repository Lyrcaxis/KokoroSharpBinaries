# KokoroSharpBinaries
This repo builds and hosts stuff **KokoroSharp**'s `.nupkg` needs to become Plug &amp; Play.

You can find **KokoroSharp**'s code on [its official github repo](https://github.com/Lyrcaxis/KokoroSharp) and download it via [NuGet](https://www.nuget.org/packages/KokoroSharp/).

## Shoutout to:
- https://huggingface.co/hexgrad/Kokoro-82M for the fantastic Kokoro-82M model and its voices
- https://github.com/thewh1teagle/espeak-ng-static for 100% working binary-building workflow
- https://github.com/taylorchu/kokoro-onnx for the plug-and-play onnx-converted kokoro models

# Building espeak-ng for Android (`.so` libraries)

This repository includes a script (`build_android.sh`) to automate the compilation of the [espeak-ng text-to-speech engine](https://github.com/espeak-ng/espeak-ng) into shared libraries (`.so`) for various Android architectures (ABIs). This is useful for embedding `espeak-ng`'s phonetization or synthesis capabilities directly into an Android application (e.g., built with Unity, React Native, or native Android).

The script uses CMake and the Android NDK (Native Development Kit) for cross-compilation.

## Prerequisites

Before running the build script, ensure you have the following installed on your system:

1.  **Git:** To clone repositories.
2.  **Android NDK:**
    *   The easiest way is via Android Studio: `Tools -> SDK Manager -> SDK Tools -> NDK (Side by side)`. Note the installation path.
    *   Alternatively, download directly from the [Android NDK website](https://developer.android.com/ndk/downloads).
3.  **CMake:** A cross-platform build system generator.
    *   Download from [cmake.org](https://cmake.org/download/) or install via package manager.
4.  **Ninja:** A small build system focused on speed (used by the script).
    *   **Linux (Debian/Ubuntu):** `sudo apt update && sudo apt install ninja-build`
    *   **macOS (Homebrew):** `brew install ninja`
    *   **Windows:** Download `ninja-win.zip` from the [Ninja GitHub Releases](https://github.com/ninja-build/ninja/releases), extract `ninja.exe`, and ensure it's in your system's PATH. (Easier if using WSL - see below).
5.  **Basic Build Tools (Host):** A C/C++ compiler for your host system (like GCC/Clang, Make) might be needed by CMake or espeak-ng's build process for host tools.
    *   **Linux (Debian/Ubuntu):** `sudo apt install build-essential`
    *   **macOS:** Install Xcode Command Line Tools: `xcode-select --install`
    *   **Windows:** Often covered by installing Visual Studio Build Tools or using WSL/Git Bash.

## Setup

1.  **Clone this Repository:**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-name>
    ```
2.  **Clone espeak-ng:** The build script expects the `espeak-ng` source code to be in a directory named `espeak-ng` *inside* the directory where you run the script.
    ```bash
    git clone https://github.com/espeak-ng/espeak-ng.git
    ```
    Your directory structure should look like this:
    ```
    <your-repo-name>/
    ├── build_android.sh  <-- The build script
    ├── espeak-ng/        <-- The cloned espeak-ng source code
    └── README.md         <-- This file (potentially)
    └── ... (other files from your repo)
    ```

## Configuration (Important!)

Before running the script, you **must** configure the path to your Android NDK installation:

1.  **Edit the `build_android.sh` script:** Open the file in a text editor.
2.  **Locate the `NDK_ROOT` variable:** Find the lines near the top:
    ```bash
    # !!! IMPORTANT: Set the path to your Android NDK installation !!!
    # Example: export NDK_ROOT="/Users/your_user/Library/Android/sdk/ndk/25.1.8937393"
    # Example: export NDK_ROOT="/home/user/Android/Sdk/ndk/25.1.8937393"
    # Example: export NDK_ROOT="C:/Users/user/AppData/Local/Android/Sdk/ndk/25.1.8937393" # (Use Git Bash/WSL on Windows)
    # NDK_ROOT=
    ```
3.  **Set the Path:** Uncomment the `NDK_ROOT=` line and set the correct path to your NDK installation directory. **Use the correct path format for your operating system and shell environment!**
    *   **Linux/macOS:** `/path/to/your/ndk/version`
    *   **Windows (using Git Bash):** `/c/path/to/your/ndk/version` (Note the leading `/c/` for C drive)
    *   **Windows (using WSL):** `/mnt/c/path/to/your/ndk/version` (Note the leading `/mnt/c/` for C drive)

4.  **(Optional) Adjust Other Settings:** You can also modify:
    *   `MIN_API_LEVEL`: Target minimum Android SDK level (default is usually fine).
    *   `ABIS_TO_BUILD`: An array of Android architectures to build for (e.g., `"arm64-v8a"`, `"armeabi-v7a"`).

## Execution

1.  **Open a Terminal or Shell:**
    *   **Linux/macOS:** Use your standard terminal.
    *   **Windows:** **Use WSL (Windows Subsystem for Linux - Recommended) or Git Bash.** Do *not* use standard Command Prompt or PowerShell directly, as they don't run bash scripts properly.
        *   **WSL:** Open your Linux distribution (e.g., Ubuntu). Install prerequisites within WSL (`sudo apt install ...`).
        *   **Git Bash:** Launch Git Bash. Ensure CMake and Ninja (downloaded `ninja.exe`) are in your Windows PATH.
2.  **Navigate:** `cd` into the directory containing the `build_android.sh` script and the `espeak-ng` source folder.
3.  **Make Executable (Linux/macOS/WSL/Git Bash):**
    ```bash
    chmod +x build_android.sh
    ```
4.  **Run the Script:**
    ```bash
    ./build_android.sh
    ```
5.  **Windows Specific - Permissions:**
    *   The build process might try to create symbolic links. If you encounter a `"privilege not held"` error near the end:
        *   **Option A (Recommended):** Enable **Developer Mode** in Windows Settings (`Settings -> Privacy & security -> For developers -> Developer Mode`). Restart your shell (WSL/Git Bash) and rerun the script.
        *   **Option B:** Run your WSL or Git Bash terminal **as Administrator** before executing the script.

The script will configure, build, and install `espeak-ng` for each ABI specified in `ABIS_TO_BUILD`. This may take some time.

## Output

Upon successful completion, the script will create an output directory (default: `android_libs`) in the same location where you ran the script. Inside, you will find the compiled shared libraries organized by ABI:
```text
<your-repo-name>/
├── android_libs/
│   ├── arm64-v8a/
│   │   └── libespeak-ng.so
│   ├── armeabi-v7a/
│   │   └── libespeak-ng.so
│   ├── x86/
│   │   └── libespeak-ng.so
│   └── x86_64/
│       └── libespeak-ng.so
├── build_android.sh
├── espeak-ng/
└── ... (other files from your repo)
```

## Using the Libraries (Example: Unity)

1.  Copy the contents of the relevant ABI directories from `android_libs/` into your Unity project's `Assets/Plugins/Android/libs/` folder. For example: 
    *   Copy `android_libs/arm64-v8a/libespeak-ng.so` to `YourUnityProject/Assets/Plugins/Android/libs/arm64-v8a/libespeak-ng.so`
    *   Copy `android_libs/armeabi-v7a/libespeak-ng.so` to `YourUnityProject/Assets/Plugins/Android/libs/armeabi-v7a/libespeak-ng.so`
    *   *(Repeat for other ABIs like x86, x86_64 if needed)*
2.  **Bundle espeak-ng Data:** Copy the `espeak-ng-data` directory (found inside the `espeak-ng` source directory after a successful build, or potentially from the temporary `_install-android-*` folders) into your Unity project's `Assets/StreamingAssets/` folder. You will need code in your app to copy this data from `StreamingAssets` to a writable location (`Application.persistentDataPath`) on the device at runtime and tell the espeak-ng library where to find it via an initialization function.
3.  **P/Invoke:** Use C#'s `[DllImport("__Internal")]` mechanism to declare and call the native C functions exposed by `libespeak-ng.so` (e.g., functions for initialization and phonetization). Refer to the C# bindings example provided earlier or `espeak-ng`'s public API documentation (`espeak-ng/docs/api.md` or `espeak-ng/src/include/espeak-ng/espeak_ng.h`).

## Troubleshooting

*   **`NDK_ROOT environment variable is not set` or `NDK_ROOT directory not found`:** Double-check the `NDK_ROOT` path in `build_android.sh`. Ensure it's uncommented, points to the correct NDK location, and uses the proper path format for your shell (WSL/Git Bash paths on Windows!).
*   **`CMake Error: ... MSBuild command:`:** You are likely running in an environment where CMake defaults to the Visual Studio generator. Ensure you are using WSL or Git Bash, and that the `-G "Ninja"` flag is present in the `cmake` command within the script. Make sure Ninja is installed and accessible.
*   **`ninja: command not found` or similar:** Ninja is not installed or not in the system PATH. Install it using your package manager (Linux/macOS/WSL) or download `ninja.exe` and add it to your PATH (Windows/Git Bash).
*   **`CMake Error: failed to create symbolic link ... privilege not held` (Windows):** Enable Developer Mode in Windows Settings or run the script terminal as Administrator.
*   **Build Errors:** Check the script output for specific compilation errors. Ensure all prerequisites are installed. Try cleaning the build directories (`build-android-*` and `_install-android-*` inside the `espeak-ng` folder) and running the script again.