# 仓库协作指南

## 仓库定位与分支

- 本仓库存放自定义 LinuxServer Docker Mods。Mod 是在目标容器启动时提取到 `/` 的单层镜像，不是独立应用镜像。
- `master` 保存仓库介绍和协作说明；`template` 是创建新 Mod 的起点；每个 Mod 独立维护在 `<baseimage>-<modname>` 分支。
- 使用现有 checkout。云任务已有隔离环境，除非用户明确要求，不创建 Git worktree。
- 修改前检查 `git status`、当前分支和目标分支内容，保护已有修改。不要将某个 Mod 的载荷直接放入 `master`，也不要将模板合并进已有 Mod 而覆盖其定制逻辑。
- 新 Mod 从 `origin/template` 创建分支；修复现有 Mod 则从它自己的分支开始。涉及多个分支的改动须分别交付，明确本地提交和远端状态。

## 创建与维护 Mod

1. 阅读目标分支 README、Dockerfile、`root/` 和 `.github/workflows/BuildImage.yml`。开发流程参考 master README；模板细节参考 template README。
2. 设置 `BASEIMAGE`、`MODNAME`，保证发布分支精确等于 `${BASEIMAGE}-${MODNAME}`。`universal` 必须有实际兼容性依据。`GITHUB_REPO` 和 `ENDPOINT` 默认均为 `cls1997/ls-docker-mods`。
3. 同步替换模板中所有 `imagename-modname`、`replace_baseimage`、`replace_modname` 和 `maintainer` 占位符，包括 s6 依赖文件名、bundle 条目和 `up` 路径。
4. 最终镜像必须 `FROM scratch` 且只有一个文件层；通常只用一次 `COPY root/ /`。复杂构建可用多阶段，但最终仅复制组装好的载荷一次。
5. 使用 s6-overlay v3。安装包前的步骤依赖 `init-mods`，并作为 `init-mods-package-install` 的依赖；安装包后的步骤依赖 `init-mods-package-install`，并作为 `init-mods-end` 的依赖。所需 oneshot/longrun 都须加入 `user/contents.d`。
   本镜像配置 Mod 的 `-early` 服务是例外：它依赖 `init-config-end`，而 `init-mods` 依赖它，保证标准 Mod 初始化前配置完成。不要给 `-early` 添加 `init-mods` 依赖，否则会形成循环。旧服务名保留为空操作兼容节点，以支持覆盖更新已有容器。
6. 将系统包和 pip 包分别追加到 `/mod-repo-packages-to-install.list`、`/mod-pip-packages-to-install.list`，避免重复实现基础镜像的包安装器。需要时区分 Ubuntu 和 Alpine。
7. longrun 服务依赖 `init-services`，使用 `exec` 在前台运行；初始化脚本应可重复执行，避免每次启动重复追加配置。不要保留会运行的演示命令或不需要的服务。
8. 脚本和 s6 文件使用 UTF-8 无 BOM、LF；`run`、`finish`、`check` 保持可执行权限。下载依赖保留 TLS、签名或校验和验证。
9. README 应列明用途、支持的基础镜像和架构、配置变量、安装示例、外部依赖与验证方法。`MULTI_ARCH=true` 前确认 amd64、arm64 载荷均可用。

## 验证与交付

- 运行 `git diff --check`，对 Bash 脚本运行 `bash -n`，检查执行权限。其他解释器使用相应检查器。
- 有 actionlint 时验证 `.github/workflows/*.yml`；修改 workflow 时检查 PR 不传入发布 Secrets、不运行有凭据的 `pull_request_target` 构建。
- 在 Mod 分支运行 `docker build -t local/mod:test .`，使用 `docker image inspect --format '{{len .RootFS.Layers}}' local/mod:test` 确认恰好一层。修改复杂示例时也构建 `Dockerfile.complex`。
- 用实际支持的 LinuxServer 镜像验证 Mod 功能、启动顺序和重启。说明用到的基础镜像与架构，区分已执行、失败和未执行检查；没有相关服务时不虚构测试结果。
- 仅文档改动检查链接、命令和分支/标签规则即可，不引入无关依赖或测试。
- 未经用户要求，不推送分支、触发远端发布、上传镜像或修改 registry 可见性。跨分支改动可保存在本地分支提交中，并报告提交 SHA。

## 发布规则

- `.github/workflows/BuildImage.yml` 是发布入口，调用 `linuxserver/github-workflows/.github/workflows/docker-mod-builder.yml@v1`。更改前检查其当前输入和标签语义，不能假设上游行为不变。
- 模板更新不自动更新已有 Mod 分支；发布前核对目标分支自己的 workflow。当前模板仅在本仓库匹配名称的 Mod 分支发生 push 或 workflow_dispatch 后发布，PR 只验证，template 不发布。
- GHCR 输出 `ghcr.io/cls1997/ls-docker-mods:<baseimage>-<modname>`；Docker Hub 输出 `cls1997/ls-docker-mods:<baseimage>-<modname>`。默认另有 `-<完整提交SHA>` 标签。
- 当前模板手动输入 `mod_version` 时使用版本覆盖模式，只发布 `-<版本>` 和 `-<版本>-<完整提交SHA>` 标签。不要在文档中将其描述为默认标签更新。
- `workflow_dispatch` 的手动入口要求默认分支存在相同路径且包含该事件的工作流。当前 master 没有该文件，不能承诺 Actions UI 已有 Run workflow 按钮；现阶段用 Mod 分支 push 发布，启用手动入口须单独配置默认分支。
- 本 Mod 的 GHCR 发布使用 `github.actor` 和自动提供的 `GITHUB_TOKEN`，经上游工作流的 `CR_USER`/`CR_PAT` 参数传入；仅 publish 任务授予 `packages: write`，PR 验证保持只读。已有 package 须授予本仓库 Actions 写入权限。Docker Hub 仍使用 `DOCKERUSER`/`DOCKERPASS`。不要在对话、仓库、脚本或日志中暴露值。
- 以 Actions 成功记录和实际 registry 产物确认发布，不把本地构建当成已发布。测试容器用 `DOCKER_MODS=<registry>/<endpoint>:<tag>`；多个 Mod 以 `|` 分隔。

## 官方参考

- https://github.com/linuxserver/docker-mods
- https://github.com/linuxserver/docker-mods/tree/template
- https://docs.linuxserver.io/general/container-customization/#docker-mods
