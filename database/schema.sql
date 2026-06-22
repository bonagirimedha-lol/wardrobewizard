-- database/schema.sql

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    style_preferences JSONB DEFAULT '{"casual": 5, "formal": 3, "athletic": 2}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Clothing items table
CREATE TABLE IF NOT EXISTS clothing_items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100),
    category VARCHAR(50) NOT NULL, -- shirt, pants, shoes, etc.
    subcategory VARCHAR(50), -- t-shirt, blouse, jeans, sneakers
    color_primary VARCHAR(30),
    color_secondary VARCHAR(30),
    pattern VARCHAR(30), -- solid, striped, floral, plaid
    style VARCHAR(30), -- casual, formal, athletic, business
    season VARCHAR(20)[], -- ['summer', 'winter', 'all']
    image_url TEXT,
    image_processed BOOLEAN DEFAULT FALSE,
    brand VARCHAR(100),
    purchase_date DATE,
    times_worn INTEGER DEFAULT 0,
    last_worn DATE,
    favorite BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Outfits table
CREATE TABLE IF NOT EXISTS outfits (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100),
    occasion VARCHAR(50), -- casual, date, interview, workout
    season VARCHAR(20),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    times_worn INTEGER DEFAULT 0,
    last_worn DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Outfit items junction table
CREATE TABLE IF NOT EXISTS outfit_items (
    outfit_id INTEGER REFERENCES outfits(id) ON DELETE CASCADE,
    item_id INTEGER REFERENCES clothing_items(id) ON DELETE CASCADE,
    position INTEGER, -- 1=top, 2=bottom, 3=shoes, 4=accessory
    PRIMARY KEY (outfit_id, item_id)
);

-- Weather preferences
CREATE TABLE IF NOT EXISTS weather_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    weather_condition VARCHAR(50), -- rain, snow, hot, cold
    preference TEXT -- 'avoid', 'perfect', 'layer'
);

-- Shopping suggestions
CREATE TABLE IF NOT EXISTS shopping_suggestions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    category VARCHAR(50),
    reason TEXT,
    priority INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
