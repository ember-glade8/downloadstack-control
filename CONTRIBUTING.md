# 贡献指南

## 开发环境

```bash
git clone <repo>
cd downloadstack-control
python -m pip install -r requirements.txt
python setup_wizard.py --scan     # 先确认环境
python panel.py                   # 直接跑面板
```

## 提交前必做

```bash
python scripts/scan_secrets.py .
```

必须输出 `[OK] 未发现敏感串`。会检查：

- Windows 用户目录绝对路径（`C:\Users\<user>\...`）
- qB 密码字段（`pass` 键）里出现真实值
- `rpc-secret=<32+ hex>`
- 内网 IP / 本机代理端口
- 个人化命名（私有脚本名、私人文件夹名）

## Commit 规范

采用 [Conventional Commits](https://www.conventionalcommits.org/)：

| 类型 | 含义 | 示例 |
| --- | --- | --- |
| `feat` | 新功能 | `feat(panel): 支持 qB 认证失败提示` |
| `fix` | 修 bug | `fix(installer): 修正 AriaNg 哈希校验` |
| `docs` | 文档 | `docs(readme): 补三平台安装说明` |
| `refactor` | 重构（不改行为） | `refactor(platform): 抽出 kill_tree` |
| `perf` | 性能 | `perf(probe): 轮询合并为一次请求` |
| `chore` | 杂项/依赖 | `chore(deps): 锁定 flet==1.1.3` |

格式：`type(scope): 一句话中文描述`，scope 用模块名（panel / installer / wizard / gui / platform / docs）。

## 分支与 PR

- 分支：`feat/xxx`、`fix/xxx`
- PR 描述请写清：
  1. 改了什么
  2. 怎么验证（命令 / 截图 / 日志）
  3. 影响范围（是否动到配置格式、跨平台行为）

## 代码约定

- **业务逻辑与 UI 分离**：探测、启停、备份等不要塞进 UI 构建函数
- **跨平台**：平台差异只允许出现在 `panel.py` 顶部「平台差异层」和 `install.bat/.sh` 对应段落
- **不引入重依赖**：新增 pip 包需在 PR 里说明理由与体积影响
- **不内置第三方二进制**：只允许在安装器里从官方地址下载
- **异常必须被吞掉并记录**：面板任何外部调用都要 try/except + 日志，不许让界面崩

## 报告问题

请附：
- `diag-report.txt`（`diag.bat` / `sh diag.sh` 生成）
- 复现步骤与期望行为

**不要在公开 issue 贴 `config.json`、日志原文或任何密钥**，先脱敏。
