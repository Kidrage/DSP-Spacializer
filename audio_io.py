"""Audio I/O helpers.

The original repository only loaded WAV via soundfile. The notebook workflow
supports practical music-file testing, so this module now accepts common audio
formats from the configured ``input_audio`` folder. Loading tries soundfile
first and falls back to librosa/audioread for formats such as MP3 when the
local environment supports them.
"""

import math
from pathlib import Path

import numpy as np
from scipy import signal

from dsp_utils import normalize_peak

SUPPORTED_AUDIO_EXTENSIONS = (".wav", ".flac", ".aiff", ".aif", ".ogg", ".mp3", ".m4a")


def load_audio(file_path, target_sr=None):
    """Load audio as stereo float32.

    Args:
        file_path: Input audio path.
        target_sr: Optional target sample-rate. If set, resample with
            ``scipy.signal.resample_poly``.

    Returns:
        ``(left, right, sample_rate)``.
    """
    path = Path(file_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    sf_error = None
    librosa_error = None

    try:
        import soundfile as sf

        audio, sample_rate = sf.read(str(path), always_2d=True, dtype="float32")
        if audio.shape[1] == 1:
            audio = np.repeat(audio, 2, axis=1)
        elif audio.shape[1] > 2:
            audio = audio[:, :2]
    except Exception as err:
        sf_error = err
        try:
            import librosa

            y, sample_rate = librosa.load(str(path), sr=None, mono=False)
            if y.ndim == 1:
                audio = np.stack([y, y], axis=1).astype(np.float32)
            elif y.shape[0] == 1:
                audio = np.repeat(y, 2, axis=0).T.astype(np.float32)
            else:
                audio = y[:2, :].T.astype(np.float32)
        except Exception as err2:
            librosa_error = err2
            raise RuntimeError(
                "Could not load audio. Install soundfile/librosa/audioread and, "
                "for MP3 on macOS, ffmpeg if needed.\n"
                f"soundfile error: {sf_error}\nlibrosa error: {librosa_error}"
            ) from err2

    if target_sr is not None and int(sample_rate) != int(target_sr):
        g = math.gcd(int(sample_rate), int(target_sr))
        up = int(target_sr) // g
        down = int(sample_rate) // g
        audio = signal.resample_poly(audio, up, down, axis=0).astype(np.float32)
        sample_rate = int(target_sr)

    audio = normalize_peak(audio.astype(np.float32), 0.99)
    return audio[:, 0], audio[:, 1], int(sample_rate)


def export_audio(file_path, audio, sample_rate):
    """Export mono/stereo/4-channel float WAV."""
    import soundfile as sf

    path = Path(file_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.asarray(audio, dtype=np.float32), int(sample_rate), subtype="FLOAT")
    return path


def discover_audio_files(input_dir):
    """Return all supported audio files inside ``input_dir`` sorted by name."""
    root = Path(input_dir).expanduser()
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
    return sorted(
        p for p in root.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
    )