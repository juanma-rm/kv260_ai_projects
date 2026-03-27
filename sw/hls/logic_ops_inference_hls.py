"""
Inference benchmark for the logic_ops_nn Vitis HLS kernel on the KV260.

The kernel implements a 2-input, 3-output MLP (AND / OR / XOR logic) entirely in
fixed-point arithmetic and is exposed via an AXI-Lite register interface:

  Offset  Register   Direction  Description
  0x00    AP_CTRL    R/W        ap_start(0) ap_done(1) ap_idle(2) ap_ready(3), ap_continue(4)
  0x10    a          W          Input bit A   (ap_fixed<8,5>)
  0x18    b          W          Input bit B   (ap_fixed<8,5>)
  0x20    res_and    R          AND output    (ap_fixed<8,2>)
  0x30    res_or     R          OR  output    (ap_fixed<8,2>)
  0x40    res_xor    R          XOR output    (ap_fixed<8,2>)

Usage (on KV260):
    sudo su
    source /etc/profile.d/pynq_venv.sh
    python3 logic_ops_inference_hls.py        # xclbin must be in same dir
"""

from pynq import Overlay
import numpy as np
import time


# ===========================================================================
# HLS Kernel Wrapper
# ===========================================================================
class HlsLogicOpsKernel:
    """Encapsulates AXI-Lite register access for the logic_ops_nn HLS kernel."""

    # Fixed-point parameters (must match top.hpp)
    INPUT_FRAC_BITS  = 3
    INPUT_SCALE      = 1 << INPUT_FRAC_BITS   # 8   (ap_fixed<8,5>)
    OUTPUT_FRAC_BITS = 6
    OUTPUT_SCALE     = 1 << OUTPUT_FRAC_BITS   # 64  (ap_fixed<8,2>)

    # AXI-Lite register offsets (from hls_compile.rpt / kernel.xml)
    REG_AP_CTRL = 0x00
    REG_A       = 0x10
    REG_B       = 0x18
    REG_RES_AND = 0x20
    REG_RES_OR  = 0x30
    REG_RES_XOR = 0x40

    AP_START    = 0x1
    AP_DONE     = 0x2
    AP_CONTINUE = 0x10

    def __init__(self, xclbin_path: str = "kv260_dpu.xclbin",
                 ip_name: str = "logic_ops_nn_1"):
        print(">>> Loading HLS Overlay...")
        self.overlay = Overlay(xclbin_path)
        self.ip = getattr(self.overlay, ip_name)
        print(">>> Overlay loaded successfully!")

    # ----- fixed-point helpers -----
    def _to_fixed_input(self, x: float) -> int:
        """float → ap_fixed<8,5> integer representation."""
        return int(round(x * self.INPUT_SCALE)) & 0xFF

    def _from_fixed_output(self, raw: int) -> float:
        """ap_fixed<8,2> register value → float."""
        val = raw & 0xFF
        if val >= 0x80:
            val -= 0x100
        return val / self.OUTPUT_SCALE

    # ----- kernel execution -----
    def run(self, a: float, b: float) -> tuple[float, float, float]:
        """Execute one inference and return (res_and, res_or, res_xor) as floats."""
        ip = self.ip
        ip.write(self.REG_A, self._to_fixed_input(a))
        ip.write(self.REG_B, self._to_fixed_input(b))

        ip.write(self.REG_AP_CTRL, self.AP_START | self.AP_CONTINUE)

        while not (ip.read(self.REG_AP_CTRL) & self.AP_DONE):
            pass

        res_and = self._from_fixed_output(ip.read(self.REG_RES_AND))
        res_or  = self._from_fixed_output(ip.read(self.REG_RES_OR))
        res_xor = self._from_fixed_output(ip.read(self.REG_RES_XOR))

        ip.write(self.REG_AP_CTRL, self.AP_CONTINUE)
        return res_and, res_or, res_xor


# ===========================================================================
# Main benchmark
# ===========================================================================

# 1. Load kernel
kernel = HlsLogicOpsKernel()

# 2. Generate dataset pool (same methodology as DPU benchmark)
dataset_size = 100000
X_test = np.random.randint(0, 2, (dataset_size, 2)).astype(np.float32)

y_and = (X_test[:, 0] * X_test[:, 1]).astype(np.int32)
y_or  = ((X_test[:, 0] + X_test[:, 1]) > 0).astype(np.int32)
y_xor = (X_test[:, 0] != X_test[:, 1]).astype(np.int32)
y_expected = np.stack([y_and, y_or, y_xor], axis=1)

# 3. Benchmark parameters
batch_sizes = [1]
num_iterations = 20000
batch_results = []

print(f"\n[INFO] HLS kernel processes 1 sample per invocation (AXI-Lite).\n")

for batch_size in batch_sizes:
    print(f">>> Starting benchmark for logical batch size: {batch_size} ({num_iterations} iterations)...")

    total_processed = num_iterations * batch_size
    latencies = []
    total_correct = 0

    for i in range(num_iterations):
        batch_start = i * batch_size
        batch_end = batch_start + batch_size
        indices = np.arange(batch_start, batch_end) % dataset_size

        batch_inputs = X_test[indices]
        batch_expected = y_expected[indices]

        outputs_list = []

        # ------------- TIMED EXECUTION BLOCK -------------
        start_time = time.perf_counter()

        for j in range(batch_size):
            a_val, b_val = float(batch_inputs[j, 0]), float(batch_inputs[j, 1])
            res_and, res_or, res_xor = kernel.run(a_val, b_val)
            outputs_list.append([res_and, res_or, res_xor])

        end_time = time.perf_counter()
        # -------------------------------------------------

        latencies.append((end_time - start_time) * 1000)

        output_batch = np.array(outputs_list)
        preds = (output_batch > 0.5).astype(np.int32)
        total_correct += np.all(preds == batch_expected, axis=1).sum()

    # Compute statistics
    lat_np = np.array(latencies)
    total_time_sec = np.sum(lat_np) / 1000
    throughput = total_processed / total_time_sec
    total_acc = (total_correct / total_processed) * 100

    batch_results.append({
        'batch_size': batch_size,
        'accuracy': total_acc,
        'throughput_ksps': throughput / 1000,
        'min': np.min(lat_np),
        'mean': np.mean(lat_np),
        'median': np.median(lat_np),
        'max': np.max(lat_np),
        'p95': np.percentile(lat_np, 95),
        'p99': np.percentile(lat_np, 99)
    })

# 4. Generate Markdown table
table_header  = "| Batch Size | Accuracy | Throughput (ksamp/s) | Latency Mean (ms) | Latency Min (ms) | Latency Median (ms) | Latency p95 (ms) | Latency p99 (ms) | Latency Max (ms) | \n"
table_divider = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
table_rows = ""

for r in batch_results:
    table_rows += (f"| {r['batch_size']} | {r['accuracy']:.2f}% | {r['throughput_ksps']:.2f} | "
                   f"{r['mean']:.4f} | {r['min']:.4f} | {r['median']:.4f} | {r['p95']:.4f} | {r['p99']:.4f} | {r['max']:.4f} |\n")

markdown_output = f"""
### BENCHMARK RESULTS (20k Iterations/Batch Size)

{table_header}{table_divider}{table_rows}

**Iterations per Batch Size:** {num_iterations}
**Device:** KV260 HLS Kernel (AXI-Lite via PYNQ)
**Note:** Data is continually wrapped around a {dataset_size}-sample pool.
**Note:** Latency is measured for each logical batch, not per sample.
"""

print(markdown_output)
