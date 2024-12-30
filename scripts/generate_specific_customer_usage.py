#!/usr/bin/env python3
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import requests
import json
import uuid

def get_rate_card_models():
    """Load rate card data from CSV"""
    return pd.read_csv('../current_rate_card_rates.csv')

def generate_usage_events(customer_id, models_df, days=7):
    """
    Generate simulated usage events for the specific customer
    
    The simulation will:
    1. Generate more usage during business hours
    2. Include both input and output tokens for each model
    3. Include occasional GPU usage
    4. Generate higher volume of events
    """
    
    events = []
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get unique models
    models = models_df[models_df['model_name'].notna()]['model_name'].unique()
    
    # Generate higher volume of events for this customer
    daily_events = np.random.randint(200, 500)  # Higher number of events per day
    model_preferences = {model: np.random.uniform(0.1, 1.0) for model in models}
    gpu_usage_probability = 0.3  # 30% chance of GPU usage
    
    # Generate events for each day
    current_date = start_date
    while current_date < datetime.now(timezone.utc):
        # More events during business hours (8am-6pm UTC)
        hour = current_date.hour
        is_business_hours = 8 <= hour <= 18
        day_multiplier = 2.0 if is_business_hours else 0.5
        
        # Generate events for this hour
        hourly_events = int(daily_events * day_multiplier / 24)
        
        for _ in range(hourly_events):
            # Choose model based on preferences
            model = np.random.choice(models, p=[model_preferences[m]/sum(model_preferences.values()) for m in models])
            
            # Generate input and output tokens with higher volumes
            input_tokens = np.random.randint(500, 5000)
            output_tokens = np.random.randint(200, input_tokens)
            
            # Add input event
            timestamp = current_date + timedelta(minutes=np.random.randint(60))
            events.append({
                "transaction_id": str(uuid.uuid4()),
                "customer_id": customer_id,
                "event_type": "tokens",
                "timestamp": timestamp.isoformat(),
                "properties": {
                    "type": "input",
                    "model_name": model,
                    "count_tokens": input_tokens
                }
            })
            
            # Add output event
            events.append({
                "transaction_id": str(uuid.uuid4()),
                "customer_id": customer_id,
                "event_type": "tokens",
                "timestamp": timestamp.isoformat(),
                "properties": {
                    "type": "output",
                    "model_name": model,
                    "count_tokens": output_tokens
                }
            })
            
            # More frequent GPU usage
            if np.random.random() < gpu_usage_probability:
                gpu_type = f"gpu_type_{np.random.randint(1, 4)}"
                gpu_hours = np.random.uniform(0.5, 4.0)  # Between 30 minutes and 4 hours
                
                events.append({
                    "transaction_id": str(uuid.uuid4()),
                    "customer_id": customer_id,
                    "event_type": "gpu_usage",
                    "timestamp": timestamp.isoformat(),
                    "properties": {
                        "type": gpu_type,
                        "hours": gpu_hours
                    }
                })
        
        current_date += timedelta(hours=1)
    
    return events

def send_events_to_metronome(events, api_key):
    """Send events to Metronome API in batches"""
    url = "https://api.metronome.com/v1/ingest"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Send in batches of 100 events
    batch_size = 100
    max_retries = 3
    timeout = 10  # seconds
    
    for i in range(0, len(events), batch_size):
        batch = events[i:i + batch_size]
        batch_num = i//batch_size + 1
        total_batches = len(events)//batch_size + 1
        
        for retry in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=batch, timeout=timeout)
                response.raise_for_status()
                print(f"Successfully sent batch {batch_num}/{total_batches}")
                break
            except requests.Timeout:
                if retry < max_retries - 1:
                    print(f"Timeout sending batch {batch_num}, retrying...")
                    continue
                print(f"Failed to send batch {batch_num} after {max_retries} retries")
            except Exception as e:
                print(f"Error sending batch {batch_num}: {str(e)}")
                if hasattr(e, 'response'):
                    print(f"Response: {e.response.text}")
                break

def main():
    # Customer ID to generate usage for
    customer_id = "821ed6cd-bd57-4adb-b69b-5f073b6a7983"
    
    # Load model data
    models_df = get_rate_card_models()
    
    # Generate events
    print(f"Generating usage events for customer {customer_id}...")
    events = generate_usage_events(customer_id, models_df)
    
    # Save events to file for reference
    output_file = f'generated_usage_events_{customer_id}.json'
    with open(output_file, 'w') as f:
        json.dump(events, f, indent=2)
    print(f"Generated {len(events)} events and saved to {output_file}")
    
    # Send events to Metronome
    api_key = "48b0453c99607fb5dfb4dc717ab2d9a2b6cc0dabec7885228871bc8c42748ccf"
    print("\nSending events to Metronome...")
    send_events_to_metronome(events, api_key)

if __name__ == "__main__":
    main()