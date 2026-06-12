import numpy as np

def apply_decorrelation(signal, strength, sample_rate):
    """Apply decorrelation to create diffuse sound without obvious echoes"""
    if strength <= 0 or signal.size == 0:
        return signal
    
    # Simple all-pass filter with different delays for LB and RB
    delay_samples_lb = int(0.012 * sample_rate)  # 12ms for LB
    delay_samples_rb = int(0.016 * sample_rate)  # 16ms for RB
    
    # Ensure we don't exceed signal length
    delay_samples_lb = min(delay_samples_lb, len(signal) - 1)
    delay_samples_rb = min(delay_samples_rb, len(signal) - 1)
    
    # Create decorrelated versions for LB and RB
    lb_signal = np.zeros_like(signal)
    rb_signal = np.zeros_like(signal)
    
    # All-pass filter with different delays for LB and RB
    feedback = 0.7 * strength
    
    for i in range(len(signal)):
        if i >= delay_samples_lb:
            lb_signal[i] = signal[i] * 0.5 + lb_signal[i - delay_samples_lb] * feedback
        else:
            lb_signal[i] = signal[i] * 0.5
            
        if i >= delay_samples_rb:
            rb_signal[i] = signal[i] * 0.5 + rb_signal[i - delay_samples_rb] * feedback
        else:
            rb_signal[i] = signal[i] * 0.5
    
    # Combine LB and RB signals with some cross-talk for diffusion
    combined = np.zeros_like(signal)
    combined[:-max(delay_samples_lb, delay_samples_rb)] = (
        lb_signal[delay_samples_lb:] + 
        rb_signal[delay_samples_rb:]
    ) * 0.7
    
    return combined