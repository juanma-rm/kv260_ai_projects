# Introduction

Collection of projects exploring AI capabilities in FPGAs, testing different flows (Vitis AI+DPU, custom RTL / HLS) and targeting an AMD KV260 board.

Each application will be available at a different branch.

# Early plan

These are just some of the projects and flows I want to explore and test, gradually. It can change on the go.

Applications:
- Logic Operations. MLP, toy app for testing dpu and custom kernels
- Iris Micro. Predicting flower type from 4 measurements. MLP, toy app for testing dpu and custom kernels
- Edge detection. CNN, toy app for testing dpu and custom kernels
- Other image processing operations
- Some application using the video stream coming from the image sensor

Workflows:
- Standard (pytorch, CPU and GPU)
- Vitis AI (DPU)
- Custom kernels (SystemVerilog, HLS)
- hls4ml

# Hardware setup

## Workstation

- CPU: AMD Ryzen 7 9800X3D 4.7/5.2GHz
- GPU: MSI GeForce RTX 5070 Ti VENTUS 3X OC 16GB GDDR7
- RAM: Corsair Vengeance DDR5 6000MHz CL30 32GB 2x16GB CL30
- OS: Windows 11 Home

![Typical computer cpu - gpu diagram](/pics/workstation_arch.png)


## AMD Kria KV260

- K26 SOM
- Zynq UltraScale+ MPSoC (XCK26-SFVC784-2LV-C/I)
- APU (Application Processing Unit): Arm Cortex A53 quad-core, Fmax 1333 MHz
- GPU (Graphics Processing Unit): Arm Mali-400 MP2, Fmax 600 MHz
- PL (Programmable Logic): 234K FFs, 117k LUTs, 5.1Mbit BRAM, 18MBit UltraRAM, 1248 DSP slices, DPUCZDX8G
- RAM: DDR4 RAM 4GB
- OS (APU): Ubuntu 22.04 LTS

![Zynq UltraScale+ Architecture Block Diagram](/pics/zynq_usplus_arch.png)
