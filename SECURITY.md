# 安全说明

## 边界

* 只启停面板自己记录在 `state/pids.json` 的进程，不全局 taskkill
* 不改系统代理 / 防火墙 / DNS / VPN
* 开机自启只写 HKCU Run 一个值，设置里可关
* 所有外部请求 2 秒超时，失败只变灯 + 写日志

## 凭据

* `config.json` 的 qB 密码、`rpc-secret.txt` 的 aria2 密钥是明文，仅适合本机单用户
* `.gitignore` 已排除 config.json / state / logs / cache / backups
* RPC 与 WebUI 默认只听 127.0.0.1，不要暴露公网
