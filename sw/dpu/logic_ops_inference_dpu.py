import vart
import xir
import numpy as np
import time
import argparse
from pynq_dpu import DpuOverlay

# Parse command line arguments
parser = argparse.ArgumentParser(description='Run logic operations inference benchmark on DPU')
args = parser.parse_args()

# 1. Load DPU Overlay
print(">>> Loading DPU Overlay...")
overlay = DpuOverlay("dpu.bit")
print(">>> Overlay loaded successfully!")

# 2. Deserialize the compiled model & Setup Runner
graph = xir.Graph.deserialize("logic_net_dpu.xmodel")
subgraphs = graph.get_root_subgraph().toposort_child_subgraph()
dpu_subgraphs =[s for s in subgraphs if s.has_attr("device") and s.get_attr("device").upper() == "DPU"]

dpu_runner = vart.Runner.create_runner(dpu_subgraphs[0], "run")

# 3. Prepare inputs and outputs properties
input_tensors = dpu_runner.get_input_tensors()
output_tensors = dpu_runner.get_output_tensors()

input_shape = tuple(input_tensors[0].dims)
output_shape = tuple(output_tensors[0].dims)
dpu_batch_size = input_shape[0]  # This is the hardware fixed batch size (usually 1)

# Get Quantization Scales
input_scale = 2 ** input_tensors[0].get_attr("fix_point")
output_scale = 1 / (2 ** output_tensors[0].get_attr("fix_point"))

# Pre-allocate memory buffers mapped to the DPU
input_data =[np.empty(input_shape, dtype=np.int8)]
output_data = [np.empty(output_shape, dtype=np.int8)]

# 4. Generate dataset pool purely in NumPy
dataset_size = 100000
X_test_batch = np.random.randint(0, 2, (dataset_size, 2)).astype(np.float32)

# Calculate expected outputs for AND, OR, and XOR
y_and_batch = (X_test_batch[:, 0] * X_test_batch[:, 1]).astype(np.int32)
y_or_batch = ((X_test_batch[:, 0] + X_test_batch[:, 1]) > 0).astype(np.int32)
y_xor_batch = (X_test_batch[:, 0] != X_test_batch[:, 1]).astype(np.int32)
y_expected_batch = np.stack([y_and_batch, y_or_batch, y_xor_batch], axis=1)

# OPTIMIZATION: Pre-quantize the entire input dataset to int8 so we don't 
# measure Python math overhead during the latency benchmark.
X_test_int8 = (X_test_batch * input_scale).astype(np.int8)

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

# 5. Run tests in batches
batch_sizes =[1] # No sense to test bigger batches, dpu doesn't support batches
num_iterations = 20000
batch_results = []

print(f"\n[INFO] DPU Native Compiled Batch Size: {dpu_batch_size}")
print(f"[INFO] Larger batch sizes will be processed in chunks of {dpu_batch_size}.\n")

for batch_size in batch_sizes:
    print(f">>> Starting benchmark for logical batch size: {batch_size} ({num_iterations} iterations)...")
 
    total_processed = num_iterations * batch_size
    latencies =[]
    total_correct = 0
    
    for i in range(num_iterations):
        batch_start = i * batch_size
        batch_end = batch_start + batch_size
        
        # Wrap around dataset pool
        indices = np.arange(batch_start, batch_end) % dataset_size
        
        # Get chunk data
        batch_input_int8 = X_test_int8[indices]
        batch_expected = y_expected_batch[indices]
        
        outputs_list =[]
        
        # ------------- TIMED EXECUTION BLOCK -------------
        start_time = time.perf_counter()
        
        # We must feed the DPU in chunks of its native `dpu_batch_size`
        for j in range(0, batch_size, dpu_batch_size):
            chunk = batch_input_int8[j:j+dpu_batch_size]
            actual_len = len(chunk)
            
            # Load into DPU memory buffer
            input_data[0][:actual_len] = chunk
            
            # Execute on FPGA
            job_id = dpu_runner.execute_async(input_data, output_data)
            dpu_runner.wait(job_id)
            
            # Read from DPU memory buffer and apply sigmoid / dequantize to have fair comparison with CPU/GPU scenarios
            raw_output = output_data[0][:actual_len].copy()
            processed_output = sigmoid(raw_output * output_scale)
            outputs_list.append(processed_output)
            
        end_time = time.perf_counter()
        # -------------------------------------------------
        
        latencies.append((end_time - start_time) * 1000)
        
        # Reconstruct full batch output
        output_batch = np.concatenate(outputs_list, axis=0)

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

# 6. Generate Markdown table
table_header = "| Batch Size | Accuracy | Throughput (ksamp/s) | Latency Mean (ms) | Latency Min (ms) | Latency Median (ms) | Latency p95 (ms) | Latency p99 (ms) | Latency Max (ms) | \n"
table_divider = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
table_rows = ""
 
for r in batch_results:
    table_rows += (f"| {r['batch_size']} | {r['accuracy']:.2f}% | {r['throughput_ksps']:.2f} | "
                   f"{r['mean']:.4f} | {r['min']:.4f} | {r['median']:.4f} | {r['p95']:.4f} | {r['p99']:.4f} | {r['max']:.4f} |\n")
 
markdown_output = f"""
### BENCHMARK RESULTS (20k Iterations/Batch Size)
 
{table_header}{table_divider}{table_rows}
 
**Iterations per Batch Size:** {num_iterations}  
**Device:** KV260 DPU (via VART Python API)  
**Note:** Data is continually wrapped around a {dataset_size}-sample pool.  
**Note:** Latency is measured for each logical batch, not per sample.  
"""
 
print(markdown_output)