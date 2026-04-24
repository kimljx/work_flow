# 离线发布目录说明

## 目录用途

- `build_windows_offline_package.py`：Windows 内网离线发布包构建脚本
- `build_windows_offline_package.bat`：脚本快捷入口
- `windows_py310/`：离线发布包模板文件
- `dist/`：构建输出目录

## 构建命令

```powershell
deploy\offline\build_windows_offline_package.bat
```

## 构建结果

构建完成后会在 `deploy/offline/dist/` 下生成：

- 目录版发布包
- zip 压缩包

## 相关文档

- `docs/deploy_offline.md`
- `docs/deploy_windows_offline.md`
- `docs/user_manual.md`
