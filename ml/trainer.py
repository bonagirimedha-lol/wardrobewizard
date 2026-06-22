# ml/trainer.py
import os
import sqlite3
import torch
import torchvision.transforms as transforms
from torchvision.models import resnet18, ResNet18_Weights
from PIL import Image
import torch.optim as optim
import torch.nn as nn

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'wardrobewizard.db')
MODEL_SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wardrobe_model.pth')

WARDROBE_TO_IMAGENET = {
    't-shirt': 610,    # jersey, T-shirt
    'jeans': 608,      # jean, blue jean, denim
    'dress': 579,      # gown
    'jacket': 860,     # trench coat
    'shoes': 770,      # running shoe
    'hat': 515,        # cowboy hat
    'scarf': 848,      # stole
    'skirt': 653,      # miniskirt
    'shorts': 841,     # trunks, swimming trunks
    'sweater': 479     # cardigan
}

def train_model():
    """Fine-tune the ResNet18 model on corrected user feedback images"""
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return {"status": "error", "message": "Database not found."}
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Get feedbacks that have a corrected category and haven't been used for training yet
    cur.execute("""
        SELECT id, image_path, corrected_category 
        FROM feedbacks 
        WHERE corrected_category IS NOT NULL AND used_for_training = 0
    """)
    rows = cur.fetchall()
    
    if not rows:
        conn.close()
        print("No new training data available.")
        return {"status": "success", "message": "No new training data available."}
        
    print(f"Found {len(rows)} new training sample(s). Preparing dataset...")
    
    # Prepare training samples
    training_data = []
    preprocess = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    feedback_ids = []
    for fid, image_path, corrected_cat in rows:
        if not image_path or not os.path.exists(image_path):
            print(f"Skipping: Image path {image_path} does not exist.")
            continue
            
        target_class = WARDROBE_TO_IMAGENET.get(corrected_cat)
        if target_class is None:
            print(f"Skipping: Category '{corrected_cat}' has no ImageNet mapping.")
            continue
            
        try:
            image = Image.open(image_path).convert('RGB')
            tensor = preprocess(image)
            training_data.append((tensor, target_class))
            feedback_ids.append(fid)
        except Exception as e:
            print(f"Error loading image {image_path}: {e}")
            
    if not training_data:
        conn.close()
        print("No valid training samples loaded.")
        return {"status": "error", "message": "No valid training samples loaded."}
        
    # Load model
    print("Loading model for fine-tuning...")
    weights = ResNet18_Weights.DEFAULT
    model = resnet18(weights=weights)
    
    # Load previously trained custom weights if they exist
    if os.path.exists(MODEL_SAVE_PATH):
        try:
            print("Loading previously saved weights...")
            model.load_state_dict(torch.load(MODEL_SAVE_PATH))
        except Exception as e:
            print(f"Error loading saved state: {e}. Starting fresh.")
            
    # Set to training mode
    model.train()
    
    # Only train the final fully connected layer + final block to speed up learning and save CPU memory
    # Freeze earlier layers
    for param in model.parameters():
        param.requires_grad = False
        
    # Unfreeze fc layer
    for param in model.fc.parameters():
        param.requires_grad = True
        
    # Unfreeze layer4 (final block) to let model adjust to custom colors/shapes
    for param in model.layer4.parameters():
        param.requires_grad = True
        
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=0.001)
    
    # Train epochs
    epochs = 5
    print(f"Fine-tuning model for {epochs} epochs...")
    for epoch in range(epochs):
        running_loss = 0.0
        for tensor, label in training_data:
            optimizer.zero_grad()
            
            inputs = tensor.unsqueeze(0) # add batch dim
            targets = torch.tensor([label])
            
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
            
        print(f"Epoch {epoch+1}/{epochs} - Loss: {running_loss / len(training_data):.4f}")
        
    # Save trained state dict
    try:
        torch.save(model.state_dict(), MODEL_SAVE_PATH)
        print(f"Model successfully saved to {MODEL_SAVE_PATH}")
    except Exception as e:
        print(f"Failed to save model: {e}")
        conn.close()
        return {"status": "error", "message": f"Failed to save model: {e}"}
        
    # Mark feedbacks as processed
    for fid in feedback_ids:
        cur.execute("UPDATE feedbacks SET used_for_training = 1 WHERE id = ?", (fid,))
        
    conn.commit()
    conn.close()
    
    return {
        "status": "success", 
        "message": f"Model fine-tuned successfully on {len(feedback_ids)} samples."
    }

if __name__ == '__main__':
    train_model()
