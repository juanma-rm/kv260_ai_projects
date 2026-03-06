import onnxruntime as ort
import numpy as np
import time
import argparse
from IPython.display import display, Markdown

# Parse command line arguments
parser = argparse.ArgumentParser(description='Run logic operations inference benchmark')
parser.add_argument('--device', type=str, default='CPU', choices=['CPU', 'GPU'], 
                    help='Device to run inference on (CPU or GPU)')
args = parser.parse_args()

# Select device
device = args.device
DEVICE_LIST = ["CPU", "GPU"]
if device not in DEVICE_LIST:
    raise ValueError(f"Invalid device: {device}. Must be one of {DEVICE_LIST}")

if device == "GPU":
    providers = ['CUDAExecutionProvider']
else:
    providers = ['CPUExecutionProvider']

# Import model from ONNX

try:
    session = ort.InferenceSession("logic_ops_params.onnx", providers=providers)
except Exception as e:
    print(f"ERROR: Failed to initialize {device} session.")
    raise e

input_name = session.get_inputs()[0].name

# Run tests in batches

# 1. Generate dataset pool purely in NumPy
dataset_size = 100000
# np.random.randint(low, high) is exclusive of high, so 0 to 2 yields 0s and 1s
X_test_batch = np.random.randint(0, 2, (dataset_size, 2)).astype(np.float32)

# Calculate expected outputs for AND, OR, and XOR
y_and_batch = (X_test_batch[:, 0] * X_test_batch[:, 1]).astype(np.int32)
y_or_batch = ((X_test_batch[:, 0] + X_test_batch[:, 1]) > 0).astype(np.int32)
y_xor_batch = (X_test_batch[:, 0] != X_test_batch[:, 1]).astype(np.int32) # Added XOR

# Stack all three targets
y_expected_batch = np.stack([y_and_batch, y_or_batch, y_xor_batch], axis=1)
 
# 2. Test different batch sizes, running exactly 20k iterations for each
batch_sizes = [1, 8, 64, 512, 2048, 16384]
num_iterations = 20000
batch_results = []
 
for batch_size in batch_sizes:
    
    print(f">>> Starting benchmark for batch size: {batch_size} ({num_iterations} iterations)...")
 
    total_processed = num_iterations * batch_size
    latencies = []
    total_correct = 0  # Track correct preds on the fly to save memory
    
    for i in range(num_iterations):
        batch_start = i * batch_size
        batch_end = batch_start + batch_size
        
        # Wrap around dataset pool if necessary using np.arange
        indices = np.arange(batch_start, batch_end) % dataset_size
        
        # Data is already in numpy format
        batch_input = X_test_batch[indices]
        batch_expected = y_expected_batch[indices]
        
        # Run inference and measure latency using CPU perf_counter
        start_time = time.perf_counter()
        raw_output = session.run(None, {input_name: batch_input})[0]
        end_time = time.perf_counter()
        
        # Convert seconds to milliseconds
        latencies.append((end_time - start_time) * 1000)
        
        # Tally accuracy for this batch against all 3 gates simultaneously
        preds = (raw_output > 0.5).astype(np.int32)
        total_correct += np.all(preds == batch_expected, axis=1).sum()
    
    # 3. Compute statistics
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
**Device:** {device}  
**Note:** Data is continually wrapped around a {dataset_size}-sample pool.  
**Note:** Latency is measured for each batch, not per sample.  
"""
 
print(markdown_output)