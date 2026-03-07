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
- Hidden layer: 8 neurons with ReLU activation
- Output layer: 3 neurons with Sigmoid activation (for AND, OR, XOR predictions). Range: [0, 1] for each logic operation

Diagram:

![Logic Ops Standard Architecture](pics/logic_ops_standard_arch.png)

# Hardware setup

See [README in main branch](https://github.com/juanma-rm/kv260_ai_projects/blob/main/README.md)

# General setup

## Development machine (workstation)

Create and activate virtual environment:
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependency modules:
```bash
pip install torch
pip install numpy
pip install matplotlib
pip install seaborn
pip install onnx
pip install onnxruntime
```

Install PyTorch:
```bash
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# Verify Pytorch installation and GPU detection
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()} | Device: {torch.cuda.get_device_name(0)}')"

# Expected output:
CUDA available: True | Device: NVIDIA GeForce RTX 5070 Ti
```

Install Jupyter and the IPyKernel bridge:
```bash
pip install jupyter ipykernel

# Add your venv as a selectable kernel in Jupyter
# This creates a "Python (AI-FPGA)" option in the Jupyter menu
python -m ipykernel install --user --name=ai_fpga --display-name "Python (AI-FPGA)"

# Launch Jupyter Lab
jupyter lab
```

Vitis AI (install, quantize, compile):
```bash
# Clone Vitis AI repository
git clone https://github.com/Xilinx/Vitis-AI.git
cd Vitis-AI

# Pull and Run the Docker Image:
# For CPU-only host
./docker_run.sh xilinx/vitis-ai-pytorch-gpu:latest
# For GPU-enabled host (recommended for faster quantization/training)
./docker_run.sh xilinx/vitis-ai-pytorch-cpu:latest

# Once inside the container, activate the PyTorch conda environment:
vitis-ai-user@docker-desktop:/workspace$ conda activate vitis-ai-pytorch

# Navigate to the DPU directory (ensure it is available from the container)
(vitis-ai-pytorch) vitis-ai-user@docker-desktop:/workspace$ cd sw/dpu

# Quantize
(vitis-ai-pytorch) vitis-ai-user@docker-desktop:/workspace$ python quantize_model.py

# Compile for KV260 DPU
(vitis-ai-pytorch) vitis-ai-user@docker-desktop:/workspace$ vai_c_xir -x quantize_result/LogicNet_int.xmodel \
          -a /opt/vitis_ai/compiler/arch/DPUCZDX8G/KV260/arch.json \
          -o ./compiled_model \
          -n logic_net_dpu
```

## KV260 board

Install dependency modules:

```bash
pip install torch
pip install numpy
pip install matplotlib
pip install seaborn
pip install onnx
pip install onnxruntime
```

Install PYNQ framework:

```bash
git clone https://github.com/Xilinx/Kria-PYNQ.git
cd Kria-PYNQ/
sudo bash install.sh -b KV260
```

# Usage

## Standard

```
cd sw\standard

# Train:
# Run notebook logic_ops_train.ipynb

# Inference
python logic_ops_inference.py --device CPU
python logic_ops_inference.py --device GPU
```

## DPU (Quantized)

Requirements in the kv260 board:
- Bitsream with DPU
- Compiled model (sw/dpu/compiled_model/logic_net_dpu.xmodel)
- Python file to interact with the DPU and run the inference (sw/dpu/logic_ops_inference_dpu.py)

A bitstream with a DPU instantiated is required, and it must match the dpu target used in the compilation process (we’re targeting kv260 dpu used by vitis ai 3.5). 
- Option 1: take bitbin, dtbo and json files from this repository (from output/artifacts or generate them). Then, copy them to the kv260 board, under /lib/firmware/xilinx/ and load them with xmutil
- Option 2: take files .bit, .xclbin and .hwh can be taken from pynq-dpu repository: https://github.com/Xilinx/DPU-PYNQ/tree/master/pynq_dpu
  - https://www.xilinx.com/bin/public/openDownload?filename=pynqdpu.dpu.kv260_som.3.5.0.bit
  - https://www.xilinx.com/bin/public/openDownload?filename=pynqdpu.dpu.kv260_som.3.5.0.hwh
  - https://www.xilinx.com/bin/public/openDownload?filename=pynqdpu.dpu.kv260_som.3.5.0.xclbin
- Option 3. Install pynq on kv260 and copy dpu.bit/xclbin/hwh files from: `/usr/local/share/pynq-venv/lib/python3.10/site-packages/pynq_dpu/dpu.*`

Note: files for options 2/3 can be found under `output\artifacts\pynqdpu.dpu.kv260_som.3.5.0` for convenience.

For running the bitstream in the kv260 board:
- Use xmutil to load the bitstream, dtbo and json files (option 1)
```bash
sudo xmutil unloadapp
sudo xmutil loadapp dpu
```
- Use pynq overlay module to load the bit/xclbin/hwh files (option 2 or 3). Assuming they are in /home/ubuntu/:
```python
# Add this to your logic_ops_inference_dpu.py script
from pynq import Overlay
overlay = Overlay("dpu.bit")
```

Run the inference from the kv260:

```bash
sudo su
export XLNX_VART_FIRMWARE=/home/ubuntu/dpu.xclbin
source /etc/profile.d/pynq_venv.sh
python3 logic_ops_inference_dpu.py
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
| 1 | 100.00% | 168.80 | 0.0059 | 0.0055 | 0.0058 | 0.0074 | 0.0080 | 0.1982 |
| 8 | 100.00% | 1351.96 | 0.0059 | 0.0057 | 0.0058 | 0.0060 | 0.0081 | 0.0720 |
| 64 | 100.00% | 10093.75 | 0.0063 | 0.0060 | 0.0062 | 0.0065 | 0.0088 | 0.0713 |
| 512 | 100.00% | 57260.83 | 0.0089 | 0.0084 | 0.0087 | 0.0094 | 0.0122 | 0.1078 |
| 2048 | 100.00% | 113958.31 | 0.0180 | 0.0169 | 0.0174 | 0.0193 | 0.0309 | 0.1177 |
| 16384 | 100.00% | 233064.39 | 0.0703 | 0.0560 | 0.0639 | 0.0968 | 0.1212 | 0.9619 |

## Standard. Workstation: GPU

| Batch Size | Accuracy | Throughput (ksamp/s) | Latency Mean (ms) | Latency Min (ms) | Latency Median (ms) | Latency p95 (ms) | Latency p99 (ms) | Latency Max (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 100.00% | 168.13 | 0.0059 | 0.0057 | 0.0058 | 0.0060 | 0.0082 | 0.2007 |
| 8 | 100.00% | 1331.76 | 0.0060 | 0.0057 | 0.0059 | 0.0060 | 0.0076 | 0.0733 |
| 64 | 100.00% | 9509.84 | 0.0067 | 0.0061 | 0.0063 | 0.0067 | 0.0097 | 0.3711 |
| 512 | 100.00% | 56601.79 | 0.0090 | 0.0085 | 0.0088 | 0.0094 | 0.0124 | 0.0856 |
| 2048 | 100.00% | 113918.88 | 0.0180 | 0.0171 | 0.0175 | 0.0192 | 0.0251 | 0.1138 |
| 16384 | 100.00% | 234336.44 | 0.0699 | 0.0562 | 0.0635 | 0.0963 | 0.1198 | 0.4904 |

## Standard. KV260: CPU

| Batch Size | Accuracy | Throughput (ksamp/s) | Latency Mean (ms) | Latency Min (ms) | Latency Median (ms) | Latency p95 (ms) | Latency p99 (ms) | Latency Max (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 100.00% | 10.75 | 0.0930 | 0.0910 | 0.0925 | 0.0937 | 0.1062 | 1.4950 |
| 8 | 100.00% | 84.79 | 0.0943 | 0.0924 | 0.0938 | 0.0953 | 0.1079 | 0.3456 |
| 64 | 100.00% | 608.69 | 0.1051 | 0.1028 | 0.1044 | 0.1066 | 0.1188 | 0.3705 |
| 512 | 100.00% | 2816.13 | 0.1818 | 0.1778 | 0.1805 | 0.1928 | 0.2004 | 0.4830 |
| 2048 | 100.00% | 4526.54 | 0.4524 | 0.4372 | 0.4471 | 0.4770 | 0.5368 | 0.8139 |
| 16384 | 100.00% | 7812.32 | 2.0972 | 2.0111 | 2.0888 | 2.1646 | 2.2927 | 12.4903 |

## DPU (Quantized). KV260: DPU

| Batch Size | Accuracy | Throughput (ksamp/s) | Latency Mean (ms) | Latency Min (ms) | Latency Median (ms) | Latency p95 (ms) | Latency p99 (ms) | Latency Max (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 100.00% | 3.96 | 0.2522 | 0.2464 | 0.2499 | 0.2647 | 0.3004 | 1.0190 |