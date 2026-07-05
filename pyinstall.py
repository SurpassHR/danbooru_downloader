import os
import PyInstaller.__main__

cmd = [
    "./main.py",
    # "--icon=./assets/icon.ico", # FILE.ico: apply the icon to a Windows executable.
    # Clean PyInstaller cache and remove temporary files before building.
    "--clean",
    # Create a one-file bundled executable.
    "--onedir",
    # Replace output directory (default: SPECPATH/dist/SPECNAME) without asking for confirmation.
    "--noconfirm",
    "--noupx",
    # 0: no optimization, 1: basic optimization, 2: full optimization
    "--optimize=2",
    # 指定程序运行时是否展示后台，推荐当系统默认 termnial 为 bash 或 pwsh 时注释此选项，若为 cmd 时会打印乱码，则开启此选项，日志直接在 log 文件夹中查看
    # "--windowed",
    # "--distpath=./dist/main"
]

target_position = os.path.join("dist", "main")
fileMoveList = {
    os.path.join("config", "config.json"): os.path.join(target_position, "config", "config.json"),
    os.path.join("assets"): os.path.join(target_position, "assets"),
}

if os.path.exists("./config/requirements.txt"):
    with open("./config/requirements.txt", "r", encoding="utf-8") as reader:
        for line in reader:
            if "#" not in line:
                cmd.append("--hidden-import=" + line.strip())

    PyInstaller.__main__.run(cmd)

for src, dst in fileMoveList.items():
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        # copy file from src to dst
        if os.path.isdir(src):
            os.system(f"cp -r {src} {dst}")
        else:
            os.system(f"cp {src} {dst}")
    else:
        print(f"Source file {src} does not exist.")
