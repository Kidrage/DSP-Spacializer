import numpy as np

def apply_limiter(audio, threshold=0.98, release_time=0.1, sample_rate=48000):
    """
    Apply a simple peak limiter to prevent clipping
    
    Args:
        audio: 4-channel audio array [LF, RF, LB, RB]
        threshold: Peak threshold level
        release_time: Release time in seconds
        sample_rate: Audio sample rate
    
    Returns:
        Limited audio
    """
    del release_time, sample_rate
    audio = np.asarray(audio, dtype=np.float32)
    p = float(np.max(np.abs(audio)) + 1e-9)
    if p <= threshold:
        return audio.astype(np.float32)
    return (audio * (threshold / p)).astype(np.float32)