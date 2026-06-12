import json
import numpy as np

def generate_diagnostics(input_file, sample_rate, duration, analysis, preset, output_audio, output_file=None):
    """
    Generate diagnostic information about the spatialization process
    
    Args:
        input_file: Path to input audio file
        sample_rate: Audio sample rate
        duration: Audio duration in seconds
        analysis: Dictionary containing analysis features
        preset: Name of the preset used
        output_audio: 4-channel output audio array [LF, RF, LB, RB]
        output_file: Path to output audio file (optional)
    
    Returns:
        Dictionary containing diagnostics
    """
    # Calculate output statistics
    output_peak = float(np.max(np.abs(output_audio)))
    front_energy = np.mean(output_audio[:, 0]**2 + output_audio[:, 1]**2)
    rear_energy = np.mean(output_audio[:, 2]**2 + output_audio[:, 3]**2)
    total_energy = front_energy + rear_energy
    
    diagnostics = {
        "input_file": input_file,
        "sample_rate": int(sample_rate),
        "duration_seconds": float(duration),
        "analysis": {
            "stereo_width": float(analysis["stereo_width"]),
            "center_dominance": float(analysis["center_dominance"]),
            "bass_mono_ratio": float(analysis["bass_mono_ratio"]),
            "high_diffuse_ratio": float(analysis["high_diffuse_ratio"]),
            "transient_density": float(analysis["transient_density"]),
            "suggested_preset": analysis["suggested_preset"]
        },
        "preset": preset,
        "output": {
            "front_energy_ratio": float(front_energy / total_energy if total_energy > 0 else 0),
            "rear_energy_ratio": float(rear_energy / total_energy if total_energy > 0 else 0),
            "peak": float(output_peak),
            "clipped_samples": int(np.sum(np.abs(output_audio) >= 1.0))
        }
    }
    
    if output_file:
        diagnostics["output_file"] = output_file
    
    return diagnostics

def save_diagnostics(diagnostics, file_path):
    """
    Save diagnostics to a JSON file
    
    Args:
        diagnostics: Dictionary containing diagnostics
        file_path: Path to save the JSON file
    """
    with open(file_path, 'w') as f:
        json.dump(diagnostics, f, indent=2)