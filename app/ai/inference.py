import io
from PIL import Image
import random

class LumenAIModel:
    def __init__(self, model_path=None):
        self.model_path = model_path

    def predict(self, image_bytes: bytes):
        Image.open(io.BytesIO(image_bytes)).convert("RGB")
        conf = round(random.random(), 2)
        return {
            "stain_detected": conf > 0.5,
            "confidence": conf,
            "material_type": "stainless_steel" if conf > 0.5 else "polymer",
        }
