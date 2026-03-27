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
  - Two flows are included: one using Xilinx's precompiled DPU platform, and another using a custom DPU platform.
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
./.venv/Scripts/Activate.ps1
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

# Usage: Standard flow (CPU/GPU inference, no DPU)

```bash
cd sw/standard

# Train:
# Run notebook logic_ops_train.ipynb

# Inference
python logic_ops_inference.py --device CPU
python logic_ops_inference.py --device GPU
```

# Vitis AI: Xilinx's precompiled DPU platform

## Install Vitis AI, quantize and compile model for the DPU

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

# Compile for KV260 DPU (using arch.json provided for the kv260 platform by Vitis AI)
(vitis-ai-pytorch) vitis-ai-user@docker-desktop:/workspace$ vai_c_xir -x quantize_result/LogicNet_int.xmodel \
          -a /opt/vitis_ai/compiler/arch/DPUCZDX8G/KV260/arch.json \
          -o ./compiled_model \
          -n logic_net_dpu
```

## Running the compiled model on the board

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
- Use xmutil to load the bitstream, dtbo and json files (option 1 or 4)
```bash
sudo xmutil unloadapp
sudo xmutil loadapp dpu # For option 1
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

# Vitis AI: Custom KV260 DPU platform

## References

- [DPUCZDX8G for Zynq UltraScale+ MPSoCs Product Guide (PG338)](https://docs.amd.com/r/en-US/pg338-dpu?tocId=3xsG16y_QFTWvAJKHbisEw)
- [Zynq UltraScale＋ MPSoC DPU TRD](https://github.com/Xilinx/Vitis-AI/blob/3.0/dpu/ref_design_docs/README_DPUCZDX8G.md)
- [Vitis AI DPU 3.0 Repository](https://github.com/Xilinx/Vitis-AI/tree/3.0/dpu)

## Notes

For convenience, the generated files are available in the repository to avoid having to generate them manually. The next steps can be skipped if you want to use the pre-generated files
- `output/artifacts/dpu_custom`: `arch.json`, `bd_top_wrapper.bit`, `bd_top.hwh`, `dpu.xclbin`, `kv260_dpu.xsa`
- `sw/dpu_custom`: `logic_ops_inference_dpu_custom.py` and compiled model `logic_net_dpu.xmodel`

You can use those files to run the inference on the board without having to go through the generation process. In that case, go directly to "Transfer files to the KV260 and run inference" section.

## Generate Vivado project, xsa and and Vitis platform (xpfm)

```bash
cd output

# Edit output/build_vivado_proj.py to set the correct path to your Vivado installation

# Generate the Vivado project, extensible XSA file and XPFM Vitis platform
python build_vivado_proj.py --target xpfm --jobs 4

```

## Generate xo and xclbin from xpfm, within DPUCZDX8G_VAI_v3.0

The DPU IP might be taken from [Vitis AI DPU 3.0 Repository](https://github.com/Xilinx/Vitis-AI/tree/3.0/dpu).
- [Direct link](https://www.xilinx.com/bin/public/openDownload?filename=DPUCZDX8G_VAI_v3.0.tar.gz)

Move it to ips and uncompress it with `tar -xzf DPUCZDX8G_VAI_v3.0.tar.gz` 

1) Edit `ips/DPUCZDX8G_VAI_v3.0/prj/Vitis/dpu_conf.vh` to define DPU configuration:

```bash
`define B4096 
`define URAM_ENABLE 
# DPU using all 64 URAM blocks
`ifdef URAM_ENABLE
    `define def_UBANK_IMG_N          8 // Buffers for input/output pixels. 8*2 = 16 URAM blocks
    `define def_UBANK_WGT_N          22 // Buffers for weights. 22*2 = 44 URAM blocks
    `define def_UBANK_BIAS           2  // Buffers for biases. 2*2 = 4 URAM blockspixels.
`elsif URAM_DISABLE
    `define def_UBANK_IMG_N          0
    `define def_UBANK_WGT_N          0
    `define def_UBANK_BIAS           0
`endif
`define DRAM_DISABLE 
`define RAM_USAGE_LOW
`define CHANNEL_AUGMENTATION_ENABLE
`define ALU_PARALLEL_DEFAULT 
`define CONV_RELU_LEAKYRELU_RELU6
`define ALU_RELU_RELU6
`define SAVE_ARGMAX_ENABLE
`define DSP48_USAGE_HIGH 
`define LOWPOWER_DISABLE
`define MPSOC
```

2) Edit ips/DPUCZDX8G_VAI_v3.0/prj/Vitis/config_file/prj_config to use only 1 DPU and configure the clock frequencies to be used:

```bash
[clock]

freqHz=300000000:DPUCZDX8G_1.aclk
freqHz=600000000:DPUCZDX8G_1.ap_clk_2
#freqHz=300000000:DPUCZDX8G_2.aclk
#freqHz=600000000:DPUCZDX8G_2.ap_clk_2

[connectivity]

sp=DPUCZDX8G_1.M_AXI_GP0:HPC0
sp=DPUCZDX8G_1.M_AXI_HP0:HP0
sp=DPUCZDX8G_1.M_AXI_HP2:HP1
#sp=DPUCZDX8G_2.M_AXI_GP0:HPC0
#sp=DPUCZDX8G_2.M_AXI_HP0:HP2
#sp=DPUCZDX8G_2.M_AXI_HP2:HP3

nk=DPUCZDX8G:1

```

3) Generate xo only

```bash
source /home/juanma/Xilinx/2025.2/Vitis/settings64.sh
cd ips/DPUCZDX8G_VAI_v3.0/prj/Vitis/
make binary_container_1/dpu.xo TARGET=hw DEVICE=kv260 KERNEL=DPU
make binary_container_1/softmax.xo TARGET=hw DEVICE=kv260 KERNEL=DPU_SM
```

4) Generate xo and xclbin

Edit DPUCZDX8G_VAI_v3.0/prj/Vitis/Makefile
```bash
SDX_PLATFORM = /home/juanma/0Projs/kv260_ai_projects/output/xpfm/kv260_dpu_vitis_platform/export/kv260_dpu_vitis_platform/kv260_dpu_vitis_platform.xpfm # Path to our custom xpfm platform, generated from vivado extensible xsa
```

To make all, including xo and xclbin
```bash
source /home/juanma/Xilinx/2025.2/Vitis/settings64.sh
cd ips/DPUCZDX8G_VAI_v3.0/prj/Vitis/
make all KERNEL=DPU DEVICE=SOM # only dpu
make all KERNEL=DPU_SM DEVICE=SOM # dpu and softmax
# It will take a while, as it runs synthesis and implementation for the DPU kernel, and then generates the xclbin. The generated files can be found under ips/DPUCZDX8G_VAI_v3.0/prj/Vitis/binary_container_1/ (including xo, xclbin and hwh files).
# It ended with an error related to copying the generated xclbin to the binary_*/sd_card folder, but the xclbin is generated correctly under binary_container_1/
# ...
# cp: cannot create regular file './binary_*/sd_card': No such file or directory
# make: *** [Makefile:113: package] Error 1
```

## Compile model

The steps are similar to the ones followed for the precompiled DPU platform, but using the arch.json generated from our custom platform:

```bash
cp ips/DPUCZDX8G_VAI_v3.0/prj/Vitis/binary_container_1/link/vivado/vpl/prj/prj.gen/sources_1/bd/bd_top/ip/bd_top_DPUCZDX8G_1_0/arch.json ~/0Projs/Vitis-AI/_logic_ops/
(vitis-ai-pytorch) vitis-ai-user@docker-desktop:/workspace/_logic_ops$ vai_c_xir -x quantize_result/LogicNet_int.xmodel -a arch.json -o ./compiled_model -n logic_net_dpu
```

## Transfer files to the KV260 and run inference

From the host:

```bash
scp ~/0Projs/Vitis-AI/_logic_ops/compiled_model/logic_net_dpu.xmodel kv260:/home/ubuntu/logic_ops/dpu_custom/logic_net_dpu.xmodel
scp sw/dpu_custom/logic_ops_inference_dpu_custom.py kv260:/home/ubuntu/logic_ops/dpu_custom/logic_ops_inference_dpu_custom.py
scp ips/DPUCZDX8G_VAI_v3.0/prj/Vitis/binary_container_1/link/vivado/vpl/prj/prj.gen/sources_1/bd/bd_top/hw_handoff/bd_top.hwh kv260:/home/ubuntu/logic_ops/dpu_custom/dpu.hwh
scp ips/DPUCZDX8G_VAI_v3.0/prj/Vitis/binary_container_1/link/vivado/vpl/prj/prj.runs/impl_1/bd_top_wrapper.bit kv260:/home/ubuntu/logic_ops/dpu_custom/dpu.bit
scp ips/DPUCZDX8G_VAI_v3.0/prj/Vitis/binary_container_1/binary_container_1.xclbin kv260:/home/ubuntu/logic_ops/dpu_custom/dpu.xclbin
```

From the KV260, run inference using VART Python API:

```bash
ubuntu@kria:~/logic_ops/dpu_custom$ ls
dpu.bit  dpu.hwh  dpu.xclbin  logic_net_dpu.xmodel  logic_ops_inference_dpu_custom.py
ubuntu@kria:~/logic_ops/dpu_custom$ sudo su
root@kria:/home/ubuntu/logic_ops/dpu_custom# export XLNX_VART_FIRMWARE=/home/ubuntu/logic_ops/dpu_custom/dpu.xclbin
root@kria:/home/ubuntu/logic_ops/dpu_custom# source /etc/profile.d/pynq_venv.sh
(pynq-venv) root@kria:/home/ubuntu/logic_ops/dpu_custom# python3 logic_ops_inference_dpu_custom.py
>>> Loading DPU Overlay...
>>> Overlay loaded successfully!

[INFO] DPU Native Compiled Batch Size: 1
[INFO] Larger batch sizes will be processed in chunks of 1.

>>> Starting benchmark for logical batch size: 1 (20000 iterations)...

### BENCHMARK RESULTS (20k Iterations/Batch Size)

| Batch Size | Accuracy | Throughput (ksamp/s) | Latency Mean (ms) | Latency Min (ms) | Latency Median (ms) | Latency p95 (ms) | Latency p99 (ms) | Latency Max (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 100.00% | 4.07 | 0.2460 | 0.2317 | 0.2438 | 0.2576 | 0.2932 | 4.4122 |


**Iterations per Batch Size:** 20000
**Device:** KV260 DPU (via VART Python API)
**Note:** Data is continually wrapped around a 100000-sample pool.
**Note:** Latency is measured for each logical batch, not per sample.

```

# Custom PL: Vitis HLS Kernel

## References

- [Vitis HLS User Guide (UG1399)](https://docs.amd.com/r/en-US/ug1399-vitis-hls)
- [PYNQ Documentation](https://pynq.readthedocs.io/en/latest/)

## Notes

The `logic_ops_nn` kernel (`kernels/logic_ops_hls/`) implements the same MLP directly in Vitis HLS using fixed-point `ap_fixed` quantized arithmetic (configurable via `USE_FLOAT` macro in `top.hpp`). All computation is integer-based for maximum efficiency.

**Kernel architecture:**
- **Input:** 2 AXI-Lite scalar registers (a, b) as `ap_fixed<8,5>`
- **Hidden layer:** 8 neurons with ReLU activation
- **Output layer:** 3 neurons with Sigmoid activation → 3 AXI-Lite scalar output registers
- **Quantization:** Layer1 weights/biases: `ap_fixed<8,5>` and `ap_fixed<8,4>`; Layer2 weights/biases: `ap_fixed<8,5>` and `ap_fixed<8,6>`; intermediate accumulators use wider types to prevent overflow
- **Ports:** All exposed as AXI-Lite registers for straightforward read/write access via PYNQ

For convenience, the generated artifacts are available in the repository:
- `output/artifacts/hls/kv260_dpu.xclbin` — xclbin containing platform bitstream + `logic_ops_nn_1` kernel
- `output/artifacts/hls/kv260_dpu.hwh` — post-link hardware description (required for PYNQ IP auto-discovery)

You can use those files to run inference on the board directly. In that case, skip to "Transfer files to the KV260 and run inference".

## Generate hardware artifacts

Generate the xo file for the logic_ops_nn kernel using Vitis HLS:
```bash
cd kernels/logic_ops_hls
source /path/to/Vitis/settings64.sh
vitis-run --mode hls --tcl --input_file run_hls.tcl
```

The `run_hls.tcl` script:
- Targets KV260 part (`xck26-sfvc784-2LV-c`) at 300 MHz (configurable)
- Runs C simulation, synthesis, co-simulation, and exports the `.xo` kernel object
- Aborts on test failure or timing violations

### Synthesis & Implementation Results

| Metric | Value | Notes |
|--------|-------|-------|
| **Clock Period (Target)** | 3.333 ns (300 MHz) | User-configurable in `run_hls.tcl` |
| **Clock Period (Estimated)** | 2.412 ns (414.59 MHz) | ✓ Passes timing constraint |
| **Pipeline Latency** | 50 clock cycles | Total end-to-end |
| **Timing Slack** | 0.02 ns | Comfortable margin |
| **BRAM** | 4 (1% of KV260) | Layer2 buffering |
| **DSP Slices** | 22 (1% of KV260) | MACs in Layer1 (4) & Layer2 (18) |
| **Flip-Flops** | 9,063 (3% of KV260) | Dominated by sigmoid (exp function) |
| **LUTs** | 7,944 (6% of KV260) | Dominated by sigmoid (exp function) |

**Co-Simulation:** ✓ PASS – RTL matches C model; measured latency 52–67 cycles (avg 59).

**Key Insight:** Sigmoid layer (with `hls::exp()`) dominates resource usage (89% FF, 80% LUT) due to fixed-point exponential expansion.

Sigmoid is resource-heavy in fixed-point HLS and could be delegated to software instead (as done in the DPU implementation) for a more efficient hardware design. However, for this proof-of-concept, I keep it in HLS to demonstrate the full NN on PL.

Generate the Vivado project, extensible XSA, Vitis platform and xclbin using the generated xo and our custom platform:
```bash
cd output

# Edit output/build_vivado_proj.py to set the correct paths to your Vivado/Vitis installations and to the xo file generated in the previous step

# Generate Vivado project, extensible XSA, Vitis platform, and XCLBIN (logic_ops_nn kernel linked in)
python build_vivado_proj.py --dev-flow vitis_platform --jobs 4
```

The build produces:
- `output/artifacts/kv260_dpu.xclbin` — xclbin with platform + kernel
- `output/artifacts/kv260_dpu.hwh` — post-link HWH for PYNQ IP discovery
- `output/artifacts/kv260_dpu.dtbo` / `output/artifacts/shell.json` — for xmutil (optional)

## Transfer files to the KV260 and run inference

From the host:

```bash
ssh kv260 "mkdir -p /home/ubuntu/logic_ops/hls"
scp output/artifacts/kv260_dpu.xclbin  kv260:/home/ubuntu/logic_ops/hls/kv260_dpu.xclbin
scp output/artifacts/kv260_dpu.hwh     kv260:/home/ubuntu/logic_ops/hls/kv260_dpu.hwh
scp sw/hls/logic_ops_inference_hls.py  kv260:/home/ubuntu/logic_ops/hls/logic_ops_inference_hls.py
```

From the KV260, run inference using the PYNQ AXI-Lite register interface:

```bash
ubuntu@kria:~/logic_ops/hls$ ls
kv260_dpu.hwh  kv260_dpu.xclbin  logic_ops_inference_hls.py
ubuntu@kria:~/logic_ops/hls$ sudo su
root@kria:/home/ubuntu/logic_ops/hls# source /etc/profile.d/pynq_venv.sh
(pynq-venv) root@kria:/home/ubuntu/logic_ops/hls# python3 logic_ops_inference_hls.py

@TODO
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

## DPU (Quantized, Xilinx's precompiled platform). KV260: DPU

| Batch Size | Accuracy | Throughput (ksamp/s) | Latency Mean (ms) | Latency Min (ms) | Latency Median (ms) | Latency p95 (ms) | Latency p99 (ms) | Latency Max (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 100.00% | 3.96 | 0.2522 | 0.2464 | 0.2499 | 0.2647 | 0.3004 | 1.0190 |

## DPU (Quantized, custom KV260 DPU platform). KV260: DPU

| Batch Size | Accuracy | Throughput (ksamp/s) | Latency Mean (ms) | Latency Min (ms) | Latency Median (ms) | Latency p95 (ms) | Latency p99 (ms) | Latency Max (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 100.00% | 4.03 | 0.2481 | 0.2349 | 0.2461 | 0.2608 | 0.2955 | 0.6850 |

## Custom PL (Vitis HLS kernel). KV260: Custom PL

| Batch Size | Accuracy | Throughput (ksamp/s) | Latency Mean (ms) | Latency Min (ms) | Latency Median (ms) | Latency p95 (ms) | Latency p99 (ms) | Latency Max (ms) | 
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 100.00% | 9.31 | 0.1074 | 0.1041 | 0.1069 | 0.1083 | 0.1212 | 0.2359 |