# 安全说明

## 边界

* 只启停面板自己记录在 `state/pids.json` 的进程，不全局 taskkill
* 不改系统代理 / 防火墙 / DNS / VPN
* 开机自启只写 HKCU Run 一个值，设置里可关
* 所有外部请求 2 秒超时，失败只变灯 + 写日志

## 凭据

* `config.json` 的 qB 密码 / AI Key、`rpc-secret.txt` 的 aria2 密钥是明文，仅适合本机单用户
* `.gitignore` 已排除 config.json / state / logs / cache / backups / 本地书库内容
* RPC 与 WebUI 默认只听 127.0.0.1，不要暴露公网
* 提交前跑 `python scripts/scan_secrets.py .`

## 无鉴权前提（最重要）

面板没有账号体系，**本地即最高权限**：任何能访问 `18550` 的人都能投递下载、删除片库、触发关机。
默认绑定 `127.0.0.1` 是硬前提，不要用端口映射把它放到公网；如需多设备访问，先按 [SETUP.md §5.3](SETUP.md) 用虚拟局域网 + 反向代理鉴权。

## 书城 / 图片代理

* 远程图片统一走 `/api/reader/img`，该接口带**主机白名单**（`reader_hub.IMG_HOST_SUFFIXES`），拒绝 `file://`、`javascript:` 与非白名单域名，避免被当成开放 SSRF 代理
* 本地书库只扫描**显式列出**的目录（`library/` + `paths.books` + `reader_roots`），不递归扫 `C:` 或整盘
* 外部源（MangaDex / Gutenberg / Internet Archive / なろう 等）返回的内容属第三方数据，按不可信内容处理

## LX 音源桥

* `lx_music_bridge.py` **只读**读取本机 LX Music 的 `user_api.json`，不写回
* `lx_userapi_host.js` 仅监听 `127.0.0.1`，用 Node `vm` 执行音源脚本 —— 这仍然是**在本机执行第三方 JavaScript**，`vm` 不是安全沙箱，只安装可信来源的音源
* 不需要 LX 音源时不要启动该桥，音乐功能退回内置源

## 破坏性操作

「看完即删」「清空缓存」删除真实文件；「下完睡眠 / 关机」会中断其它程序。两者都由用户主动确认触发，首次使用请先在测试目录验证，详见 [SETUP.md §12](SETUP.md)。
