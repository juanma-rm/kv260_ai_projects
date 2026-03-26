#!/usr/bin/env python3
"""
Convert float neural network parameters to fixed-point quantized format.

Quantization specs are defined in the script for easy configuration.
Loads original float parameters and outputs quantized integer values.

Model structure:
  Input (2) → Linear(2→8) + ReLU → Linear(8→3) + Sigmoid → Output (3)
"""

import json
import argparse
from pathlib import Path


# ============================================================================
# USER-CONFIGURABLE QUANTIZATION SPECIFICATIONS
# ============================================================================
# Define quantization specs for each parameter layer
# Format: {'fracbits': <fractional_bits>, 'bitwidth': <total_bits>}

QUANT_SPECS = {
    'layer1_weights': {'fracbits': 3, 'bitwidth': 8},  # Q5.3 (for 8×2 weights)
    'layer1_bias':    {'fracbits': 4, 'bitwidth': 8},  # Q4.4 (for 8 biases)
    'layer2_weights': {'fracbits': 3, 'bitwidth': 8},  # Q5.3 (for 3×8 weights)
    'layer2_bias':    {'fracbits': 2, 'bitwidth': 8},  # Q6.2 (for 3 biases)
}

# Input/activation quantization (informational, not used in conversion)
ACTIVATION_SPECS = {
    'input':      {'fracbits': 6, 'bitwidth': 8},  # Q2.6 (input scaling)
    'relu_output': {'fracbits': 3, 'bitwidth': 8},  # Q5.3 (after ReLU)
    'dense_output': {'fracbits': -1, 'bitwidth': 8}, # Dynamic scale (before Sigmoid)
}

# ============================================================================


def quantize_value(value, fracbits, bitwidth=8):
    """
    Quantize a float value to fixed-point.
    
    Formula: quant_int = round(float_val * 2^fracbits)
    Then clamp to signed integer range: [-2^(bitwidth-1), 2^(bitwidth-1)-1]
    """
    if fracbits == -1:
        # Dynamic scale, return as-is
        return float(value)
    
    scale = 2 ** fracbits
    quant_int = round(value * scale)
    
    # Clamp to signed integer range
    min_val = -(2 ** (bitwidth - 1))
    max_val = (2 ** (bitwidth - 1)) - 1
    quant_int = max(min_val, min(max_val, quant_int))
    
    return float(quant_int) / scale


def quantize_array(data, fracbits, bitwidth=8):
    """Recursively quantize arrays (handles nested lists)"""
    if isinstance(data, list):
        if isinstance(data[0], list):
            # 2D array
            return [quantize_array(row, fracbits, bitwidth) for row in data]
        else:
            # 1D array
            return [quantize_value(v, fracbits, bitwidth) for v in data]
    else:
        return quantize_value(data, fracbits, bitwidth)


def main():
    parser = argparse.ArgumentParser(
        description='Convert float NN parameters to quantized fixed-point format'
    )
    parser.add_argument(
        'input_params',
        type=Path,
        help='Path to input float parameters JSON file (e.g., logic_ops_params.json)'
    )
    parser.add_argument(
        'output_file',
        type=Path,
        help='Path to output quantized parameters JSON file'
    )
    
    args = parser.parse_args()
    
    # Validate input file exists
    if not args.input_params.exists():
        print(f"Error: Input file not found: {args.input_params}")
        return 1
    
    # Create output directory if needed
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Loading float parameters from {args.input_params}")
    with open(args.input_params, 'r') as f:
        float_params = json.load(f)
    
    print("\n=== Quantization Specifications ===")
    for param_name, spec in QUANT_SPECS.items():
        print(f"{param_name}: {spec['bitwidth']}-bit Q{spec['bitwidth']-spec['fracbits']}.{spec['fracbits']}")
    
    # Generate quantized parameters matching model structure
    quantized_params = {
        "weights": [[], []],  # [layer1_weights, layer2_weights]
        "biases": [[], []],   # [layer1_bias, layer2_bias]
        "quant_specs": QUANT_SPECS.copy()
    }
    
    print("\n=== Quantizing Parameters ===\n")
    
    # Layer 1 weights: shape (8, 2)
    spec = QUANT_SPECS['layer1_weights']
    print(f"Layer 1 Weights (8×2): Q{spec['bitwidth']-spec['fracbits']}.{spec['fracbits']}")
    layer1_weights_quantized = quantize_array(
        float_params['weights'][0], 
        spec['fracbits'],
        spec['bitwidth']
    )
    quantized_params['weights'][0] = layer1_weights_quantized
    print(f"  ✓ Shape: {len(layer1_weights_quantized)}×{len(layer1_weights_quantized[0])}")
    
    # Layer 1 bias: shape (8,)
    spec = QUANT_SPECS['layer1_bias']
    print(f"Layer 1 Bias (8,): Q{spec['bitwidth']-spec['fracbits']}.{spec['fracbits']}")
    layer1_bias_quantized = quantize_array(
        float_params['biases'][0],
        spec['fracbits'],
        spec['bitwidth']
    )
    quantized_params['biases'][0] = layer1_bias_quantized
    print(f"  ✓ Length: {len(layer1_bias_quantized)}")
    
    # Layer 2 weights: shape (3, 8)
    spec = QUANT_SPECS['layer2_weights']
    print(f"Layer 2 Weights (3×8): Q{spec['bitwidth']-spec['fracbits']}.{spec['fracbits']}")
    layer2_weights_quantized = quantize_array(
        float_params['weights'][1],
        spec['fracbits'],
        spec['bitwidth']
    )
    quantized_params['weights'][1] = layer2_weights_quantized
    print(f"  ✓ Shape: {len(layer2_weights_quantized)}×{len(layer2_weights_quantized[0])}")
    
    # Layer 2 bias: shape (3,)
    spec = QUANT_SPECS['layer2_bias']
    print(f"Layer 2 Bias (3,): Q{spec['bitwidth']-spec['fracbits']}.{spec['fracbits']}")
    layer2_bias_quantized = quantize_array(
        float_params['biases'][1],
        spec['fracbits'],
        spec['bitwidth']
    )
    quantized_params['biases'][1] = layer2_bias_quantized
    print(f"  ✓ Length: {len(layer2_bias_quantized)}")
    
    # Save output
    print(f"\nSaving to {args.output_file}")
    with open(args.output_file, 'w') as f:
        json.dump(quantized_params, f, indent=4)
    
    print("✓ Quantization complete!")
    
    return 0


if __name__ == '__main__':
    exit(main())
