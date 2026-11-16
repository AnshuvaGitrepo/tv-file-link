"""Build a sideloadable Fire OS test APK using the installed Android SDK and JDK."""
import os
import shutil
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
ROOT = PROJECT.parent
WORK = ROOT / "work" / "fire-os-build"
APP = PROJECT / "app" / "src" / "main"
APK = PROJECT / "TV-File-Link-Fire-OS.apk"
ABIS = {
    "armeabi-v7a": "armv7a-linux-androideabi",
    "arm64-v8a": "aarch64-linux-android",
    "x86_64": "x86_64-linux-android",
    "x86": "i686-linux-android",  # Android TV emulator images are 32-bit x86
}
VERSION_CODE, VERSION_NAME = "6", "1.4.1"


def run(*command):
    subprocess.run([str(arg) for arg in command], check=True)


def make_library(ndk, abi, target):
    library = WORK / abi / "libtvfilelink.so"
    library.parent.mkdir(exist_ok=True)
    run(ndk / "clang++.exe", f"--target={target}24", "-std=c++17", "-O2",
        "-fPIC", "-shared", "-static-libstdc++", "-Wl,--no-undefined",
        f"-ffile-prefix-map={ROOT}=.", f"-ffile-prefix-map={ROOT.as_posix()}=.",  # no build-PC paths in the binary
        "-I", ROOT / "shared", APP / "jni" / "Bridge.cpp", ROOT / "shared" / "Transfer.cpp",
        "-o", library)
    run(ndk / "llvm-strip.exe", "--strip-unneeded", library)
    return abi, library


def main():
    sdk = Path(os.environ["ANDROID_HOME"])
    tools = sdk / "build-tools" / "36.0.0"
    ndk = sdk / "ndk" / "28.2.13676358" / "toolchains" / "llvm" / "prebuilt" / "windows-x86_64" / "bin"
    android = sdk / "platforms" / "android-36" / "android.jar"
    if sys.platform != "win32":
        raise SystemExit("This build script uses the Windows Android SDK and NDK.")
    if not all(path.is_file() for path in (android, tools / "aapt2.exe", ndk / "clang++.exe")):
        raise SystemExit("Install Android Platform 36, Build Tools 36.0.0 and NDK 28.2.13676358.")
    jdk = Path(os.environ["JAVA_HOME"]) / "bin" if "JAVA_HOME" in os.environ else None
    java, javac, keytool = [jdk / (name + ".exe") if jdk else name for name in ("java", "javac", "keytool")]
    WORK.mkdir(parents=True, exist_ok=True)
    classes = WORK / "classes"
    dex = WORK / "dex"
    generated = WORK / "resources-java"
    for folder in (classes, dex, generated):
        folder.mkdir(exist_ok=True)
    run("node.exe", ROOT / "shared" / "make-portal.cjs")
    manifest = WORK / "AndroidManifest.xml"
    manifest.write_text((APP / "AndroidManifest.xml").read_text(encoding="utf-8").replace(
        "<manifest ", '<manifest package="com.anshuva.tvfilelink" ', 1), encoding="utf-8")
    resources = WORK / "resources.zip"
    template = WORK / "resources.apk"
    run(tools / "aapt2.exe", "compile", "--dir", APP / "res", "-o", resources)
    run(tools / "aapt2.exe", "link", "--manifest", manifest, "-I", android,
        "--min-sdk-version", "24", "--target-sdk-version", "34", "--version-code", VERSION_CODE,
        "--version-name", VERSION_NAME, "--java", generated, "-o", template, resources)
    with ThreadPoolExecutor(max_workers=4) as pool:
        builds = [pool.submit(make_library, ndk, abi, target) for abi, target in ABIS.items()]
        run(javac, "--release", "8", "-encoding", "UTF-8", "-classpath", android,
            "-d", classes, *APP.glob("java/**/*.java"), *generated.rglob("*.java"))
        run(java, "-cp", tools / "lib" / "d8.jar", "com.android.tools.r8.D8",
            "--lib", android, "--min-api", "24", "--output", dex, *classes.rglob("*.class"))
        binaries = [build.result() for build in builds]
    unsigned = WORK / "unsigned.apk"
    shutil.copyfile(template, unsigned)
    with zipfile.ZipFile(unsigned, "a") as archive:
        archive.write(dex / "classes.dex", "classes.dex", zipfile.ZIP_DEFLATED)
        for abi, library in binaries:
            archive.write(library, f"lib/{abi}/libtvfilelink.so")
    aligned = WORK / "aligned.apk"
    run(tools / "zipalign.exe", "-P", "16", "-f", "4", unsigned, aligned)
    key = WORK / "sideload.keystore"
    if not key.exists():
        run(keytool, "-genkeypair", "-keystore", key, "-storepass", "android",
            "-keypass", "android", "-alias", "tvfilelink", "-keyalg", "RSA", "-keysize", "2048",
            "-validity", "10000", "-dname", "CN=TV File Link Sideload")
    apksigner = tools / "lib" / "apksigner.jar"
    run(java, "-jar", apksigner, "sign", "--ks", key, "--ks-pass", "pass:android",
        "--key-pass", "pass:android", "--v4-signing-enabled", "false", "--out", APK, aligned)
    run(java, "-jar", apksigner, "verify", "--verbose", APK)
    run(tools / "zipalign.exe", "-c", "-P", "16", "4", APK)


if __name__ == "__main__":
    main()
