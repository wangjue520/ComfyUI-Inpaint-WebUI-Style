# 发布到 ComfyUI Manager 完整步骤

本文档说明如何把这个项目发布到 ComfyUI Manager 让其他人能搜索安装。

ComfyUI 现在有**两种**节点发布渠道,都可以投递,推荐都做:

1. **ComfyUI Registry**(新,官方主推) — 通过 `pyproject.toml` 自动化发布
2. **ComfyUI-Manager 仓库**(旧,但用户基数大) — 提 PR 到 [ltdrdata/ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager)

---

## 第一步:替换占位符

打开下列文件,把 `wangjue520` 全部替换成你的真实 GitHub 用户名:

- `README.md`
- `LICENSE`
- `pyproject.toml`

可以用编辑器的"全局查找替换"(VS Code: `Ctrl+Shift+H`)。

---

## 第二步:在 GitHub 创建仓库

1. 登录 GitHub
2. 右上角 `+` → `New repository`
3. 仓库名:`ComfyUI-Inpaint-WebUI-Style`
4. 描述(可选):`WebUI-style inpaint nodes for ComfyUI`
5. **Public**(必须是公开的,Manager 才能索引)
6. 不要勾选 "Add README"、"Add .gitignore"、"Choose a license"(我们自己已经有这些文件了)
7. 点 `Create repository`

---

## 第三步:把代码推上去

在本地这个项目文件夹打开命令行,执行:

```bash
# 初始化 git 仓库
git init
git add .
git commit -m "Initial release: WebUI-style inpaint nodes"

# 关联到 GitHub 仓库(把 wangjue520 改成你的用户名)
git remote add origin https://github.com/wangjue520/ComfyUI-Inpaint-WebUI-Style.git
git branch -M main
git push -u origin main
```

如果是第一次用 git,你可能需要先配置:

```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱@example.com"
```

推送时如果要求登录,GitHub 现在用 **Personal Access Token** 代替密码 — 去 GitHub Settings → Developer settings → Personal access tokens 生成一个,推送时用 token 代替密码。

---

## 第四步:打 Tag(版本发布)

ComfyUI Registry 需要 Git tag 来识别版本。每次发新版本时:

```bash
git tag v1.0.0
git push origin v1.0.0
```

或者直接在 GitHub 仓库页面点 `Releases` → `Create a new release` → 填 tag `v1.0.0` → 发布。

---

## 第五步(推荐):发布到 ComfyUI Registry

Registry 是新的官方注册中心,在 https://registry.comfy.org

### 5.1 注册 Publisher

1. 访问 https://registry.comfy.org
2. 用 GitHub 账号登录
3. 创建一个 Publisher(发布者),Publisher ID 自己取,**记下来**

### 5.2 修改 pyproject.toml

把 `pyproject.toml` 里的 `PublisherId` 改成你刚才创建的 Publisher ID:

```toml
[tool.comfy]
PublisherId = "你的_publisher_id"
```

提交并推送:
```bash
git add pyproject.toml
git commit -m "Set publisher id"
git push
```

### 5.3 创建 API Token 并配置 GitHub Action(自动发布)

在 Registry 网站个人页面创建一个 API Key,然后:

1. 在 GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret
2. 名字:`REGISTRY_ACCESS_TOKEN`,值:刚才的 API Key

然后在仓库里创建 `.github/workflows/publish.yml`:

```yaml
name: Publish to Comfy Registry
on:
  workflow_dispatch:
  push:
    branches:
      - main
    paths:
      - "pyproject.toml"

jobs:
  publish-node:
    name: Publish Custom Node to registry
    runs-on: ubuntu-latest
    if: ${{ github.repository_owner == 'wangjue520' }}
    steps:
      - name: Check out code
        uses: actions/checkout@v4
      - name: Publish Custom Node
        uses: Comfy-Org/publish-node-action@main
        with:
          personal_access_token: ${{ secrets.REGISTRY_ACCESS_TOKEN }}
```

每次更新 `pyproject.toml` 的 version 字段并 push,就会自动发布新版本到 Registry。

---

## 第六步(推荐):提交到 ComfyUI-Manager 数据库

虽然 Registry 是新方向,但 ComfyUI-Manager 旧数据库目前用户基数更大,**最好两边都收录**。

1. Fork [ltdrdata/ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager) 到你的账号
2. 在你 fork 的仓库里编辑 `custom-node-list.json` 文件
3. 在合适位置(按字母顺序大致排)添加一条:

```json
{
  "author": "wangjue520",
  "title": "ComfyUI-Inpaint-WebUI-Style",
  "id": "comfyui-inpaint-webui-style",
  "reference": "https://github.com/wangjue520/ComfyUI-Inpaint-WebUI-Style",
  "files": [
    "https://github.com/wangjue520/ComfyUI-Inpaint-WebUI-Style"
  ],
  "install_type": "git-clone",
  "description": "WebUI-style inpaint nodes that reproduce AUTOMATIC1111 / Forge inpaint behavior in ComfyUI: mask blur, mask invert, four masked-content modes (original/fill/latent_noise/latent_nothing), only-masked padding, and composite-back-to-original for seamless inpainting without color shift."
}
```

4. 提交一个 Pull Request 到原仓库
5. 等待维护者审核合并(通常几天到一两周)

合并后,所有用户在 Manager 里搜索 `Inpaint WebUI Style` 就能找到并一键安装了。

---

## 维护建议

- **版本号管理**:每次更新功能,记得改 `pyproject.toml` 里的 `version`,并打新 Git tag
- **CHANGELOG**:重大变更建议在 README 加一个 "Changelog" 段落,或者用 GitHub Releases 的描述
- **Issues / PR**:GitHub 上别人可能提 issue 或 PR,记得查收

---

## 资源链接

- [ComfyUI Registry 文档](https://docs.comfy.org/registry/overview)
- [ComfyUI-Manager 仓库](https://github.com/ltdrdata/ComfyUI-Manager)
- [自定义节点开发指南](https://docs.comfy.org/custom-nodes/overview)
