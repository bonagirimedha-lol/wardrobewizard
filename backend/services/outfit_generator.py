# backend/services/outfit_generator.py
import random
from datetime import datetime
import os
from psycopg2.extras import RealDictCursor
from services.db_service import get_db_connection
from services.aesthetic_service import get_item_aesthetics, get_outfit_aesthetics

class OutfitGenerator:
    def __init__(self, user_id):
        self.user_id = user_id
        self.conn = get_db_connection()
    
    def get_user_items(self):
        """Fetch all user's clothing items"""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM clothing_items 
            WHERE user_id = %s
        """, (self.user_id,))
        items = cur.fetchall()
        cur.close()
        return items
    
    def generate_combinations(self, occasion='casual', weather=None, aesthetic=None, limit=5):
        """Generate outfit combinations"""
        items = self.get_user_items()
        
        # If aesthetic is specified, filter items to only those matching that aesthetic
        if aesthetic:
            items = [i for i in items if aesthetic in get_item_aesthetics(i)]
        
        # Separate items by category
        tops = [i for i in items if i['category'] in ['shirt', 't-shirt', 'blouse']]
        bottoms = [i for i in items if i['category'] in ['pants', 'jeans', 'skirt']]
        shoes = [i for i in items if i['category'] == 'shoes']
        outerwear = [i for i in items if i['category'] == 'jacket']
        
        outfits = []
        
        # Attempt to generate unique combinations (up to 60 iterations)
        attempts = 0
        while len(outfits) < limit and attempts < 60:
            attempts += 1
            outfit = {
                'items': [],
                'occasion': occasion,
                'weather_suitability': 1.0,
                'aesthetics': []
            }
            
            # Select items based on occasion and weather
            if tops:
                top = self.select_item(tops, occasion, weather)
                outfit['items'].append(top)
            
            if bottoms:
                bottom = self.select_item(bottoms, occasion, weather)
                outfit['items'].append(bottom)
            
            if shoes:
                shoe = self.select_item(shoes, occasion, weather)
                outfit['items'].append(shoe)
            
            # Add outerwear if weather appropriate
            if weather and weather.get('temp', 20) < 15 and outerwear:
                jacket = self.select_item(outerwear, occasion, weather)
                outfit['items'].append(jacket)
            
            # Check if outfit follows fashion rules
            if self.is_valid_outfit(outfit['items']):
                outfit['aesthetics'] = get_outfit_aesthetics(outfit['items'])
                # Ensure the outfit matches requested aesthetic (it should, but safety first)
                if aesthetic and aesthetic not in outfit['aesthetics']:
                    continue
                # Avoid duplicates
                outfit_ids = sorted([item['id'] for item in outfit['items']])
                if not any(sorted([item['id'] for item in existing['items']]) == outfit_ids for existing in outfits):
                    outfits.append(outfit)
            elif len(outfits) < 1 and len(outfit['items']) > 0:
                # Fallback for small wardrobes
                outfit['aesthetics'] = get_outfit_aesthetics(outfit['items'])
                if aesthetic and aesthetic not in outfit['aesthetics']:
                    continue
                outfits.append(outfit)
        
        return outfits
    
    def select_item(self, items, occasion, weather):
        """Select appropriate item based on occasion and weather"""
        # Filter by occasion
        occasion_filtered = [i for i in items if i['style'] == occasion]
        if not occasion_filtered:
            occasion_filtered = items
        
        # Filter by weather if provided
        if weather:
            temp = weather.get('temp', 20)
            weather_filtered = []
            for item in occasion_filtered:
                season = item.get('season') or ['all']
                # Check if item is appropriate for temperature
                if temp > 25 and 'summer' in season:
                    weather_filtered.append(item)
                elif temp < 10 and 'winter' in season:
                    weather_filtered.append(item)
                elif 10 <= temp <= 25:
                    weather_filtered.append(item)
            
            if weather_filtered:
                return random.choice(weather_filtered)
        
        return random.choice(occasion_filtered)
    
    def is_valid_outfit(self, items):
        """Check if outfit follows fashion rules"""
        if len(items) < 2:
            return False
        
        # Rule 1: No clashing patterns (simplified)
        patterns = [item.get('pattern', 'solid') for item in items]
        if patterns.count('patterned') > 1:
            return False
        
        # Rule 2: Style consistency
        styles = [item.get('style', 'casual') for item in items]
        if len(set(styles)) > 1 and 'casual' in styles:
            # Allow one casual item with formal
            if styles.count('formal') > 1 and 'casual' in styles:
                return False
        
        # Rule 3: Color harmony (simplified - avoid same color top and bottom)
        colors = [item.get('color_primary') for item in items]
        if len(colors) >= 2 and colors[0] == colors[1] and colors[0] is not None:
            return False
        
        return True

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
