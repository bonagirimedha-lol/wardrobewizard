# backend/services/aesthetic_service.py
import numpy as np

AESTHETICS_LIST = [
    "Clean Girl",
    "Y2K",
    "Quiet Luxury / Old Money",
    "Coquette Core",
    "Cottagecore",
    "Neo Deco / Retro Glam",
    "Dark Academia",
    "Coastal Cowgirl",
    "Gummy / Jelly Aesthetic",
    "Indie Sleaze / Grunge Revival"
]

def hex_to_rgb(hex_str):
    if not hex_str:
        return (128, 128, 128)
    hex_str = hex_str.lstrip('#')
    if len(hex_str) != 6:
        return (128, 128, 128)
    try:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return (128, 128, 128)

def classify_color(rgb):
    r, g, b = rgb
    # Determine color classification
    # 1. Jet Black / Distressed Dark
    if r < 50 and g < 50 and b < 50:
        return "black"
    # 2. Pure White / Off-White
    if r > 230 and g > 230 and b > 220:
        return "white"
    # 3. Warm Earth Tones (Autumnal Browns, Burnt Oranges, Tans)
    if r > 100 and g > 40 and b < 80 and abs(r - g) > 20:
        if g > 110:
            return "camel_beige"
        return "burnt_orange_brown"
    # 4. Pastel Pink & Soft Pastels
    if r > 200 and g > 170 and b > 180:
        if r - g > 15 and r - b > 15:
            return "pastel_pink"
        return "pastel"
    # 5. Forest Green / Academic Navy / Dark Brown
    if (g > 60 and r < 80 and b < 85 and g > r) or (b > 80 and r < 70 and g < 90) or (r > 60 and r < 120 and g < 80 and b < 60):
        return "academic_dark"
    # 6. Metallics / Shiny Silver / Gold
    if abs(r - g) < 15 and abs(g - b) < 15 and r > 150:
        return "metallic"
    # 7. Bright/Neon Gummy Color
    if max(r, g, b) > 180 and min(r, g, b) < 120:
        return "bright"
        
    return "neutral"

def get_item_aesthetics(item):
    """Categorize a clothing item into a list of the 10 target aesthetics based on elements"""
    aesthetics = []
    
    category = (item.get('category') or '').lower()
    color_hex = item.get('color_primary') or ''
    pattern = (item.get('pattern') or 'solid').lower()
    style = (item.get('style') or 'casual').lower()
    
    rgb = hex_to_rgb(color_hex)
    color_type = classify_color(rgb)
    
    # 1. Clean Girl
    # Minimalist, wellness, matching sets, activewear, solid neutrals
    if pattern == 'solid' and color_type in ['white', 'neutral', 'camel_beige'] and style in ['athletic', 'casual']:
        aesthetics.append("Clean Girl")
    elif category in ['shorts', 'pants', 't-shirt'] and style == 'athletic' and pattern == 'solid':
        aesthetics.append("Clean Girl")

    # 2. Y2K
    # Baby tees, glitter graphics, metallic textures, platform styles, futuristic elements
    if color_type == 'metallic' or color_hex.lower() in ['#ff00ff', '#00ffff', '#c0c0c0']:
        aesthetics.append("Y2K")
    elif category in ['t-shirt', 'jeans', 'skirt', 'hat'] and pattern in ['patterned', 'striped'] and style == 'casual':
        aesthetics.append("Y2K")

    # 3. Quiet Luxury / Old Money
    # Trench coats, tailored trousers, cashmere sweaters, neutral solids, loafers
    if pattern == 'solid' and color_type in ['white', 'camel_beige', 'neutral'] and style in ['formal', 'business']:
        aesthetics.append("Quiet Luxury / Old Money")
    elif category in ['pants', 'jacket', 'sweater', 'shirt'] and style in ['formal', 'business'] and color_type != 'bright':
        aesthetics.append("Quiet Luxury / Old Money")

    # 4. Coquette Core
    # Romantic, ribbons, pastel pink, lace details, skirts
    if color_type == 'pastel_pink' or color_hex.lower() in ['#ffc0cb', '#ffb6c1', '#ffe4e1']:
        aesthetics.append("Coquette Core")
    elif category in ['dress', 'skirt', 'sweater'] and pattern in ['floral', 'patterned'] and color_type in ['pastel', 'white']:
        aesthetics.append("Coquette Core")

    # 5. Cottagecore
    # Slow-living, flowing dresses, floral, knitted cardigans, straw hats
    if category in ['dress', 'skirt', 'sweater', 'hat'] and pattern in ['floral', 'plaid']:
        aesthetics.append("Cottagecore")
    elif category in ['dress', 'skirt'] and color_type in ['camel_beige', 'pastel'] and style == 'casual':
        aesthetics.append("Cottagecore")

    # 6. Neo Deco / Retro Glam
    # 70s autumnal warm tones, velvet textures, geometric silhouettes
    if color_type == 'burnt_orange_brown' or color_hex.lower() in ['#d2691e', '#cd853f', '#b8860b']: # chocolate, sienna, goldenrod
        aesthetics.append("Neo Deco / Retro Glam")
    elif category in ['jacket', 'dress', 'pants'] and pattern == 'patterned' and style in ['formal', 'casual']:
        aesthetics.append("Neo Deco / Retro Glam")

    # 7. Dark Academia
    # Tweed blazers, pleated plaid skirts, brown/forest green/black, literature mood
    if color_type == 'academic_dark' or (category in ['jacket', 'skirt', 'sweater'] and color_type == 'black'):
        aesthetics.append("Dark Academia")
    elif category in ['jacket', 'skirt', 'sweater'] and pattern == 'plaid' and color_type in ['burnt_orange_brown', 'academic_dark']:
        aesthetics.append("Dark Academia")

    # 8. Coastal Cowgirl
    # Cowboy boots, white linen dresses, denim skirts, crocheted/knitted tops
    if category in ['dress', 'skirt'] and color_type == 'white':
        aesthetics.append("Coastal Cowgirl")
    elif category == 'jeans' and color_type in ['neutral', 'pastel'] and style == 'casual': # blue denim
        aesthetics.append("Coastal Cowgirl")
    elif category == 'shoes' and color_type in ['burnt_orange_brown', 'camel_beige']: # brown leather boot
        aesthetics.append("Coastal Cowgirl")

    # 9. Gummy / Jelly Aesthetic
    # Childhood nostalgia, bright gel/translucent colors, high-gloss look
    if color_type == 'bright' or color_hex.lower() in ['#ff1493', '#adff2f', '#00ff00', '#ffff00']: # neon pink, green, yellow
        aesthetics.append("Gummy / Jelly Aesthetic")
    elif category in ['shoes', 'hat', 't-shirt'] and pattern == 'patterned' and color_type == 'bright':
        aesthetics.append("Gummy / Jelly Aesthetic")

    # 10. Indie Sleaze / Grunge Revival
    # Messy, band tees, distressed leather, heavy black/gray
    if color_type == 'black' and category in ['jacket', 't-shirt', 'jeans', 'shoes']:
        aesthetics.append("Indie Sleaze / Grunge Revival")
    elif category == 't-shirt' and pattern in ['patterned', 'striped'] and color_type in ['black', 'neutral']:
        aesthetics.append("Indie Sleaze / Grunge Revival")

    # Fallbacks: If none matched, fall back to best style match
    if not aesthetics:
        if style in ['formal', 'business']:
            aesthetics.append("Quiet Luxury / Old Money")
        elif style == 'athletic':
            aesthetics.append("Clean Girl")
        else:
            aesthetics.append("Minimalist / Clean Girl" if "Minimalist / Clean Girl" in AESTHETICS_LIST else "Clean Girl")
            
    return aesthetics

def get_outfit_aesthetics(outfit_items):
    """Determine the aesthetics of an outfit based on its items"""
    if not outfit_items:
        return ["Clean Girl"]
        
    aesthetic_counts = {}
    for item in outfit_items:
        item_aesthetics = get_item_aesthetics(item)
        for ae in item_aesthetics:
            aesthetic_counts[ae] = aesthetic_counts.get(ae, 0) + 1
            
    if not aesthetic_counts:
        return ["Clean Girl"]
        
    # Find aesthetics with the highest counts
    max_count = max(aesthetic_counts.values())
    dominant_aesthetics = [ae for ae, count in aesthetic_counts.items() if count == max_count]
    return dominant_aesthetics
