# backend/services/analytics.py
import os
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor
from services.db_service import get_db_connection

class WardrobeAnalytics:
    def __init__(self, user_id):
        self.user_id = user_id
        self.conn = get_db_connection()
    
    def get_most_worn(self, limit=10):
        """Get the most worn items"""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT name, category, times_worn, image_url 
            FROM clothing_items 
            WHERE user_id = %s 
            ORDER BY times_worn DESC 
            LIMIT %s
        """, (self.user_id, limit))
        results = cur.fetchall()
        cur.close()
        return results
    
    def get_unused_items(self, days=30):
        """Get items not worn for a certain number of days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT name, category, last_worn, image_url 
            FROM clothing_items 
            WHERE user_id = %s AND (last_worn < %s OR last_worn IS NULL)
        """, (self.user_id, cutoff_date))
        results = cur.fetchall()
        cur.close()
        return results
    
    def get_color_distribution(self):
        """Get the distribution of primary colors"""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT color_primary, COUNT(*) as count 
            FROM clothing_items 
            WHERE user_id = %s 
            GROUP BY color_primary
        """, (self.user_id,))
        results = {row['color_primary']: row['count'] for row in cur.fetchall() if row['color_primary']}
        cur.close()
        return results
    
    def get_category_breakdown(self):
        """Get the breakdown of items by category"""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT category, COUNT(*) as count 
            FROM clothing_items 
            WHERE user_id = %s 
            GROUP BY category
        """, (self.user_id,))
        results = {row['category']: row['count'] for row in cur.fetchall()}
        cur.close()
        return results
    
    def identify_gaps(self):
        """Identify gaps in the wardrobe"""
        categories = self.get_category_breakdown()
        gaps = []
        
        # Simple logic for common gaps
        if categories.get('shoes', 0) < 2:
            gaps.append({'reason': 'Missing shoe variety', 'priority': 5})
        if categories.get('jacket', 0) < 1:
            gaps.append({'reason': 'Missing outerwear', 'priority': 4})
        if categories.get('shirt', 0) < 3 and categories.get('t-shirt', 0) < 3:
            gaps.append({'reason': 'Low on tops', 'priority': 3})
            
        return gaps

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
