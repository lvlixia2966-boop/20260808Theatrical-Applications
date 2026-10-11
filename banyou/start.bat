@echo off
rem 凉山伴游 · 一键启动（Windows 开发/局域网演示用）
rem 用法：双击启动服务；start.bat backup 一次性配置远端备份；start.bat push 推送备份
if "%~1"=="backup" goto backup-config
if "%~1"=="push" goto backup-push
cd /d "%~dp0backend"

rem 预检：8300 已有服务在监听时友好退出（避免端口冲突报错栈）
netstat -ano | findstr /C:":8300" | findstr /C:"LISTENING" >nul
if not errorlevel 1 (
    echo [提示] 端口 8300 已有服务在监听，伴游服务可能已在运行。
    echo        可直接访问 http://127.0.0.1:8300/ ；如需重启请先停止现有进程。
    pause
    exit /b 0
)

echo [自检] 可选集成状态（未配置不影响基础功能，自动降级）:
python -c "import pathlib;env=pathlib.Path('.env');d=env.read_text(encoding='utf-8') if env.exists() else '';f=lambda k:('已配置' if (k+'=') in d and len(d.split(k+'=',1)[1].splitlines()[0].strip())>0 else '未配置');print('  耳机语音链(ASR/TTS):',f('DOUBAO_SPEECH_APP_ID'));print('  AI应答(LLM):',f('ARK_API_KEY'))"
echo   HTTPS: 生产部署项（本脚本仅本机/局域网 HTTP）

echo [1/3] 检查依赖...
python -c "import fastapi, uvicorn, sqlalchemy" 2>nul
if errorlevel 1 (
    echo       缺少依赖，正在安装 requirements.txt ...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请手动执行: python -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

if not exist banyou.db (
    echo [2/3] 首次运行：初始化数据库并灌入凉山演示内容...
    python seed_liangshan.py
    if errorlevel 1 (
        echo [错误] 初始化失败，请检查上方日志
        pause
        exit /b 1
    )
) else (
    echo [2/3] 数据库已存在，跳过初始化
)

echo [3/3] 启动服务（Ctrl+C 停止）...
echo        游客端  http://127.0.0.1:8300/   （局域网用本机 IP 访问）
echo        管理后台 http://127.0.0.1:8300/admin/
python run.py
pause

:backup-config
cd /d "%~dp0"
git remote get-url origin >nul 2>&1
if not errorlevel 1 (
    echo 当前已配置远端:
    git remote get-url origin
    echo 如需更换，请先执行: git remote remove origin
    pause
    exit /b 0
)
echo 远端备份一次性配置（URL 格式二选一）:
echo   https://host/group/repo.git
echo   git@host:group/repo.git
set /p URL=请粘贴远端 URL 后回车: 
python -c "import re,sys;u=sys.argv[1];ok=bool(re.match(r'^https://[\w.-]+/.+[.]git$',u)) or bool(re.match(r'^git@[\w.-]+:.+[.]git$',u));sys.exit(0 if ok else 1)" "%URL%"
if errorlevel 1 (
    echo [错误] URL 格式不符合要求（需以 https:// 开头或 git@ 开头，且以 .git 结尾），未写入。
    pause
    exit /b 1
)
git remote add origin "%URL%"
echo 已写入远端 origin = %URL%
echo 首次备份请执行: start.bat push
pause
exit /b 0

:backup-push
cd /d "%~dp0"
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo [提示] 尚未配置远端，请先执行: start.bat backup
    pause
    exit /b 1
)
echo 推送备份到远端（首次会建立 master 上游）...
git push -u origin master
pause
exit /b 0
