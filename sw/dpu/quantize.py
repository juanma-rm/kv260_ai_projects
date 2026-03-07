import torch
import torch.nn as nn
from pytorch_nndct.apis import torch_quantizer

# 1. Re-define your model architecture exactly as in training
class LogicNet(nn.Module):
    def __init__(self):
        super(LogicNet, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(2, 8),
            nn.ReLU(),
            nn.Linear(8, 3),
            nn.Sigmoid() 
        )

    def forward(self, x):
        return self.net(x)

def main():
    device = torch.device("cpu")
    model = LogicNet().to(device)
    
    # Load the trained weights
    model.load_state_dict(torch.load("logic_ops_params.pth", map_location=device))
    model.eval()

    # Vitis AI requires batch_size=1 for the final compilation export
    dummy_input = torch.randn([1, 2], dtype=torch.float32).to(device)

    print("--- Starting Calibration Phase ---")
    # Initialize the quantizer in 'calib' mode
    quantizer = torch_quantizer('calib', model, (dummy_input), device=device)
    quant_model = quantizer.quant_model

    # Create calibration data (Vitis AI usually needs 100-1000 samples)
    # Since our logic gate dataset is just 4 states, we'll just repeat them 25 times
    X_calib = torch.tensor([[0, 0], [0, 1], [1, 0],[1, 1]], dtype=torch.float32)
    
    with torch.no_grad():
        for _ in range(25): 
            quant_model(X_calib)
            
    # Export calibration data
    quantizer.export_quant_config()

    print("--- Starting Export Phase ---")
    # Initialize the quantizer in 'test' mode to generate the xmodel
    quantizer_test = torch_quantizer('test', model, (dummy_input), device=device)
    quant_model_test = quantizer_test.quant_model
    
    with torch.no_grad():
        # A single forward pass with batch_size=1 is required here
        quant_model_test(dummy_input)
        
    # Export the quantized XIR model
    output_dir = "quantize_result"
    quantizer_test.export_xmodel(deploy_check=False, output_dir=output_dir)
    print(f"Quantization complete! Model saved in ./{output_dir}")

if __name__ == "__main__":
    main()