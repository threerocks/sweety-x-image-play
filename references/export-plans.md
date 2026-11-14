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

## 主体出框

```json
{
  "mode": "breakout",
  "source": "original.png",
  "foreground_mask": "subject-mask.png",
  "count": 5,
  "bar_width": 80,
  "gap_width": 8,
  "corner_radius": 12
}
```

数值仅为示例，应根据原图确定。原图与蒙版严格同尺寸；无裁剪、缩放或重绘。白色蒙版保护前景，黑色区域接受透明条缝，灰色可柔化边缘。源图已有透明度也会保留。

省略 `widths` 时自动根据蒙版横向范围安排宽主体附件与左右窄片，主图位置随主体而变。可选 `subject_padding`（非负像素）、`min_panel_width`（正像素）控制余量与外围最小宽度。布局空间不足会失败，不能强行凑 20 张。没有指定 count 时默认 5，作者仍需先按构图决定数量。

手动布局可写 `widths: [53, 64, 62, 510, 47]`（仅为 736 像素母图示例，不能照抄到其他图）。长度须等于 count，总和须等于原图宽；所有实际切口必须避开蒙版覆盖的整个横向跨度。不要写旧模式的 `width`；`height` 可省略，填写时必须等于原图高度。只支持 `fit: exact`。

此模式的 manifest 使用 schema_version 2、`width: null` 和逐张 `widths`；其他模式维持旧格式。记录前景范围、白色保护区域像素检查和透明像素数；重组必须等于合成后的母图。PNG 可同时适应浅/深背景，preview.html 提供三种底色切换；这不证明 X 客户端一定按相同比例排列。

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
