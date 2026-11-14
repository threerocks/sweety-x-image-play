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

## 主体出框：混合等宽视觉栏

```json
{
  "mode": "breakout",
  "layout": "hybrid",
  "source": "prepared-original.png",
  "foreground_mask": "subject-mask.png",
  "column_count": 20,
  "column_width": 80,
  "gap_width": 8,
  "corner_radius": 12
}
```

先将母图与主角蒙版按同一尺度准备到 `column_count * column_width + (column_count - 1) * gap_width`，此例为 1752 px 宽。工具严格要求同尺寸，不自动缩放。height 省略则使用母图高度。

hybrid 为 breakout 默认布局。它将覆盖主角横向范围的最少连续整栏合为一个宽附件，其余栏分别导出为窄附件。`subject_padding` 可设置额外保护范围，默认 0。主图宽度包括内部模拟缝；外围窄图不包含真实附件间距。主角范围不穿过任何真实边界。只有一个附件或超过 20 个附件时明确失败，不通过切开主体迁就数量。

`column_count` 是视觉栏数，`count` 是推导出的实际附件数。通常省略 count；若指定，必须与推导值一致。不要传 width / widths / bar_width 自行覆盖该网格。默认 20 个视觉栏不保证 20 个附件。最多 20 个附件与视觉栏数是两个不同约束。

manifest 中的 breakout 报告包含 column_count、column_width、main_columns（从 0 开始）、main_attachment（从 1 开始）、crop_ranges（源图起点与裁切宽度）、source_width。重组检查把省去的真实间距还原为同宽透明缝，并比较可见 RGB 与 Alpha；全透明像素隐藏的 RGB 不参与此判断。上传文件本身不包含这些额外间距。

preview.html 初始间距按当前显示高度与 gap_width 的比例换算，主图和窄图同高等比显示。实际 X 的间距与缩放必须另行核对。零间距拼图不能作为本模式验收结果。

### 兼容旧方案

`layout: uniform` 将每个附件切成相同像素宽，允许真实切口穿过主体，只用于明确要求等宽文件的其他实验。`layout: adaptive` 是按主体范围自由分配侧边宽度的旧模式。两者保留兼容，但不满足当前默认的真假栏统一网格要求。

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
