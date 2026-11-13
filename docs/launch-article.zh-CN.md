# 用 AI 做 X 多图长条、连续切片与横滑揭晓：开源 Skill `sweety-x-image-play` 发布

![X 多图创作 Skill：独立窄条、连续切片与横滑揭晓](https://raw.githubusercontent.com/threerocks/sweety-x-image-play/main/docs/assets/launch-cover.png)

`sweety-x-image-play` 是一个面向 X（Twitter）多图玩法的开源 Skill，现已发布在 GitHub：[https://github.com/threerocks/sweety-x-image-play](https://github.com/threerocks/sweety-x-image-play)。它由 Skill 工作流规范和本地确定性 Python 脚本组成，支持 **2–20 张**切片导出：在支持生图的 AI 助手环境里，可以用自然语言生成并导出独立窄条、连续长图和横滑揭晓组图；如果手头已经有现成横图或素材，也可以跳过生图步骤，直接用脚本完成精确裁切、中段延展、排序打包与结果校验。

靠纯提示词直接让图像模型输出多张首尾相连或超细窄条的图片，通常难以控制精确像素宽高、边缘对齐与顺序编号。这个 Skill 把「构图与生图」交给 AI，把「像素计算、拼接校验与文件输出」交给本地脚本，目前已收录覆盖三种模式的 5 组公开示例（下文三组代表样例，加上早前同属连续切片模式的「机器人与猫咪」与「云中游龙」各 20 张，共计 84 张）。

## 三种模式的创意区别

同样是多图横向排列，`sweety-x-image-play` 对应三种不同的视觉与叙事结构，先明确它们在创意上的分工，再分别看实际导出效果：

| 模式 | 创意核心 | 读者在时间线上的体验 | 资产组织方式 | 代表样例 |
| :--- | :--- | :--- | :--- | :--- |
| **`independent` 独立窄条** | 一图一物、并排成列 | 看到几根独立细长物件整齐竖立，对比材质与配色 | 每张单独成物，保留两端比例，只拉长指定中段 | 四支原创彩铅（4 张 `40×1920`） |
| **`panorama` 连续切片** | 一幅横卷、多格贯通 | 从左到右顺着同一场景横移浏览，感受横向空间跨度 | 一张完整母图经修边后按等宽连续竖切 | 云海列车（20 张 `76×1024`） |
| **`reveal` 横滑揭晓** | 动作引导、终点揭晓 | 先看到动作或连接线索，沿中段连续横滑，在末图获得答案 | `head` 首图 + 复用的 `bridge` 中段 + `tail` 尾图 | 手臂延伸摸猫头（20 张 `780×1200`） |

---

## 玩法一：`independent` 独立窄条——四支原创彩铅

![四支原创彩铅：independent 模式四张窄条预览](https://raw.githubusercontent.com/threerocks/sweety-x-image-play/main/examples/pencils-independent/preview.png)

> 注：上图为方便浏览做过缩小排版，不代表真实文件尺寸；实际导出与上传使用的是 4 张独立的 `40×1920` PNG 原图。示例包下载：[pencils-independent/set/images.zip](https://github.com/threerocks/sweety-x-image-play/blob/main/examples/pencils-independent/set/images.zip)。

- **读者看到了什么**：珊瑚粉、薄荷绿、天空蓝、鹅黄四支完整彩铅并排呈现。每一张图都是一支从笔尖到笔尾完整收束的铅笔，而不是把同一支笔横向切成了四段。
- **适用题材**：彩铅、充电线、竹子、零食棒（如 2026 年 11 月 12 日在时间线上观察到的 [mamintzz 四张 Pocky 窄条帖子](https://x.com/mamintzz/status/2120786097701842965)，当时读取到的加载尺寸同样为 `40×1920`，不一定等于作者上传原尺寸）等本身具有细长比例、适合单图独立成物的题材。
- **制作方法**：这组案例复用了项目早前制作并核验过的四支原创彩铅素材。如果直接生成 `40×1920` 极窄画幅，主体两端极易变形；脚本的做法是先保留笔尖与笔尾的原始比例，只对人工或方案明确选定的笔杆中段区域做纵向延长与重采样，再分别输出为 4 张独立 `40×1920` PNG。
- **可复制自然语言请求**：

> 使用 $sweety-x-image-play，按 independent 独立窄条模式制作 4 张 40×1920 PNG，主题是四支不同配色的原创彩铅（珊瑚粉、薄荷绿、天空蓝、鹅黄）。每张都是完整物体，保留笔尖与笔尾比例，只延长选定的笔杆中段，输出单图、images.zip 和预览页并检查尺寸。

---

## 玩法二：`panorama` 连续切片——云海列车

![云海列车：20 张连续切片的拼图预览](https://raw.githubusercontent.com/threerocks/sweety-x-image-play/main/examples/mountain-train/preview.png)

> 注：预览图加入了模拟间距以方便发帖前检查接缝，实际导出为 20 张连续编号的独立 `76×1024` PNG。示例包下载：[mountain-train/set/images.zip](https://github.com/threerocks/sweety-x-image-play/blob/main/examples/mountain-train/set/images.zip)。项目既有的「机器人与猫咪」（20 张）和「云中游龙」（20 张）同样属于 `panorama` 连续切片模式，而非另两种玩法。

- **读者看到了什么**：一列驶过山巅云海的列车横贯多张画格，铁轨、车厢与云层沿着横向顺序自然衔接。读者顺着画面一路向右浏览全景细节，重点在于画面的连贯与延展感，不依赖结尾反转。
- **适用题材**：列车、长桥、云中游龙、长卷山水、长桌群像等适合横向连续构图的场景。构图时让铁轨、桥梁、绳索或龙身穿过相邻画面边界会更自然；普通人像如果切分过多，五官容易正好落在客户端图缝里被截断。
- **制作方法**：先完成一张 `1536×1024` 的横向母图，脚本在左右两侧各裁掉 8 像素得到恰好能被 20 整除的 `1520×1024` 画布，再按精确坐标连续竖切为 20 张 `76×1024` 独立 PNG，全程不做拉伸或挤窄。导出时脚本会自动把 20 张切片重新拼回，校验与裁边后的母图逐像素一致。
- **可复制自然语言请求**：

> 使用 $sweety-x-image-play，按 panorama 连续切片模式做一组“云海列车”。先生成横向母图，裁边后连续竖切为 20 张 76×1024 独立 PNG，按顺序编号并确保拼回后与准备后的母图逐像素一致，给我单图、images.zip 和本地预览。

---

## 玩法三：`reveal` 横滑揭晓——手臂延伸摸猫头

![手臂延伸摸猫头：20 张切片的本地逐帧演示动图](https://raw.githubusercontent.com/threerocks/sweety-x-image-play/main/examples/arm-reveal/sequence.gif)

> **重要说明**：上方动图是根据导出的 20 张成品 PNG 在本地制作的逐帧演示，画面上带有 `01/20` 至 `20/20` 的编号，**不是 X 客户端实机录屏，也不保证 X 界面呈现效果**；实际发帖上传的仍是 20 张独立的 `780×1200` PNG，GIF 只用于文章讲解。静态备用图 [arm-reveal/preview.png](https://raw.githubusercontent.com/threerocks/sweety-x-image-play/main/examples/arm-reveal/preview.png) 展示的是首图、一种中段、尾图这三类基础素材对照，**不是**完整 20 张拼图。示例包下载：[arm-reveal/set/images.zip](https://github.com/threerocks/sweety-x-image-play/blob/main/examples/arm-reveal/set/images.zip)。

- **读者看到了什么**：这一玩法参考了 [ripped1taliano 的 20 图创意帖](https://x.com/ripped1taliano/status/2121044139705778359)——原帖首图是路飞拿着肉、另一只手臂向右延伸，中段只有水平手臂，末图手掌轻放在乔巴头上。这里复现的是“伸长手臂 → 持续横滑 → 末尾摸头”的互动机制，使用新生成的原创人物与猫咪（不搬运原作者图片，也不冒充原帖角色）：首图中一个穿黄 T 恤的原创人物坐在凳子上，一只手拿着面包，另一只裸露手臂像橡皮一样向右伸长；连续向右滑动 18 张只有水平手臂的中段画面后，在末图看到手掌轻抚到一只开心的橘白猫头顶。
- **适用题材**：需要“引导动作 + 持续过渡 + 终点揭晓”的横滑叙事场景，例如“伸长手臂摸到谁”、“视线看向哪里”、“绳索另一头牵着什么”。
- **制作方法**：这组案例实际按 `reveal` 导出方案生成 20 张独立的 `780×1200` PNG，与 `panorama` 连续切片不同——它**不是**把原图均分成 20 份，而是延长中段直到末尾揭晓。首图（`head`）、中段（`bridge`）和尾图（`tail`）三类资产取自同一张 `2172×724` 原创图：先拆分为三个 `724×724` 区域，再各自等比缩放到 `780×780`，最后居中补白到 `780×1200`；最终导出的 20 张成品由 1 张首图、同一手臂中段资产复用 18 次、1 张尾图组成，本次检查确认首、中、尾接缝处的手臂上下边缘位置一致。
- **可复制自然语言请求**：

> 使用 $sweety-x-image-play，按 reveal 横滑揭晓模式制作一组 20 张 780×1200 的叙事组图：用原创人物（穿黄 T 恤坐凳子、一手拿面包），另一只手臂像橡皮一样向右延长，末尾手掌摸到开心的橘白猫头。首图 1 张、同一中段手臂资产复用 18 次、尾图 1 张，保证中段连接高度和粗细一致（不是 20 个不同动作），交付单图、images.zip 和本地模拟预览。

---

## 交付结构与核验机制

每次运行都会写入一个独立的新输出目录，默认开启覆盖保护以免覆盖旧作品，统一生成四类文件：

- `images/01.png` 起按上传顺序编号的独立 PNG 文件；
- `images.zip`：仅包含这批独立 PNG 的压缩包，方便传到手机端发布；
- `preview.html`：可在本地浏览器打开的横向预览页，支持调节显示高度和模拟间距（本地模拟仅用于核对衔接，不等同于 X 客户端最终渲染效果）；
- `manifest.json`：记录图片张数、像素宽高、文件摘要及检查结果。

仓库已有 **13 项自动测试**全部通过，覆盖尺寸越界拦截、覆盖保护、文件篡改检测与 ZIP 一致性等场景。针对新制作的素材与每次导出，脚本和检查流程都会核对实际文件数量、单张真实宽高、ZIP 包条目一致性，以及对应的连续切片拼回一致性或 `reveal` 模式的中段重复与端点连接。

## 依赖说明与安装

本地运行需要 **Git**、**Python 3.9+** 和 **ImageMagick 7**（macOS 装有 Homebrew 时可执行 `brew install imagemagick`）。切片与校验脚本只在本地离线执行；若由 AI 助手生成母图或素材，会调用宿主助手的生图工具并消耗对应额度。

如果需要在导出时移除图片的 EXIF、GPS 及来源元数据，可另行安装独立的隐私技能 [sweety-image-privacy](https://github.com/threerocks/sweety-skills/tree/main/skills/sweety-image-privacy) 到同一技能目录；未安装时脚本仍可正常出图，但会在结果报告中标明隐私工作流未完整执行；导出器本身仍会做基础元数据清理（可见水印或画面内文字不会被元数据清理移除）。

将仓库克隆到技能目录即可启用（如目录已存在，请先确认内容避免覆盖个人修改）：

```bash
git clone https://github.com/threerocks/sweety-x-image-play.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/sweety-x-image-play"
```

## 平台支持边界与开源获取

截至 2026 年 11 月 13 日，X 时间线上已经可以见到 20 张图的原帖（例如 [Crain1Art](https://x.com/Crain1Art/status/2121009306233438440) 与 [ripped1taliano](https://x.com/ripped1taliano/status/2121044139705778359) 的帖子）；但 [X iOS 帮助页](https://help.x.com/en/using-x/x-ios-app) 与 [创建帖子 API 文档](https://docs.x.com/x-api/posts/create-post) 仍标明单帖图片上限为 4 张，[图片发布帮助](https://help.x.com/en/using-x/posting-gifs-and-pictures) 也未写明全量开放。本工具仅负责在本地出图与核验，**X 客户端实机发帖尚未验证**；发布前请先核对自己的账号权限，并可参照 [ALT 说明文档](https://help.x.com/en/using-x/add-image-descriptions) 为每张图标注序号与内容说明。

项目代码、文档与仓库示例均采用 MIT 协议开源，欢迎前往 [https://github.com/threerocks/sweety-x-image-play](https://github.com/threerocks/sweety-x-image-play) 获取或提交 Issue 反馈尺寸与配置问题。
