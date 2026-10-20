# universal-package-manager-certnet-mirror

为 LinuxServer 容器的发行版包管理器配置 [CERNET 镜像服务](https://mirrors.cernet.edu.cn)，加速软件包下载。名称按本仓库约定保留 `certnet` 拼写；服务名称和域名是 **CERNET**。

本 Mod 只调整仓库地址，不安装包、不升级系统、不改变发行版版本、仓库组件或签名校验策略。每次启动会按 `/etc/os-release` 自动选择配置，且在 `init-mods-package-install` 之前完成，使其他 Mod 的统一包安装也能使用镜像。仅适用于 s6-overlay v3 基础镜像。

## 基础镜像定义

下表覆盖 [LinuxServer baseimage 仓库列表](https://github.com/linuxserver?q=baseimage&type=all&language=&sort=) 中的 10 个仓库。按**容器内部发行版**判断，不凭镜像名称猜测；读取 `/etc/os-release`，缺失时回退到 `/usr/lib/os-release`（部分 Arch 基础镜像采用此布局）。桌面镜像的不同发行版标签分别使用对应规则。

| LinuxServer baseimage | 发行版 / 包管理器 | 本 Mod 的定义 |
| --- | --- | --- |
| `baseimage-alpine` | Alpine / APK | CERNET `alpine`，保留原版本号、main/community、edge 和标签 |
| `baseimage-alpine-nginx` | Alpine / APK | 同 Alpine |
| `baseimage-ubuntu` | Ubuntu / APT | x86 使用 `ubuntu`，ARM 等 ports 架构使用 `ubuntu-ports` |
| `baseimage-debian` | Debian、Kali / APT | Debian 使用 `debian` + `debian-security`；Kali 标签使用 `kali` |
| `baseimage-arch` | Arch Linux、Arch Linux ARM / Pacman | x86_64 使用 `archlinux/$repo/os/$arch`；ARM 使用 `archlinuxarm/$arch/$repo` |
| `baseimage-fedora` | Fedora / DNF | `fedora` 的 release/updates mirrorlist；按当前 44 分支及历史版本分别适配（旧 42 分支标记为弃用，不代表 44 分支弃用） |
| `baseimage-el` | Red Hat UBI / DNF | **明确不换源**：CERNET 无等价 UBI 仓库，保留原仓库并输出提示；该 baseimage 已被上游弃用 |
| `baseimage-kasmvnc` | Alpine、Arch、Debian、Fedora、Kali、Ubuntu | 分别使用上述发行版规则 |
| `baseimage-selkies` | Alpine、Arch、Debian、Fedora、Kali、Ubuntu（含 dev 的实际发行版） | 分别使用上述发行版规则 |
| `baseimage-rdesktop` | Alpine、Ubuntu 等历史标签 | 按实际发行版使用上述规则；该 baseimage 已被上游弃用，仅 s6 v3 标签适用 |

“定义覆盖”不表示恢复已弃用镜像的支持，也不保证镜像站仍提供过期发行版。未知发行版、无配置文件或未知 Arch 架构会输出提示/保留原配置，不会误用其他发行版的包。

### 包管理器行为

- **APT（Ubuntu/Debian）**：替换已识别的官方 URL，使用 CERNET 官方文档的 `mirror+https://mirrors.cernet.edu.cn/api/apt/mirrorlist/...` 接口。安全更新添加 `?official_index=1`，优先取官方索引，再从镜像下载包。支持 `.list`、DEB822 `.sources`、多行 URIs/Suites，保留 Signed-By、架构限制、组件和 Enabled。混合普通/安全 Suites 的 DEB822 stanza 会拆开，以便只给安全源加参数。需要 APT ≥ 1.6，当前支持的 LinuxServer Ubuntu/Debian 满足此条件。
- **APT（Kali）**：将官方 `http.kali.org/kali` 或 `kali.download/kali` 替换为 `https://mirrors.cernet.edu.cn/kali`，保留 kali-rolling 等 suite 和组件。
- **APK**：替换官方 `dl-cdn` / `dl-N` Alpine URL；兼容 `/etc/apk/repositories` 和 `repositories.d/*.list`，保留版本和仓库标签。
- **Pacman**：将 CERNET Server 放在 `/etc/pacman.d/mirrorlist` 顶部，保留原 Server 作为后备；不会修改 SigLevel，也不会执行可能造成部分升级的 `pacman -Sy`。
- **DNF**：仅调整 Fedora 的 `fedora` / `updates` 仓库，不启用 debug/source 仓库。Fedora ≤ 43 修改对应 `.repo` section；Fedora ≥ 44 使用 `/etc/dnf/repos.override.d/99-certnet-mirror.repo`，兼容 Fedora ≥ 45 将系统仓库文件移至 `/usr/share/dnf5/repos.d` 的布局。使用 CERNET RPM mirrorlist，保留原有 GPG key、校验和 enabled 设置。

第三方仓库、PPA 和无法识别的自定义镜像不修改。已经改成其他镜像的来源不会强行重置。HTTPS 和软件包签名校验始终保留；不添加 `trusted=yes`、关闭 TLS 验证或导入其他发行版的密钥。

## 使用

待镜像实际发布后，在目标 LinuxServer 服务设置：

```yaml
services:
  app:
    image: lscr.io/linuxserver/openssh-server:latest
    environment:
      DOCKER_MODS: ghcr.io/cls1997/ls-docker-mods:universal-package-manager-certnet-mirror
    # 按目标镜像文档补齐其他环境变量、端口及卷。
```

配合其他 Mod 时用 `|` 分隔：

```yaml
environment:
  DOCKER_MODS: "ghcr.io/cls1997/ls-docker-mods:universal-package-manager-certnet-mirror|linuxserver/mods:universal-tshoot"
```

无需额外配置变量。目标平台为 `linux/amd64`、`linux/arm64`，载荷均为 Bash/awk 文本；具体发行版/软件仓库也须支持相应架构。Mod 初始化日志以 `[certnet-mirror]` 开头。CERNET 提供镜像选择与重定向，实际速度取决于网络和所选镜像站，不保证一定比官方源快。

如果外网访问受限，应允许 `mirrors.cernet.edu.cn`、返回的镜像站域名，以及安全更新官方索引域名。只允许 CERNET 一个域名并不足以下载所有索引和软件包。

## 备份与退出

首次修改现有配置文件时，在旁边保留 `<原文件>.certnet-mirror.bak`，不会在重启时覆盖备份；内容未改变时不重写文件。新建的 DNF override 不需要原文件备份。不会修改自定义文件的权限。

移除 `DOCKER_MODS` 后**重新创建容器**即可恢复基础镜像配置，单纯重启同一个容器不会回滚其可写层。若仓库配置通过 bind mount/volume 持久化，需自行恢复旁边的备份；Fedora 新建的 `99-certnet-mirror.repo` 可删除。不要恢复覆盖其他管理员后续修改的配置。

## 开发与验证

```bash
python3 -m unittest discover -s tests -v
bash -n root/usr/local/lib/certnet-mirror/configure
git diff --check
docker build -t local/certnet-mirror:test .
docker image inspect --format '{{len .RootFS.Layers}}' local/certnet-mirror:test
```

分发镜像必须只有 **1 个文件层**。离线测试使用临时根目录执行真实配置转换程序，验证各发行版、APT 两种格式、Ubuntu ARM 路径、原有签名配置/第三方源保留、备份及重复运行。

在实际 LinuxServer 基础镜像中检查 s6 启动与重启（需 Docker）：

可直接运行 `python3 tests/smoke.py` 检查预设的 10 个基础镜像，或加 `--image <镜像:标签>` 指定单个镜像。也可手动执行：

```bash
docker build -f tests/Dockerfile.smoke \
  --build-arg BASE_IMAGE=ghcr.io/linuxserver/baseimage-ubuntu:noble \
  -t local/certnet-smoke:test .
docker run -d --name certnet-smoke local/certnet-smoke:test
docker logs certnet-smoke
docker exec certnet-smoke cat /etc/apt/sources.list
docker restart certnet-smoke
docker logs certnet-smoke
docker rm -f certnet-smoke
```

其他发行版替换 BASE_IMAGE，并检查对应配置文件和日志。测试镜像通过 COPY 模拟载荷已提取，不包含从 registry 下载 Mod 的流程。联网验证还应在目标网络中运行 `apt-get update` / `apk update` / `dnf makecache`，确认元数据可用、签名校验成功；Arch 使用完整系统升级流程，避免部分升级。

当前实现的验证结果与网络限制见 [tests/VALIDATION.md](tests/VALIDATION.md)。

## 发布

分支为 `universal-package-manager-certnet-mirror`，工作流参数为 `BASEIMAGE=universal`、`MODNAME=package-manager-certnet-mirror`、`MULTI_ARCH=true`。仅在匹配的 Mod 分支 push/手动运行后发布；PR 只验证。

GHCR 使用 GitHub 自动提供的 `GITHUB_TOKEN` 和 `github.actor`，通过上游工作流的 `CR_PAT` / `CR_USER` 参数传入，无需维护同名个人 Secrets。仅 publish 任务授予 `packages: write` 权限；已有 GHCR package 还需在 **Manage Actions access** 中授予本仓库写入权限。Docker Hub 仍使用 `DOCKERUSER` / `DOCKERPASS`。默认标签为 `universal-package-manager-certnet-mirror` 和其 `-<完整提交SHA>` 版本。手动 `mod_version` 只发布版本标签，不移动默认标签。手动入口仍需默认分支存在对应 workflow；详见 [仓库发布说明](https://github.com/cls1997/ls-docker-mods/blob/master/README.md)。代码完成和本地构建不表示已经发布。

## 参考

- [Ubuntu](https://help.mirrors.cernet.edu.cn/ubuntu/) / [Ubuntu ports](https://help.mirrors.cernet.edu.cn/ubuntu-ports/)
- [Debian](https://help.mirrors.cernet.edu.cn/debian/) / [Debian security](https://help.mirrors.cernet.edu.cn/debian-security/)
- [Alpine](https://help.mirrors.cernet.edu.cn/alpine/) / [Arch](https://help.mirrors.cernet.edu.cn/archlinux/) / [Arch ARM](https://help.mirrors.cernet.edu.cn/archlinuxarm/)
- [Fedora](https://help.mirrors.cernet.edu.cn/fedora/) / [Kali](https://help.mirrors.cernet.edu.cn/kali/)
- 帮助站访问受限时，可核对官方源文档仓库 [mirrorz-org/mirrorz-docs](https://github.com/mirrorz-org/mirrorz-docs)；本次实现参考提交 `5f4f561b195d39eadbf486687325dd02eacb9937`。
