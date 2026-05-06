# 离线发布目录说明

## 目录用途
- `build_windows_offline_package.py`：Windows 内网离线发布包构建脚本
- `build_windows_offline_package.bat`：Windows 离线构建快捷入口
- `build_linux_offline_package.py`：Linux x86_64 内网离线发布包构建脚本
- `build_linux_offline_package.sh`：Linux 离线构建快捷入口
- `windows_py310/`：Windows 离线发布包模板文件
- `linux_py310/`：Linux 离线发布包模板文件
- `dist/`：离线构建产物输出目录

## 构建命令

Windows：

```powershell
deploy\offline\build_windows_offline_package.bat
```

Linux：

```bash
./deploy/offline/build_linux_offline_package.sh
```

## 构建结果

构建完成后会在 `deploy/offline/dist/` 下生成：

- 目录版发布包
- Windows 的 `.zip` 压缩包
- Linux 的 `.tar.gz` 压缩包

## 相关文档

- `docs/deploy_offline.md`
- `docs/deploy_windows_offline.md`
- `docs/deploy_linux_offline.md`
- `docs/user_manual.md`
