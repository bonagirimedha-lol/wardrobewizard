# ml/clothing_classifier.py
import torch
import torchvision.transforms as transforms
from torchvision.models import resnet18, ResNet18_Weights
from PIL import Image
import numpy as np
from sklearn.cluster import KMeans
import webcolors
import os

class ClothingClassifier:
    def __init__(self):
        # Load pre-trained model (using ResNet18 with default weights)
        try:
            weights = ResNet18_Weights.DEFAULT
            self.model = resnet18(weights=weights)
            
            # Check if custom fine-tuned weights exist and load them!
            custom_weights_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wardrobe_model.pth')
            if os.path.exists(custom_weights_path):
                print("Loading fine-tuned wardrobe model weights...")
                try:
                    self.model.load_state_dict(torch.load(custom_weights_path))
                except Exception as ex:
                    print(f"Error loading custom state dict: {ex}")
                    
            self.model.eval()
            self.imagenet_classes = weights.meta["categories"]
        except Exception as e:
            print(f"Error loading model: {e}")
            self.model = None
            self.imagenet_classes = []
        
        # Categories for clothing
        self.categories = [
            't-shirt', 'jeans', 'dress', 'jacket', 'shoes',
            'hat', 'scarf', 'skirt', 'shorts', 'sweater'
        ]
        
        # Style classifier (simplified - would need proper training)
        self.styles = {
            'formal': ['suit', 'blazer', 'dress_shirt'],
            'casual': ['t-shirt', 'jeans', 'sneakers'],
            'athletic': ['sweatpants', 'hoodie', 'gym_shoes']
        }
    
    def map_imagenet_to_clothing(self, label_name):
        """Map ImageNet classes to wardrobe categories using keyword matches"""
        label_lower = label_name.lower()
        
        # Check shoes first
        if any(w in label_lower for w in ['shoe', 'sandal', 'clog', 'boot', 'loafer', 'sneaker', 'slipper']):
            return 'shoes'
        
        # Check hat
        if any(w in label_lower for w in ['hat', 'cap', 'bonnet', 'sombrero', 'helmet']):
            return 'hat'
            
        # Check jacket
        if any(w in label_lower for w in ['jacket', 'coat', 'windbreaker', 'overcoat', 'blazer', 'trench', 'cardigan']):
            return 'jacket'
            
        # Check jeans / pants
        if any(w in label_lower for w in ['jean', 'pant', 'trouser', 'slacks']):
            return 'jeans'
            
        # Check dress
        if any(w in label_lower for w in ['dress', 'gown', 'frock', 'robe', 'kimono']):
            return 'dress'
            
        # Check sweater
        if any(w in label_lower for w in ['sweater', 'pullover', 'poncho', 'wool']):
            return 'sweater'
            
        # Check skirt
        if any(w in label_lower for w in ['skirt', 'kilt', 'miniskirt']):
            return 'skirt'
            
        # Check shorts
        if any(w in label_lower for w in ['shorts', 'trunks', 'swimwear']):
            return 'shorts'
            
        # Check scarf
        if any(w in label_lower for w in ['scarf', 'stole', 'shawl', 'boa', 'muffler']):
            return 'scarf'
            
        # Check t-shirt / shirt
        if any(w in label_lower for w in ['t-shirt', 'tee shirt', 'jersey', 'sweatshirt', 'shirt', 'blouse']):
            return 't-shirt'
            
        return None

    def classify_item(self, image_path):
        """Main classification function"""
        try:
            image = Image.open(image_path).convert('RGB')
        except Exception:
            return {'error': 'Invalid image'}
        
        category = 't-shirt' # Fallback
        confidence = 0.0
        
        if self.model and self.imagenet_classes:
            # Preprocess for model
            preprocess = transforms.Compose([
                transforms.Resize(256),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            ])
            
            input_tensor = preprocess(image)
            input_batch = input_tensor.unsqueeze(0)
            
            # Get prediction
            with torch.no_grad():
                output = self.model(input_batch)
            
            # Find the best matching clothing class in the top-20 predictions
            probabilities = torch.nn.functional.softmax(output[0], dim=0)
            top_probs, top_indices = torch.sort(probabilities, descending=True)
            
            mapped_category = None
            for prob, idx in zip(top_probs[:20], top_indices[:20]):
                class_name = self.imagenet_classes[int(idx)]
                mapped = self.map_imagenet_to_clothing(class_name)
                if mapped:
                    mapped_category = mapped
                    confidence = float(prob)
                    break
            
            if mapped_category:
                category = mapped_category
            else:
                # If no clothing item in top 20, fallback to top-1 overall prediction category
                category = 't-shirt'
                confidence = float(top_probs[0])
        
        # Extract colors
        colors = self.extract_colors(image)
        
        # Detect pattern
        pattern = self.detect_pattern(image)
        
        # Detect style
        style = self.detect_style(image, category)
        
        # Detect aesthetics using the dynamic service
        try:
            from services.aesthetic_service import get_item_aesthetics
        except ImportError:
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
            from services.aesthetic_service import get_item_aesthetics
            
        aesthetics = get_item_aesthetics({
            'category': category,
            'color_primary': colors[0] if colors else '',
            'pattern': pattern,
            'style': style
        })
        
        return {
            'category': category,
            'confidence': confidence,
            'colors': colors,
            'pattern': pattern,
            'style': style,
            'aesthetics': aesthetics
        }
    
    def extract_colors(self, image, n_colors=3):
        """Extract dominant colors from image"""
        # Resize for faster processing
        image_small = image.resize((150, 150))
        img_array = np.array(image_small)
        pixels = img_array.reshape(-1, 3)
        
        # Use K-means to find dominant colors
        kmeans = KMeans(n_clusters=n_colors, random_state=42)
        kmeans.fit(pixels)
        
        colors = []
        for center in kmeans.cluster_centers_:
            # Convert RGB to hex color format (so frontend color input works perfectly!)
            hex_color = "#{:02x}{:02x}{:02x}".format(
                int(np.clip(center[0], 0, 255)),
                int(np.clip(center[1], 0, 255)),
                int(np.clip(center[2], 0, 255))
            )
            colors.append(hex_color)
        
        return colors
    
    def detect_pattern(self, image):
        """Detect if clothing has pattern (simplified)"""
        # Convert to grayscale
        gray = image.convert('L')
        img_array = np.array(gray)
        
        # Calculate local variance using a simple numpy filter
        # (avoiding scipy ndimage dependency to make loading even lighter)
        try:
            h, w = img_array.shape
            # Simple standard deviation of local patches
            std_devs = []
            for i in range(0, h-10, 20):
                for j in range(0, w-10, 20):
                    std_devs.append(np.std(img_array[i:i+10, j:j+10]))
            
            mean_std = np.mean(std_devs)
            if mean_std > 25:
                return 'patterned'
        except Exception:
            pass
            
        return 'solid'
    
    def detect_style(self, image, category):
        """Detect clothing style (simplified)"""
        if category in ['dress', 'skirt']:
            return 'formal'
        if category in ['jeans', 't-shirt']:
            return 'casual'
        return 'casual'  # Default
