# backend/services/weather_service.py
import requests
import os
from datetime import datetime

class WeatherService:
    def __init__(self):
        self.api_key = os.environ.get('OPENWEATHER_API_KEY')
        self.base_url = "http://api.openweathermap.org/data/2.5"
    
    def get_weather(self, lat, lon):
        """Get current weather for location"""
        if not self.api_key:
            # Fallback to free Open-Meteo API (requires NO API key)
            try:
                url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
                response = requests.get(url, timeout=5)
                data = response.json()
                current = data.get('current_weather', {})
                temp = current.get('temperature', 20.0)
                code = current.get('weathercode', 0)
                
                # Map WMO weathercode to OpenWeather-style main/description
                main_cond = "Clear"
                desc = "clear sky"
                if code in [1, 2, 3]:
                    main_cond = "Clouds"
                    desc = "partly cloudy"
                elif code in [45, 48]:
                    main_cond = "Fog"
                    desc = "foggy"
                elif code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]:
                    main_cond = "Rain"
                    desc = "rain"
                elif code in [71, 73, 75, 77, 85, 86]:
                    main_cond = "Snow"
                    desc = "snow"
                elif code in [95, 96, 99]:
                    main_cond = "Thunderstorm"
                    desc = "thunderstorm"
                
                return {
                    'main': {'temp': temp},
                    'weather': [{'main': main_cond, 'description': desc}]
                }
            except Exception as e:
                print(f"Open-Meteo fallback error: {e}")
                # Mock response if offline or failed
                return {
                    'main': {'temp': 20.0},
                    'weather': [{'main': 'Clear', 'description': 'clear sky'}]
                }

        url = f"{self.base_url}/weather"
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric'
        }
        
        response = requests.get(url, params=params)
        return response.json()
    
    def get_forecast(self, lat, lon, days=5):
        """Get weather forecast"""
        if not self.api_key:
            return {'list': []}
        url = f"{self.base_url}/forecast"
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric',
            'cnt': days * 8  # 8 forecasts per day
        }
        
        response = requests.get(url, params=params)
        return response.json()
    
    def get_outfit_recommendations(self, weather):
        """Get outfit recommendations based on weather"""
        temp = weather['main']['temp']
        condition = weather['weather'][0]['main'].lower()
        
        recommendations = {
            'temperature_advice': '',
            'weather_advice': '',
            'suggested_items': []
        }
        
        # Temperature based advice
        if temp > 25:
            recommendations['temperature_advice'] = "It's hot! Wear lightweight, breathable fabrics."
            recommendations['suggested_items'].extend(['t-shirt', 'shorts', 'sundress', 'sandals'])
        elif temp < 10:
            recommendations['temperature_advice'] = "It's cold! Layer up with warm clothing."
            recommendations['suggested_items'].extend(['sweater', 'jacket', 'boots', 'scarf'])
        else:
            recommendations['temperature_advice'] = "Mild weather - comfortable for most outfits."
            recommendations['suggested_items'].extend(['jeans', 'long-sleeve shirt', 'light jacket'])
        
        # Weather condition based advice
        if 'rain' in condition:
            recommendations['weather_advice'] = "Rain expected - bring waterproof items."
            recommendations['suggested_items'].extend(['raincoat', 'umbrella', 'waterproof boots'])
        elif 'snow' in condition:
            recommendations['weather_advice'] = "Snow expected - wear warm, waterproof items."
            recommendations['suggested_items'].extend(['winter coat', 'snow boots', 'hat', 'gloves'])
        elif 'clear' in condition:
            recommendations['weather_advice'] = "Clear skies - perfect for any outfit!"
        
        return recommendations
