"""Central configuration for folder-based spatializer runs.

只需要改这个文件即可控制：
- input audio 文件夹位置
- 处理单首歌还是整个文件夹
- 输出 4ch / binaural / both
- binaural 是否额外导出 front/rear pair
- preset 模式：manual / auto_select / auto_acoustic
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_AUDIO_DIR = BASE_DIR / "input_audio"
OUTPUT_DIR = BASE_DIR / "outputs"

# "single"：只处理 SINGLE_INPUT_FILENAME；"all"：处理 input_audio 里全部支持格式。
PROCESS_MODE = "all"  # "single" / "all"
SINGLE_INPUT_FILENAME = "test_input.wav"

TARGET_SR = 48000
ANALYSIS_SECONDS = 2.0

# 输出模式："4ch" / "binaural" / "both"
#OUTPUT_MODE = "binaural"
OUTPUT_MODE = "4ch"
# binaural 主输出是 4.0 虚拟扬声器耳机监听。
# CTC 输出会把 binaural 双耳目标反解到 4ch 音响阵列，适合在真实 4.0 扬声器上试听耳机空间感。
# front/rear pair 默认 False：需要检查前场/后场定位时再打开。
EXPORT_BINAURAL_CROSSTALK_CANCELLED_4CH = True
EXPORT_BINAURAL_FRONT_PAIR = False
EXPORT_BINAURAL_REAR_PAIR = False

# preset 工作模式：
# - manual：使用 MANUAL_PRESET
# - auto_select：根据 analysis 选择已有 preset
# - auto_acoustic：根据 analysis 动态生成当前歌曲专属 preset

#PRESET_MODE = "manual"
PRESET_MODE = "auto_acoustic"
#PRESET_MODE = "auto_select"

MANUAL_PRESET = "wide_smooth"

# 如果 auto_acoustic 后方音响偏不显著，可以改 True 启用 presets.py 里的安全预备方案。
AUTO_ACOUSTIC_REAR_ENHANCEMENT = True

# binaural 监听设置。rear gain 只影响耳机监听文件，不改变 4ch master。
BINAURAL_FRONT_AZIMUTH_DEG = 30.0
BINAURAL_REAR_AZIMUTH_DEG = 135.0
BINAURAL_FULL_REAR_GAIN_DB = 1.5

# Crosstalk cancellation inverse-filter settings. 越低越激进、定位更强但更容易染色/爆峰；
# 越高越稳、更像温和 speaker virtualization。
CTC_REGULARIZATION = 0.08
CTC_IR_LENGTH_SAMPLES = 4096
CTC_PEAK_TARGET = 0.98

# 四个虚拟扬声器到听音者的距离（米），用于 1/r 能量衰减和高频空气吸收。
# 参考距离处 gain=1.0；更远则更轻且高频被空气吸收更明显。
# 设为 None 则关闭该对扬声器的距离模拟。
SPEAKER_DISTANCE_FRONT_M = 1.2
SPEAKER_DISTANCE_REAR_M = 0.95
SPEAKER_DISTANCE_REFERENCE_M = 1.0
# 高频空气吸收系数 (dB/m @ 8kHz)。温和值约 0.5 dB/m；设为 0 关闭。
SPEAKER_AIR_ABSORPTION_DB_PER_M = 0.5

EXPORT_DIAGNOSTICS = True

# ---- Room RIR (post-binaural stereo-matrix convolution) ----
# 在 binaural 输出之后额外卷积一个合成小房间 RIR，增强外化感/前后定位。
# 不是真正的 per-speaker BRIR，但对耳机监听有明显帮助。
EXPORT_BINAURAL_ROOM_RIR = True
ROOM_RIR_RT60_SECONDS = 0.30
ROOM_RIR_LENGTH_SECONDS = 0.50
ROOM_RIR_LATE_START_SECONDS = 0.03
ROOM_RIR_RANDOM_SEED = 20260611
ROOM_RIR_KEEP_TAIL = True


def ensure_directories():
    INPUT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
