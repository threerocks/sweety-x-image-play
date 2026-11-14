# 导出方案与命令

Python 3.9+ 标准库 + ImageMagick 7。通过 PATH 找 `magick`，或设置 `MAGICK_BIN` 为它的绝对路径。没有时报告缺少依赖，不自动安装。源图路径相对 plan.json 所在目录解析；不支持远程地址。成品目录必须不存在。

## 独立窄条

```json
{
  "mode": "independent",
  "count": 4,
  "width": 40,
  "height": 1920,
  "assets": [
    {"source": "cream.png", "crop": [382, 0, 152, 1717], "stretch_band": [430, 1287]},
    {"source": "pink.png", "crop": [382, 0, 152, 1717], "stretch_band": [430, 1287]},
    {"source": "mint.png", "crop": [382, 0, 152, 1717], "stretch_band": [430, 1287]},
    {"source": "blue.png", "crop": [382, 0, 152, 1717], "stretch_band": [430, 1287]}
  ]
}
```

crop 是 `[left, top, width, height]`；上面坐标只是 916×1717 样本示例，不适用于任意新图。stretch_band 是裁切后源图的 `[start_y, end_y)`，仅拉伸该段，上下段等比缩放到指定宽度。没有 stretch_band 时按 fit 等比处理（默认 exact，尺寸不符就失败）。黑白/浅色主体慎用自动背景裁切；本脚本要求显式 crop，不自动猜主体。

## 连续切片

```json
{
  "mode": "panorama",
  "count": 20,
  "width": 140,
  "height": 2048,
  "source": "master.png",
  "fit": "exact"
}
```

exact 要求母图为 2800×2048。`contain` 等比完整保留并补背景，可能产生空白切片；`cover` 等比填满并居中裁剪，可能丢失边缘内容。两者均需目视确认；禁止凭默认值掩盖裁剪。背景默认 white，可设置 `background`。

切片不重叠、不跳列。工具将切片重组，与准备后的母图做像素摘要比较；相等才通过。图片之间不主动添加缝隙。

## 横滑揭晓

```json
{
  "mode": "reveal",
  "count": 20,
  "width": 780,
  "height": 1200,
  "head": "start.png",
  "bridge": "middle.png",
  "tail": "end.png",
  "fit": "exact"
}
```

首尾各一张，中段重复 18 次。不想重复时用 `assets` 替换 head/bridge/tail，数组长度必须等于 count；每项是源图路径或 `{ "source": "...", "crop": [...] }`。所有帧最终同尺寸。工具记录相邻图边缘误差，无法保证故事节奏或自动对齐细线。

## 贯穿线与传统主体出框

贯穿线要求：先准备整幅全高线母图，再用 `panorama` 方案，设置 count=20、width=80、height=母图实际高度、fit=exact。主角或标题不能在之后盖住竖线；贯穿线的视觉检查独立于重组检查。

以下 `breakout` 方案仅用于用户显式选择的传统局部出框。该合成器会用主体蒙版覆盖条缝，不能用于当前默认的贯穿线效果。

默认方案（先将母图和蒙版等比准备到 1600 px 总宽）：

```json
{
  "mode": "breakout",
  "layout": "uniform",
  "source": "prepared-original.png",
  "foreground_mask": "prepared-mask.png",
  "count": 20,
  "width": 80,
  "bar_width": 72,
  "gap_width": 8,
  "corner_radius": 12
}
```

`count` 默认 20，`width` 默认 80，可按用户要求修改。总宽必须恰好等于 count × width；源图与蒙版必须同尺寸。脚本不会静默缩放、裁边、拉伸各片或将余数分给最后一片。`height` 可省略，填写时须与准备后的母图相同；仅支持 `fit: exact`。先准备整张母图与蒙版，例如原图按 1600 px 宽等比缩放，再将蒙版配准到相同宽高；像素保留检查相对于准备后的母图，不能据此声称与未缩放原图逐像素相同。

白色保留目标，黑色允许图内透明条缝，灰色用于边缘过渡。目标选择必须先通过语义检查：手握石头不意味着把手并入石头。需要保护文字时先单独验收主角蒙版，再合并独立的文字保护层用于导出。

默认背景条框与附件同为 80 px 节距，72 px 图像条 + 8 px 透明缝；整套使用统一条宽、间距与圆角。生成模型不负责保证最终像素尺寸。

`uniform` 允许等宽切口穿过目标，并在 `breakout.subject_cut_positions` 记录位于目标横向范围内的切口（保守范围，不是逐行语义判定）。这不改变文件重组结果，但 X 的真实附件间距仍可分隔主体。若用户要求真实切口不得穿过目标，设置 `allow_subject_cuts: false`；冲突时停止，不自动回退到不等宽。

### 历史不等宽选项

只有用户明确选用时才设置 `layout: adaptive`。省略 widths 时按蒙版范围安排宽主图与外围窄片；可用 `subject_padding`、`min_panel_width` 调整。也可显式传入各张 widths；长度须等于 count，总和须等于母图宽。此布局不接受 width，默认不允许切口穿过目标范围。旧方案需补上 `layout: adaptive` 和原 count 才能按原方式复现。

breakout 清单使用 schema_version 2 和逐张 widths；uniform 的 width 为单张实际宽度，adaptive 的 width 为 null。重组必须等于合成母图；preview.html 支持浅色、黑色、深蓝背景。所有检查均不代表目标 X 客户端发布效果已验证。

## 交付检查

```bash
python3 scripts/export_images.py build plan.json --out final-set
# 读取并运行 sweety-image-privacy，input 指向 final-set/images，--json 输出保存到 privacy-report.json
python3 scripts/export_images.py finalize final-set --privacy-report privacy-report.json
python3 scripts/export_images.py audit final-set
```

build 后 privacy_skill 为 pending，不能报告完整隐私流程通过。finalize 验证隐私报告覆盖本套每个文件，且没有 GPS、来源 EXIF、必清理来源扩展属性；可如实记录 macOS provenance 残留。它随后重新 strip 元数据、更新摘要、生成 ZIP 和预览，并检查包内图片与单图字节一致。若像素已经改变，应重新 build 新版本，不用 finalize 重新认可改图。

`audit` 遇到缺图、多图、尺寸错误、顺序清单错误、摘要错误、嵌入来源元数据、压缩包缺文件/内容不一致时以非零状态退出。正常 JSON 的 `file_checks_passed` 只代表文件检查；`privacy_workflow_complete` 单列，`x_client_verified` 永远不会由本地脚本自动设为 true。

本地 preview.html 可离线打开，显示各图真实尺寸、单张下载链接、横滑预览和间距调节。单图路径是 images/01.png 起；上传顺序按两位序号，不能依赖文件管理器的修改时间排序。
