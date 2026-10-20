# 新 Mod 模板

`template` 分支是 [cls1997/ls-docker-mods](https://github.com/cls1997/ls-docker-mods) 创建自定义 LinuxServer Docker Mod 的起点，不是可直接发布的 Mod。仓库说明和完整发布流程见 [master README](https://github.com/cls1997/ls-docker-mods/blob/master/README.md)。

Mod 是容器启动时解压到 `/` 的**单层镜像**，用于扩展 LinuxServer 容器。当前模板使用 **s6-overlay v3**，不兼容旧版 s6 v2 镜像。参考 [官方 Docker Mods 指南](https://github.com/linuxserver/docker-mods) 和 [容器自定义文档](https://docs.linuxserver.io/general/container-customization/#docker-mods)。

## 从这里创建新 Mod

```bash
git fetch origin
git switch -c universal-my-mod origin/template
```

已有同名分支时直接切换，避免覆盖。分支必须命名为 `<baseimage>-<modname>`；仅当确实适配多个基础镜像时使用 `universal`。

1. 设置 `.github/workflows/BuildImage.yml`：例如 `BASEIMAGE: "universal"`、`MODNAME: "my-mod"`。保留本仓库的 `GITHUB_REPO` 和 `ENDPOINT`；按实际支持情况设置 `MULTI_ARCH`（`true` 表示 amd64 和 arm64）。
2. 修改 Dockerfile 的 `maintainer`。默认 `FROM scratch` + 一次 `COPY root/ /`；如需构建阶段，参考 `Dockerfile.complex` 并将其内容用于 `Dockerfile`，最终阶段仍只能有一次 `COPY`。完成后删除不再使用的示例文件。
3. 重命名 `root/etc/s6-overlay/s6-rc.d/` 下所有 `imagename-modname` 占位符，包括目录名、依赖文件名、`user/contents.d` 条目及 `up` 中的绝对路径。
4. 编辑 `root/` 载荷和初始化脚本。模板脚本默认无副作用，不会安装示例包或运行虚构服务。删除不用的初始化步骤时，同时删除引用它们的依赖和 bundle 条目。
5. 将本 README 替换为 Mod 的用途、适用基础镜像/架构、环境变量、使用方法和验证步骤，保留适用的 AGENTS.md 约束。

## s6 v3 初始化顺序

```text
init-mods
  → init-mod-<baseimage>-<modname>-add-package
  → init-mods-package-install
  → init-mod-<baseimage>-<modname>-install
  → init-mods-end
```

- `add-package/run` 将系统包追加到 `/mod-repo-packages-to-install.list`，pip 包追加到 `/mod-pip-packages-to-install.list`，由基础镜像统一安装；跨发行版 Mod 须区分 Ubuntu/Alpine 包名。
- `install/run` 执行安装包之后的配置，必须可重复执行。`type` 为 `oneshot`，`up` 指向对应 `run`，并在 `user/contents.d/` 注册。
- 如需后台服务，新增 `svc-mod-<baseimage>-<modname>/`：`type` 为 `longrun`，`dependencies.d/init-services` 为空文件，在 `user/contents.d/` 注册；`run` 使用 `exec` 在前台运行进程，按需通过 `s6-setuidgid abc` 降权。模板默认不启用后台服务。
- 所有脚本使用 UTF-8（无 BOM）和 LF；`run`、`finish`、`check` 必须有可执行权限。

## 本地验证

```bash
find root -type f \( -name run -o -name finish -o -name check \) -exec chmod +x {} +
find root -type f \( -name run -o -name finish -o -name check \) -exec bash -n {} \;
git diff --check
docker build -t local/my-mod:test .
docker image inspect --format '{{len .RootFS.Layers}}' local/my-mod:test
```

层数必须为 `1`。使用其他解释器的脚本应改用对应语法检查器。还需在真实目标 LinuxServer 镜像中验证初始化、功能及重启；单纯构建成功不能证明 Mod 可用。不要将 Mod 镜像当应用直接运行。未发布时，可先将 `root/` 只读挂载到目标容器的临时目录检查载荷；完整 `DOCKER_MODS` 下载/应用流程需可访问的测试 registry 镜像。

## 发布

在 GitHub 仓库 **Settings → Secrets and variables → Actions** 配置至少一组凭据：

- GHCR：`CR_USER` + `CR_PAT`（具有 `read:packages`、`write:packages` 权限的 PAT）。
- Docker Hub：`DOCKERUSER` + `DOCKERPASS`（建议使用有写入权限的访问令牌）。

推送或合并到匹配 `BASEIMAGE-MODNAME` 的分支会验证并调用上游 `docker-mod-builder.yml@v1` 发布到已配置的 registry。`template`、占位参数和 PR 不发布；PR 只构建验证，不获取发布凭据。手动运行 **Build Image** 时选择 Mod 分支：不填写 `mod_version` 更新默认标签及完整提交 SHA 标签；填写版本则仅发布版本标签及版本-SHA 标签，不移动默认标签。

例如 `universal-my-mod` 默认产物为 `ghcr.io/cls1997/ls-docker-mods:universal-my-mod` 和 `:universal-my-mod-<完整提交SHA>`；Docker Hub 对应路径不带 `ghcr.io/` 前缀。发布成功后检查 Actions 日志、镜像层数、架构和 package 可见性，再在目标容器设置：

```yaml
environment:
  DOCKER_MODS: ghcr.io/cls1997/ls-docker-mods:universal-my-mod
```

GitHub 的 `workflow_dispatch` 手动入口要求默认分支也存在相同路径、含该事件的工作流文件。当前 `master` 未包含工作流，暂用 Mod 分支 push 发布；手动版本发布能力需先单独在默认分支配置入口，之后才能通过 Actions 的 Run workflow 使用。

这里只给出将来发布的路径示例，不代表该标签已经存在。多个 Mod 用 `|` 分隔。凭据只存于 GitHub Secrets，不写入文件或日志。
