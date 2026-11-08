# 东方明珠塔（程序化建模）

在 Blender 中用 bpy 脚本从零程序化建模的上海东方明珠广播电视塔（Oriental Pearl Tower）。几何、材质、灯光和天空都由代码生成，没有使用任何外部模型、素材或贴图。

## 重新建模和重新渲染

使用 Blender 5.2.3 LTS。脚本把渲染设为 Eevee（`BLENDER_EEVEE`）、1920×1080、24 fps、第 1 帧到第 240 帧（约 10 秒），静帧为 PNG，视频为 H.264 MP4。

在项目目录 `E:\Work\2026-11-08-oriental-pearl-blender\2026-11-08-project` 中执行：

```
E:\Tools\Blender\blender.exe -b -P build_oriental_pearl.py
```

这是本项目实际使用的命令：后台无界面，不附加额外参数。脚本默认完成全部流程：重建场景、保存 `oriental_pearl.blend`、写出第 1、120、240 帧静帧，再编码 `oriental_pearl.mp4`。

## 使用的模型

Cursor CLI，Grok 4.7 xhigh。

## 文件清单

- `build_oriental_pearl.py`：程序化建模、布光、环绕镜头，并渲染静帧与 MP4 的 bpy 脚本。
- `verify_outputs.py`：在没有 ffprobe 时读取 PNG 与 MP4 元数据，核对分辨率、时长、帧率和 H.264。
- `oriental_pearl.blend`：脚本保存的 Blender 工程。
- `oriental_pearl.mp4`：1920×1080、24 fps、240 帧的 H.264 环绕展示视频。
- `frame_0001.png`：第 1 帧静帧，环绕起点。
- `frame_0120.png`：第 120 帧静帧，大约转到对面。
- `frame_0240.png`：第 240 帧静帧，转满一圈后回到与第 1 帧相同的视角。
- `render_log.txt`：建模与渲染的计时和运行记录。
- `README.md`：本说明文件。
- `index.html`：用相对路径嵌入视频和三张静帧的静态展示页。
