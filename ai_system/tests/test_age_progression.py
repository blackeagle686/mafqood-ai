import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Force unload mock cv2 if present in sys.modules
if 'cv2' in sys.modules and (isinstance(sys.modules['cv2'], MagicMock) or 'MagicMock' in str(type(sys.modules['cv2']))):
    del sys.modules['cv2']

# Force unload services.age_progression_service if present in sys.modules
if 'services.age_progression_service' in sys.modules:
    del sys.modules['services.age_progression_service']

import cv2
import numpy as np
import tempfile
import shutil
from services.age_progression_service import AgeProgressionGAN

# Store a reference to the real exists function for selective mocking
_real_exists = os.path.exists

@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    if _real_exists(d):
        shutil.rmtree(d)

@pytest.fixture
def sample_image_path(temp_dir):
    img_path = os.path.join(temp_dir, "child_face.jpg")
    # Create a 256x256 solid blue image
    img = np.zeros((256, 256, 3), dtype=np.uint8)
    img[:, :] = [255, 0, 0] # Blue in BGR
    cv2.imwrite(img_path, img)
    return img_path

def test_age_progression_fallback_simulation(sample_image_path):
    # Initialize with non-existent model path to trigger simulation
    gan = AgeProgressionGAN(model_path="non_existent_model_path.onnx")
    assert gan.session is None

    age_jumps = [5, 10, 15]
    result = gan.generate_aged_images(sample_image_path, age_jumps=age_jumps)
    
    assert len(result) == 3
    for jump in age_jumps:
        assert jump in result
        saved_path = result[jump]
        assert _real_exists(saved_path)
        # Verify it's a valid image
        saved_img = cv2.imread(saved_path)
        assert saved_img is not None
        assert saved_img.shape == (256, 256, 3)
        # Cleanup temp generated file
        os.remove(saved_path)

def test_preprocess_postprocess():
    gan = AgeProgressionGAN(model_path="non_existent_model_path.onnx")
    
    # Create a dummy image
    img = np.ones((256, 256, 3), dtype=np.uint8) * 128
    
    tensor = gan._preprocess(img, target_size=(128, 128))
    # Expected shape: NCHW -> (1, 3, 128, 128)
    assert tensor.shape == (1, 3, 128, 128)
    assert tensor.dtype == np.float32
    assert -1.0 <= tensor.min() <= 1.0
    
    reconstructed = gan._postprocess(tensor)
    assert reconstructed.shape == (128, 128, 3)
    assert reconstructed.dtype == np.uint8

@patch('os.path.exists')
@patch('onnxruntime.InferenceSession')
def test_onnx_model_execution(mock_inference_session, mock_exists, sample_image_path):
    # Only mock exists for the dummy ONNX model path
    mock_exists.side_effect = lambda path: True if "dummy_age_progression.onnx" in path else _real_exists(path)
    
    # Mock ONNX InferenceSession metadata
    mock_session_instance = MagicMock()
    mock_input_1 = MagicMock()
    mock_input_1.name = "input_image"
    mock_input_1.shape = [1, 3, 256, 256]
    mock_session_instance.get_inputs.return_value = [mock_input_1]
    
    mock_output_1 = MagicMock()
    mock_output_1.name = "output_image"
    mock_session_instance.get_outputs.return_value = [mock_output_1]
    
    # Mock session run output (returns NCHW float32 tensor of size 1x3x256x256)
    dummy_out = np.zeros((1, 3, 256, 256), dtype=np.float32)
    mock_session_instance.run.return_value = [dummy_out]
    mock_inference_session.return_value = mock_session_instance
    
    # Initialize GAN - should trigger ONNX loading
    gan = AgeProgressionGAN(model_path="models/dummy_age_progression.onnx")
    
    assert gan.session is not None
    assert gan.input_name == "input_image"
    assert gan.output_name == "output_image"
    
    # Execute generation
    result = gan.generate_aged_images(sample_image_path, age_jumps=[10])
    
    assert 10 in result
    saved_path = result[10]
    assert _real_exists(saved_path)
    
    # Verify session run was called
    assert mock_session_instance.run.call_count == 1
    # Cleanup
    os.remove(saved_path)

@patch('os.path.exists')
@patch('onnxruntime.InferenceSession')
def test_onnx_model_with_age_input(mock_inference_session, mock_exists, sample_image_path):
    mock_exists.side_effect = lambda path: True if "dummy_age_progression.onnx" in path else _real_exists(path)
    
    # Mock ONNX session with two inputs: image and age
    mock_session_instance = MagicMock()
    mock_input_image = MagicMock()
    mock_input_image.name = "input_image"
    mock_input_image.shape = [1, 3, 256, 256]
    mock_input_age = MagicMock()
    mock_input_age.name = "input_age"
    mock_input_age.shape = [1]
    mock_session_instance.get_inputs.return_value = [mock_input_image, mock_input_age]
    
    mock_output = MagicMock()
    mock_output.name = "output_image"
    mock_session_instance.get_outputs.return_value = [mock_output]
    
    dummy_out = np.zeros((1, 3, 256, 256), dtype=np.float32)
    mock_session_instance.run.return_value = [dummy_out]
    mock_inference_session.return_value = mock_session_instance
    
    gan = AgeProgressionGAN(model_path="models/dummy_age_progression.onnx")
    
    result = gan.generate_aged_images(sample_image_path, age_jumps=[5])
    
    assert 5 in result
    saved_path = result[5]
    assert _real_exists(saved_path)
    
    # Verify it ran with age parameter
    args, kwargs = mock_session_instance.run.call_args
    input_feed = kwargs.get('input_feed') or args[1]
    assert "input_image" in input_feed
    assert "input_age" in input_feed
    assert input_feed["input_age"][0] == 5.0
    
    # Cleanup
    os.remove(saved_path)

def test_real_onnx_model_execution(sample_image_path):
    if not _real_exists("models/age_progression_light.onnx"):
        pytest.skip("Real ONNX model not found")
        
    gan = AgeProgressionGAN(model_path="models/age_progression_light.onnx")
    assert gan.session is not None
    assert gan.input_shape[1] == 5 # 5 channels
    
    result = gan.generate_aged_images(sample_image_path, age_jumps=[10])
    assert 10 in result
    saved_path = result[10]
    assert _real_exists(saved_path)
    
    # Verify image dimensions
    saved_img = cv2.imread(saved_path)
    assert saved_img is not None
    # Output size should be identical to input size (256, 256)
    assert saved_img.shape == (256, 256, 3)
    
    os.remove(saved_path)
