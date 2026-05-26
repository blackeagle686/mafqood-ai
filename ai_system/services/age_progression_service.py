import logging
import cv2
import numpy as np
import os
import uuid
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class AgeProgressionGAN:
    """
    Module responsible for generating age-progressed versions of missing children's faces.
    Utilizes pre-trained, lightweight Generative Adversarial Networks (GANs) or autoencoders
    compiled to ONNX format and optimized for CPU inference.
    """
    
    def __init__(self, model_path: str = "models/age_progression_light.onnx"):
        self.model_path = model_path
        self.session = None
        self._load_model()
        
    def _load_model(self):
        """
        Loads the ONNX model into memory and configures CPU optimization settings.
        """
        if not os.path.exists(self.model_path):
            logger.warning(
                f"Age progression model not found at '{self.model_path}'. "
                "Running in simulated mode for age progression."
            )
            return

        try:
            import onnxruntime as ort
            
            # CPU performance optimizations
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            
            # Limit thread counts to avoid CPU thrashing on multi-core servers
            opts.intra_op_num_threads = min(4, os.cpu_count() or 1)
            opts.inter_op_num_threads = 1
            
            logger.info(f"Initializing CPU-optimized ONNX session for age progression from {self.model_path}...")
            self.session = ort.InferenceSession(self.model_path, sess_options=opts, providers=['CPUExecutionProvider'])
            
            # Fetch input/output metadata
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            self.input_shape = self.session.get_inputs()[0].shape
            logger.info(f"ONNX model loaded successfully. Input shape: {self.input_shape}")
        except Exception as e:
            logger.error(f"Failed to load ONNX age progression model: {e}. Falling back to simulation.")
            self.session = None
            
    def _preprocess(self, img: np.ndarray, target_size=(256, 256)) -> np.ndarray:
        """
        Preprocesses a raw image to a normalized NCHW float32 tensor.
        """
        # Resize to standard model size
        resized = cv2.resize(img, target_size)
        # BGR to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        # Normalize to [-1, 1] range commonly used by GANs
        normalized = (rgb.astype(np.float32) / 127.5) - 1.0
        # HWC to NCHW
        nchw = np.transpose(normalized, (2, 0, 1))
        tensor = np.expand_dims(nchw, axis=0)
        return tensor

    def _postprocess(self, tensor: np.ndarray) -> np.ndarray:
        """
        Converts the model output tensor back to a standard BGR OpenCV image.
        """
        # Remove batch dimension: NCHW to CHW
        chw = np.squeeze(tensor, axis=0)
        # Clip to [-1, 1] range to avoid artifacts
        clipped = np.clip(chw, -1.0, 1.0)
        # Scale back to [0, 255]
        scaled = ((clipped + 1.0) * 127.5).astype(np.uint8)
        # CHW to HWC
        rgb = np.transpose(scaled, (1, 2, 0))
        # RGB to BGR for OpenCV saving
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        return bgr

    def generate_aged_images(self, image_path: str, age_jumps: List[int] = [5, 10, 15], source_age: int = 8) -> Dict[str, str]:
        """
        Takes an original image and generates new versions corresponding to the requested age jumps.
        Saves output images to disk temporarily.
        
        Args:
            image_path: Original face image
            age_jumps: List of years to add to the face
            source_age: Current estimated/known age of the child
            
        Returns:
            Dictionary mapped like: { 5: "/temp/aged_5_uuid.jpg", 10: "/temp/aged_10_uuid.jpg" }
        """
        logger.info(f"Generating +{age_jumps} years age progressions for {image_path} (source age: {source_age})")
        
        img = cv2.imread(image_path)
        if img is None:
            logger.error("Failed to read image for age progression.")
            return {}
             
        generated_paths = {}
        temp_dir = "./temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        
        for jump in age_jumps:
            try:
                if self.session is not None:
                    input_channels = self.input_shape[1] if len(self.input_shape) > 1 else 3
                    
                    if input_channels == 5:
                        # FRAN model: Input size is typically 512x512
                        model_size = (512, 512)
                        resized = cv2.resize(img, model_size)
                        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                        # Normalize to [0, 1] range as used during transforms.ToTensor()
                        rgb_normalized = rgb.astype(np.float32) / 255.0
                        chw = np.transpose(rgb_normalized, (2, 0, 1))
                        
                        # Construct age channels (normalized by 100)
                        src_age_val = float(source_age) / 100.0
                        tgt_age_val = float(source_age + jump) / 100.0
                        src_age_channel = np.full((1, model_size[1], model_size[0]), src_age_val, dtype=np.float32)
                        tgt_age_channel = np.full((1, model_size[1], model_size[0]), tgt_age_val, dtype=np.float32)
                        
                        # Concatenate channels to form shape: (5, 512, 512)
                        input_data = np.concatenate([chw, src_age_channel, tgt_age_channel], axis=0)
                        input_tensor = np.expand_dims(input_data, axis=0)
                        
                        # Run ONNX inference
                        outputs = self.session.run([self.output_name], {self.input_name: input_tensor})
                        output_tensor = outputs[0]
                        
                        # FRAN output is a residual map to be added to the input image
                        residual_chw = np.squeeze(output_tensor, axis=0)
                        residual_rgb = np.transpose(residual_chw, (1, 2, 0))
                        
                        # Add residual to normalized input and clamp
                        final_rgb = rgb_normalized + residual_rgb
                        final_rgb = np.clip(final_rgb, 0.0, 1.0)
                        
                        # Convert back to uint8 BGR
                        final_rgb_255 = (final_rgb * 255.0).astype(np.uint8)
                        aged_img = cv2.cvtColor(final_rgb_255, cv2.COLOR_RGB2BGR)
                        # Resize back to original input image size
                        aged_img = cv2.resize(aged_img, (img.shape[1], img.shape[0]))
                    else:
                        # Standard 3-channel GAN model
                        input_tensor = self._preprocess(img)
                        
                        if len(self.session.get_inputs()) > 1:
                            age_input_name = self.session.get_inputs()[1].name
                            age_tensor = np.array([float(jump)], dtype=np.float32)
                            outputs = self.session.run(
                                [self.output_name],
                                {self.input_name: input_tensor, age_input_name: age_tensor}
                            )
                        else:
                            outputs = self.session.run([self.output_name], {self.input_name: input_tensor})
                        
                        aged_img = self._postprocess(outputs[0])
                        # Resize back to original input image size
                        aged_img = cv2.resize(aged_img, (img.shape[1], img.shape[0]))
                else:
                    # Optimized simulated aging fallback
                    aged_img = img.copy()
                    # Simulating aging: Adding noise & slight blurring
                    if jump > 0:
                        noise = np.random.normal(0, jump * 1.5, aged_img.shape).astype(np.uint8)
                        aged_img = cv2.add(aged_img, noise)
                        aged_img = cv2.GaussianBlur(aged_img, (5, 5), jump * 0.2)
                
                # Save temporary aged image
                jump_path = os.path.join(temp_dir, f"aged_{jump}_{uuid.uuid4()}.jpg")
                cv2.imwrite(jump_path, aged_img)
                generated_paths[jump] = jump_path
                
            except Exception as e:
                logger.error(f"Error executing age progression for +{jump}: {e}")
                
        return generated_paths
