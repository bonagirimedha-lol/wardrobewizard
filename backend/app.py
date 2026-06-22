# backend/app.py
import sys
import os
# Add parent directory to sys.path so we can import 'ml' module when running locally
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, session
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from services.outfit_generator import OutfitGenerator
from services.analytics import WardrobeAnalytics
from services.weather_service import WeatherService

# Configure Flask to serve the static frontend folder
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

@app.route('/')
def index_route():
    return app.send_static_file('index.html')

# Allow all origins in dev; on Render set CORS_ORIGINS env var to your frontend URL
cors_origins = os.environ.get('CORS_ORIGINS', '*')
CORS(app, supports_credentials=True, origins=cors_origins)

from services.db_service import get_db_connection

# Database connection
def get_db():
    return get_db_connection()

# Routes
@app.route('/api/items', methods=['GET', 'POST'])
def handle_items():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # For demo purposes, we'll use a hardcoded user_id if not in session
    user_id = session.get('user_id', 1) 
    
    if request.method == 'GET':
        cur.execute("SELECT * FROM clothing_items WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        items = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(items)
    
    elif request.method == 'POST':
        data = request.json
        cur.execute("""
            INSERT INTO clothing_items 
            (user_id, name, category, subcategory, color_primary, color_secondary, 
             pattern, style, season, image_url, brand)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            user_id, data['name'], data['category'], data.get('subcategory'),
            data['color_primary'], data.get('color_secondary'),
            data.get('pattern', 'solid'), data['style'],
            data.get('season', ['all']), data['image_url'], data.get('brand')
        ))
        
        item_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'id': item_id, 'message': 'Item added successfully'})

@app.route('/api/outfits/generate', methods=['POST'])
def generate_outfits():
    """Generate outfit combinations based on user's wardrobe"""
    user_id = session.get('user_id', 1)
    data = request.json
    occasion = data.get('occasion', 'casual')
    weather = data.get('weather', {})
    aesthetic = data.get('aesthetic') # optional aesthetic parameter
    
    generator = OutfitGenerator(user_id)
    outfits = generator.generate_combinations(occasion=occasion, weather=weather, aesthetic=aesthetic, limit=12)
    
    # Segregate outfits into different aesthetics
    segregated = {}
    for outfit in outfits:
        outfit_aes = outfit.get('aesthetics', [])
        for ae in outfit_aes:
            if ae not in segregated:
                segregated[ae] = []
            segregated[ae].append(outfit)
            
    return jsonify({
        'all': outfits,
        'segregated': segregated
    })

@app.route('/api/analytics/wardrobe', methods=['GET'])
def wardrobe_analytics():
    """Get wardrobe analytics and insights"""
    user_id = session.get('user_id', 1)
    analytics = WardrobeAnalytics(user_id)
    
    return jsonify({
        'most_worn': analytics.get_most_worn(10),
        'unused_items': analytics.get_unused_items(30),
        'color_distribution': analytics.get_color_distribution(),
        'category_breakdown': analytics.get_category_breakdown(),
        'gaps': analytics.identify_gaps()
    })

@app.route('/api/weather', methods=['GET'])
def get_weather():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if not lat or not lon:
        return jsonify({'error': 'Missing coordinates'}), 400
    
    weather_service = WeatherService()
    weather = weather_service.get_weather(lat, lon)
    return jsonify(weather)

@app.route('/api/analyze-clothing', methods=['POST'])
def analyze_clothing():
    import uuid
    from ml.clothing_classifier import ClothingClassifier
    
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    image = request.files['image']
    
    # Create uploads directory if not exists
    uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend/uploads'))
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Generate unique filename
    file_ext = os.path.splitext(image.filename)[1] or '.jpg'
    filename = f"{uuid.uuid4()}{file_ext}"
    image_path = os.path.join(uploads_dir, filename)
    
    # Save image
    image.save(image_path)
    
    classifier = ClothingClassifier()
    analysis = classifier.classify_item(image_path)
    
    analysis['image_url'] = f"/uploads/{filename}"
    analysis['image_path'] = image_path
    
    return jsonify(analysis)

# --- USER AUTHENTICATION ROUTES ---

@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not username or not email or not password:
        return jsonify({'error': 'Missing required fields'}), 400
        
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check if username or email exists
    cur.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({'error': 'Username or Email already registered'}), 400
        
    password_hash = generate_password_hash(password)
    cur.execute("""
        INSERT INTO users (username, email, password_hash)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (username, email, password_hash))
    
    user_id = cur.fetchone()['id']
    conn.commit()
    cur.close()
    conn.close()
    
    session['user_id'] = user_id
    session['username'] = username
    
    return jsonify({'id': user_id, 'username': username, 'message': 'Registration successful'})

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.json
    login_id = data.get('username')  # can be username or email
    password = data.get('password')
    
    if not login_id or not password:
        return jsonify({'error': 'Missing credentials'}), 400
        
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT id, username, password_hash FROM users WHERE username = %s OR email = %s", (login_id, login_id))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid username or password'}), 401
        
    session['user_id'] = user['id']
    session['username'] = user['username']
    
    return jsonify({'id': user['id'], 'username': user['username'], 'message': 'Login successful'})

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'logged_in': False})
        
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, username, email, style_preferences, created_at FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if not user:
        return jsonify({'logged_in': False})
        
    user['logged_in'] = True
    return jsonify(user)

# --- ML FEEDBACK LOOP ROUTES ---

@app.route('/api/feedback', methods=['POST'])
def add_feedback():
    data = request.json
    user_id = session.get('user_id', 1) # Fallback to default user
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        INSERT INTO feedbacks 
        (user_id, image_path, predicted_category, corrected_category, 
         predicted_color, corrected_color, rating, comment)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        user_id, data.get('image_path'), data.get('predicted_category'), data.get('corrected_category'),
        data.get('predicted_color'), data.get('corrected_color'),
        data.get('rating', 5), data.get('comment', '')
    ))
    
    feedback_id = cur.fetchone()['id']
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'id': feedback_id, 'message': 'Feedback successfully saved'})

@app.route('/api/feedback/stats', methods=['GET'])
def feedback_stats():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT COUNT(*) as total_feedback, AVG(rating) as avg_rating FROM feedbacks")
    stats = cur.fetchone()
    
    cur.execute("SELECT COUNT(*) as pending_training FROM feedbacks WHERE corrected_category IS NOT NULL AND used_for_training = 0")
    pending = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return jsonify({
        'total_feedback': stats['total_feedback'] or 0,
        'avg_rating': round(stats['avg_rating'], 2) if stats['avg_rating'] else 5.0,
        'pending_training': pending['pending_training'] or 0
    })

@app.route('/api/model/train', methods=['POST'])
def trigger_training():
    from ml.trainer import train_model
    try:
        res = train_model()
        return jsonify(res)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
