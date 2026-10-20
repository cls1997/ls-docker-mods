# 自定义 LinuxServer Docker Mods

本仓库用于存放和维护自定义的 **LinuxServer Docker Mods**，为 [LinuxServer.io](https://linuxserver.io) 容器添加软件包、配置、初始化步骤或后台服务。

Docker Mod 是包含文件和脚本的**单层容器镜像**。支持 Mods 的 LinuxServer 容器启动时，根据 `DOCKER_MODS` 下载 Mod 的文件层并解压到容器的 `/`，再执行初始化流程。因此可以继续使用 LinuxServer 更新的基础镜像，同时应用自定义扩展。

概念、规范和示例以官方资料为准：

- [linuxserver/docker-mods](https://github.com/linuxserver/docker-mods)
- [LinuxServer 容器自定义：Docker Mods](https://docs.linuxserver.io/general/container-customization/#docker-mods)

本仓库的 Mod 由本仓库维护，并非 LinuxServer 官方维护的 Mod。仅使用可信来源；排查基础容器问题时，应先移除 Mods 并重建干净容器。

## 仓库结构与入口

本仓库采用**一个 Mod 一个分支**的方式，而不是在 `master` 下为每个 Mod 建目录。

| 分支/路径 | 用途 |
| --- | --- |
| [`master`](https://github.com/cls1997/ls-docker-mods/tree/master) | 仓库说明和协作规范 |
| [`template`](https://github.com/cls1997/ls-docker-mods/tree/template) | **创建新 Mod 的起点**，包含 Dockerfile、s6 v3 骨架与构建/发布工作流；模板本身不作为可用 Mod 发布 |
| `<baseimage>-<modname>` | 单个 Mod 的实现、使用说明与发布配置 |
| Mod 分支的 `root/` | 要添加到目标容器 `/` 下的文件和脚本 |
| Mod 分支的 `Dockerfile` | 构建单层 Mod 镜像 |
| Mod 分支的 `.github/workflows/BuildImage.yml` | 构建与发布入口 |
| `AGENTS.md` | 面向自动化助手及贡献者的分支、实现、验证和发布约束 |

现有 Mod 源码：[`universal-trust-kachitoritai-ca`](https://github.com/cls1997/ls-docker-mods/tree/universal-trust-kachitoritai-ca)。具体用途、兼容性和可用标签应查看该分支及其发布记录。

## 新增 Mod

使用当前仓库 checkout；已有工作须先妥善保存。**从 `template` 创建新分支，不从 `master` 开始：**

```bash
git fetch origin
git switch -c universal-my-mod origin/template
```

`universal-my-mod` 是占位示例，请替换为实际的 `<baseimage>-<modname>`。`baseimage` 使用目标 LinuxServer 镜像名称，跨镜像通用的 Mod 才使用 `universal`。已有 Mod 应在自己的分支上修改，无需重新从模板创建。

1. **配置身份。** 在 `.github/workflows/BuildImage.yml` 设置 `BASEIMAGE` 和 `MODNAME`，使分支名精确等于 `${BASEIMAGE}-${MODNAME}`。本仓库的 `GITHUB_REPO`、`ENDPOINT` 均为 `cls1997/ls-docker-mods`。更新 Dockerfile 的 `maintainer`。
2. **编写载荷。** 在 `root/` 中放置要加入容器的文件。默认 Dockerfile 使用 `FROM scratch` 和一次 `COPY root/ /`；复杂构建参考 `Dockerfile.complex`，最终镜像仍只能有一个文件层。
3. **配置 s6 v3。** 将模板所有 `imagename-modname` 替换为实际名称，包括目录、依赖文件名、`user/contents.d` 注册项和 `up` 中的绝对路径。当前模板支持 s6-overlay v3，不兼容旧版 s6 v2 镜像。
4. **安排初始化。** 需要的系统包/pip 包分别追加到 `/mod-repo-packages-to-install.list` 和 `/mod-pip-packages-to-install.list`，交由基础镜像统一安装。安装前脚本在 `init-mods` 后运行；后续配置依赖 `init-mods-package-install`，并阻塞 `init-mods-end`。后台服务依赖 `init-services`。不需要的模板步骤应连同依赖和注册项一起删除。
5. **验证并说明。** 设置脚本执行权限，更新分支 README，写明用途、支持的基础镜像/架构、配置变量及验证方法。按实际支持情况设置 `MULTI_ARCH`：`true` 构建 amd64 和 arm64，`false` 仅构建 amd64。细节见 [template README](https://github.com/cls1997/ls-docker-mods/blob/template/README.md)。

提交前至少执行：

```bash
find root -type f \( -name run -o -name finish -o -name check \) -exec chmod +x {} +
find root -type f \( -name run -o -name finish -o -name check \) -exec bash -n {} \;
git diff --check
docker build -t local/my-mod:test .
docker image inspect --format '{{len .RootFS.Layers}}' local/my-mod:test
```

最后输出必须为 `1`。非 Bash 脚本改用相应语法检查器。还应在真实目标 LinuxServer 容器中验证初始化、实际功能和重启；构建成功不能代替功能验证。Mod 镜像不直接作为应用运行。

## 发布 Mod

### 发布目标与凭据

发布由 **Mod 分支**的 [Build Image 工作流](https://github.com/cls1997/ls-docker-mods/blob/template/.github/workflows/BuildImage.yml) 调用上游 `linuxserver/github-workflows/.github/workflows/docker-mod-builder.yml@v1` 完成。根据配置的凭据，可推送到 GHCR、Docker Hub 或两者：

| Registry | 镜像路径 | GitHub Actions Secrets |
| --- | --- | --- |
| GHCR | `ghcr.io/cls1997/ls-docker-mods:<baseimage>-<modname>` | `CR_USER`、`CR_PAT` |
| Docker Hub | `cls1997/ls-docker-mods:<baseimage>-<modname>` | `DOCKERUSER`、`DOCKERPASS` |

在仓库 **Settings → Secrets and variables → Actions** 配置至少一组完整凭据。GHCR 的 PAT 需要 `read:packages` 和 `write:packages` 权限；Docker Hub 建议使用有目标仓库写入权限的访问令牌。不要将凭据写入源码、README 或日志。公开使用前还需确认对应 package/repository 的可见性和匿名拉取权限。

### 发布步骤与标签

1. 完成本地和目标容器验证，检查目标分支名与 `BASEIMAGE-MODNAME` 一致。
2. 将更改推送或合并到该 Mod 分支，工作流验证成功后自动发布。若通过 PR 开发，PR 的目标应为该 Mod 分支；当前模板中 PR 只验证，不发布，也不传入发布凭据。
3. 启用手动入口后，可在 **Actions → Build Image → Run workflow** 中选择该 Mod 分支手动发布。GitHub 要求默认分支也存在相同路径、含 `workflow_dispatch` 的工作流文件；当前 `master` 只有说明文件，因此尚无此手动入口，现阶段使用 Mod 分支的 push 发布。如需启用手动发布，需另行在默认分支添加入口，并保持模板不发布的限制。`template` 和未替换的占位参数不会发布。
4. 检查 Actions 的发布结果，确认 registry 中的镜像标签、架构及可见性，并使用实际目标容器测试 `DOCKER_MODS` 下载和应用流程。

默认发布以下标签：

```text
<baseimage>-<modname>
<baseimage>-<modname>-<完整提交SHA>
```

当前模板支持可选的 `mod_version` 手动输入。填写后启用版本覆盖模式，**只发布**以下标签，不移动上面的默认标签：

```text
<baseimage>-<modname>-<版本>
<baseimage>-<modname>-<版本>-<完整提交SHA>
```

若需要自动版本检测，可按上游接口调整 `set-vars` 的版本逻辑和 `MOD_VERSION_OVERRIDE`。不要假设手动版本覆盖会更新默认标签。

以上流程描述当前 `template` 的行为；已有 Mod 分支保留自己的工作流，模板更新不会自动同步。维护旧 Mod 时应单独检查并迁移其配置。

## 使用 Mod

在目标 LinuxServer 容器配置 `DOCKER_MODS`，例如下列 **待发布的占位示例**：

```yaml
services:
  app:
    image: lscr.io/linuxserver/openssh-server:latest
    environment:
      DOCKER_MODS: ghcr.io/cls1997/ls-docker-mods:universal-my-mod
    # 按目标镜像文档补齐其他环境变量、端口和卷。
```

请将镜像及 Mod 标签替换为实际兼容且已发布的版本。多个 Mod 使用 `|` 分隔：

```yaml
environment:
  DOCKER_MODS: "ghcr.io/cls1997/ls-docker-mods:universal-my-mod|other-owner/mods:other-mod"
```

需要可复现部署时，选择完整提交 SHA 标签，并核实基础镜像兼容性。
