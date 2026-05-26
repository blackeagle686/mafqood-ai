import os
import sys
import torch

# Add temp repository to python import path
sys.path.append(os.path.abspath("temp_face_reaging"))

from model.models import UNet

def export():
    model_path = "models/best_unet_model.pth"
    onnx_path = "models/age_progression_light.onnx"
    
    print(f"Loading PyTorch checkpoint from {model_path}...")
    model = UNet()
    state_dict = torch.load(model_path, map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()
    
    print("Preparing dummy input tensor...")
    # The U-Net expects 5 input channels: RGB (3) + source age channel (1) + target age channel (1)
    # The training/inference uses 512x512 resolution
    dummy_input = torch.randn(1, 5, 512, 512, dtype=torch.float32)
    
    print(f"Exporting model to ONNX at {onnx_path}...")
    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        input_names=["input_tensor"],
        output_names=["output_tensor"],
        opset_version=14, # Opsets 14+ support advanced PyTorch features like antialiased BlurPool
        dynamic_axes={
            "input_tensor": {0: "batch_size"},
            "output_tensor": {0: "batch_size"}
        }
    )
    print("ONNX model exported successfully!")

if __name__ == "__main__":
    export()
