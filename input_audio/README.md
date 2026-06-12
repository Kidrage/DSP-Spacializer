# input_audio

把要处理的音频文件放在这个文件夹里。

支持格式取决于本机解码依赖，代码会尝试读取：`.wav`, `.flac`, `.aiff`, `.aif`, `.ogg`, `.mp3`, `.m4a`。

在 `config_center.py` 中：
- `PROCESS_MODE = "all"`：处理本文件夹里所有支持的音频文件。
- `PROCESS_MODE = "single"`：只处理 `SINGLE_INPUT_FILENAME` 指定的一首歌。
