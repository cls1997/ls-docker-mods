# 验证记录

日期：2026-10-20。此文件记录当前实现的实测范围，不表示镜像已经发布。

## 已通过

- 15 项离线功能测试：`python3 -m unittest discover -s tests -v`。
- 工作流 actionlint 检查、Bash 语法、s6 注册/依赖/执行权限和 `git diff --check`。
- `linux/amd64`、`linux/arm64` 两个目标均构建成功，最终镜像均恰好 1 个文件层。
- 以下 10 个实际 LinuxServer 基础镜像（均 amd64）完成初始化、包管理器配置检查、重复运行及重启检查。早期关卡更新后已全部重跑，使用 `S6_VERBOSITY=2` 日志断言每次启动均先完成 `init-mod-universal-package-manager-certnet-mirror-early`，再启动 `init-mods`。
- 升级兼容性：在 Alpine 3.23 中先复制旧版本 `61f9c05` 的 root 载荷，再覆盖新载荷，验证初始化、镜像配置和重启顺序均通过，没有旧依赖残留引起的循环。

| 基础镜像 | 实际系统版本 | 结果 | 本地基础镜像 ID（sha256） |
| --- | --- | --- | --- |
| `ghcr.io/linuxserver/baseimage-alpine:3.23` | Alpine Linux v3.23 | PASS | `2fe1c115d748547086eff3f3b96a39d55c6d122fd99de2fed27fdc8f25d03be0` |
| `ghcr.io/linuxserver/baseimage-ubuntu:noble` | Ubuntu 24.04.5 LTS | PASS | `1045435ac044c2b75e605f1a31c7d948829d2e8f1f64adc70f647fc81172c507` |
| `ghcr.io/linuxserver/baseimage-debian:trixie` | Debian GNU/Linux 13 (trixie) | PASS | `ad4f24578d426db79c6ce842550ad8b408660a24c2c3c190699a00023510d1c4` |
| `ghcr.io/linuxserver/baseimage-debian:kali` | Kali GNU/Linux Rolling | PASS | `cc94bf09e505bc8dfa1a19f0f2dd7f8cfd2eef466d95721c9c55b1f6114f0db6` |
| `ghcr.io/linuxserver/baseimage-arch:latest` | Arch Linux | PASS | `e632574c4eca088e0585a9820681ee8bef08dba7e1684f4444f37dc0c20cd46c` |
| `ghcr.io/linuxserver/baseimage-fedora:42` | Fedora Linux 42 (Container Image) | PASS | `467710b9b7be1cd8b4b3519fc7ac5e1cd9627facfb80e920582989698894088e` |
| `ghcr.io/linuxserver/baseimage-el:9` | Red Hat Enterprise Linux 9.7 (Plow) | PASS | `a91a3132db9a5561bd3672abe34beecaa6f077ae4b8194acadcc2fe9018522d5` |
| `ghcr.io/linuxserver/baseimage-fedora:44` | Fedora Linux 44 (Container Image) | PASS | `a2ef27bf7c1a95e68500cb4bd02e7a4d92d064c0d857ca1db3219ea70396946f` |
| `ghcr.io/linuxserver/baseimage-alpine:3.24` | Alpine Linux v3.24 | PASS | `a0d54bcf8f576de49f6498c8bdcad2a6407a97133e98f607895f653e7f0b4dff` |
| `ghcr.io/linuxserver/baseimage-ubuntu:resolute` | Ubuntu 26.04.1 LTS | PASS | `32f0058c3e6f0ea4991af04b0fa9f47b780865b9c6abbd896c57fb99d924c4b7` |

运行脚本：`python3 tests/smoke.py`。该脚本使用 `tests/Dockerfile.smoke` 把真实载荷复制到基础镜像，启动 s6 并重复启动；APT 使用 `--print-uris update` 验证配置解析，Pacman 使用 `pacman-conf`，DNF 使用 `--cacheonly repolist`。不执行软件包下载或系统升级。UBI 的通过表示原有仓库未被替换，而非获得 CERNET 加速。

Fedora 44 另通过 `dnf --dump-repo-config=fedora,updates` 核实生效配置：两个仓库均使用 CERNET mirrorlist，原 metalink/baseurl 已清空，`gpgcheck = 1` 保持启用。

## 未验证及限制

- 当前代理对 `mirrors.cernet.edu.cn` 和帮助站返回 HTTP 403，未能执行 CERNET 索引/软件包的真实下载、签名验证或速度对比。帮助内容通过官方 `mirrorz-org/mirrorz-docs` 源码核对，未绕过网络策略或关闭 TLS 校验。
- arm64 已验证镜像构建和 Ubuntu ports / Arch ARM 的离线转换；未在 ARM 上启动真实基础镜像。
- Fedora 45 的新仓库路径通过离线夹具验证，真实 DNF5 使用 Fedora 44 镜像验证。
- nginx、KasmVNC、Selkies、rdesktop 的发行版映射已定义；未逐个启动这些完整桌面/应用基础镜像，验证的是它们继承的发行版基础镜像。
- 未验证 registry 拉取和 `DOCKER_MODS` 实际下载/提取过程，未推送分支或发布镜像。
