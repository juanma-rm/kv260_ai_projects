# Introduction

This project implements a neural network that simultaneously predicts the results of AND, OR and XOR logic operations for 2-bit binary inputs.

# Flavors

There are several versions:
- Standard (baseline):
  - Workflow: Pytorch for training, ONNX for inference
  - Target devices: workstation CPU, workstation GPU, KV260 CPU
- DPU (Quantized):
  - Workflow: Pytorch for training, Vitis AI for quantization / optimization, ONNX for inference
  - Target devices: workstation CPU, workstation GPU, KV260 CPU, KV260 PL (DPU)
- Custom PL:
  - Workflow: NN directly coded in RTL (SystemVerilog) or Vitis HLS, custom deploy on PL (interaction via Pynq/XRT?)
  - Target devices: KV260 PL

# AI architecture

MLP (Multi-Layer Perceptron):
- Input layer: 2 neurons (for 2-bit binary inputs)
- Hidden layer: 4 neurons with ReLU activation
- Output layer: 3 neurons with Sigmoid activation (for AND, OR, XOR predictions). Range: [0, 1] for each logic operation

Diagram:

![Logic Ops Standard Architecture](pics/logic_ops_standard_arch.png)

# Hardware setup

See [README in main branch](https://github.com/juanma-rm/kv260_ai_projects/blob/main/README.md)

# General setup

For Windows PowerShell: enable execution policy:
```PowerShell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Create and activate virtual environment:
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependency modules:
```
pip install torch
pip install numpy
pip install matplotlib
pip install seaborn
pip install onnx
pip install onnxruntime
```

Install Blackwell-ready PyTorch:
```
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# Verify Pytorch installation and GPU detection
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()} | Device: {torch.cuda.get_device_name(0)}')"

# Expected output:
CUDA available: True | Device: NVIDIA GeForce RTX 5070 Ti
```

Install Jupyter and the IPyKernel bridge:
```
pip install jupyter ipykernel

# Add your venv as a selectable kernel in Jupyter
# This creates a "Python (AI-FPGA)" option in the Jupyter menu
python -m ipykernel install --user --name=ai_fpga --display-name "Python (AI-FPGA)"

# Launch Jupyter Lab
jupyter lab
```

# Results

Notes:
- Dataset: 100000 samples
- Iterations per Batch Size: 20000
- Data is continually wrapped around a 100000-sample pool.
- Latency is measured for each batch, not per sample.

## Standard. Workstation: CPU

| Batch Size | Accuracy | Throughput (ksamp/s) | Latency Mean (ms) | Latency Min (ms) | Latency Median (ms) | Latency p95 (ms) | Latency p99 (ms) | Latency Max (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 100.00% | 152.10 | 0.0066 | 0.0056 | 0.0061 | 0.0066 | 0.0092 | 0.3999 |
| 8 | 100.00% | 1321.75 | 0.0061 | 0.0057 | 0.0059 | 0.0060 | 0.0082 | 0.3641 |
| 64 | 100.00% | 9920.90 | 0.0065 | 0.0060 | 0.0063 | 0.0070 | 0.0098 | 0.0543 |
| 512 | 100.00% | 59877.40 | 0.0086 | 0.0079 | 0.0082 | 0.0090 | 0.0122 | 0.4523 |
| 2048 | 100.00% | 133558.28 | 0.0153 | 0.0143 | 0.0149 | 0.0171 | 0.0204 | 0.4592 |
| 16384 | 100.00% | 271893.11 | 0.0603 | 0.0518 | 0.0570 | 0.0818 | 0.1011 | 0.6132 |


## Standard. Workstation: GPU

| Batch Size | Accuracy | Throughput (ksamp/s) | Mean (ms) | Min (ms) | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 100.00% | 155.39 | 0.0064 | 0.0057 | 0.0059 | 0.0087 | 0.0105 | 0.1980 |
| 8 | 100.00% | 1325.21 | 0.0060 | 0.0057 | 0.0059 | 0.0061 | 0.0085 | 0.2490 |
| 64 | 100.00% | 10161.38 | 0.0063 | 0.0060 | 0.0062 | 0.0064 | 0.0082 | 0.1248 |
| 512 | 100.00% | 61941.04 | 0.0083 | 0.0077 | 0.0081 | 0.0084 | 0.0118 | 0.1455 |
| 2048 | 100.00% | 138045.58 | 0.0148 | 0.0136 | 0.0145 | 0.0158 | 0.0243 | 0.1135 |
| 16384 | 100.00% | 280483.71 | 0.0584 | 0.0489 | 0.0553 | 0.0784 | 0.1090 | 0.6468 |

## Standard. KV260: CPU

| Batch Size | Accuracy | Throughput (ksamp/s) | Latency Mean (ms) | Latency Min (ms) | Latency Median (ms) | Latency p95 (ms) | Latency p99 (ms) | Latency Max (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 100.00% | 8.20 | 0.1219 | 0.0928 | 0.1154 | 0.1352 | 0.1463 | 14.9923 |
| 8 | 100.00% | 83.82 | 0.0954 | 0.0933 | 0.0948 | 0.0959 | 0.1093 | 1.0305 |
| 64 | 100.00% | 610.80 | 0.1048 | 0.1025 | 0.1040 | 0.1055 | 0.1193 | 1.0031 |
| 512 | 100.00% | 2968.09 | 0.1725 | 0.1668 | 0.1690 | 0.2070 | 0.2268 | 1.1082 |
| 2048 | 100.00% | 4850.88 | 0.4222 | 0.3927 | 0.4037 | 0.5082 | 0.5290 | 0.8698 |
| 16384 | 100.00% | 6886.35 | 2.3792 | 2.0145 | 2.4360 | 2.5079 | 3.4191 | 34.5714 |

