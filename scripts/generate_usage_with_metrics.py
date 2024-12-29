import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import requests
import json
import uuid

def get_customers():
    """Load customer data from CSV"""
    return pd.read_csv('new_customer_data.csv')

def get_rate_card_models():
    """Load rate card data from CSV"""
    return pd.read_csv('current_rate_card_rates.csv')

def generate_usage_events(customers_df, models_df, days=7):
    """
    Generate simulated usage events for each customer matching the billable metrics:
    
    1. Tokens metric:
       - event_type: 'tokens'
       - group_keys: ['type', 'model_name']
       - properties: count_tokens, type (input/output), model_name
    
    2. GPU metric:
       - event_type: 'gpu'
       - group_keys: ['type']
       - properties: count_seconds, type (gpu_type_X)
    
    The simulation includes:
    1. More usage during business hours
    2. Variation between customers
    3. Both input and output tokens for each model
    4. Occasional GPU usage
    """
    
    events = []
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get unique models (excluding GPU types)
    models = models_df[models_df['model_name'].notna()]['model_name'].unique()
    
    # Get GPU types
    gpu_types = models_df[models_df['type'].str.startswith('gpu_type_', na=False)]['type'].unique()
    
    for _, customer in customers_df.iterrows():
        # Assign random usage patterns to this customer
        daily_events = np.random.randint(50, 200)  # Events per day
        model_preferences = {model: np.random.uniform(0.1, 1.0) for model in models}
        gpu_usage_probability = np.random.uniform(0.05, 0.2)  # 5-20% chance of GPU usage
        
        # Generate events for each day
        current_date = start_date
        while current_date < datetime.now(timezone.utc):
            # More events during business hours (8am-6pm UTC)
            hour = current_date.hour
            is_business_hours = 8 <= hour <= 18
            day_multiplier = 1.5 if is_business_hours else 0.5
            
            # Generate events for this hour
            hourly_events = int(daily_events * day_multiplier / 24)
            
            for _ in range(hourly_events):
                # Choose model based on preferences
                model = np.random.choice(models, p=[model_preferences[m]/sum(model_preferences.values()) for m in models])
                
                # Generate input and output tokens
                input_tokens = np.random.randint(100, 2000)
                output_tokens = np.random.randint(50, input_tokens)  # Output is generally smaller than input
                
                # Generate unique transaction ID
                transaction_id = str(uuid.uuid4())
                timestamp = current_date + timedelta(minutes=np.random.randint(60))
                
                # Add input event
                events.append({
                    'transaction_id': transaction_id,
                    'customer_id': customer['customer_id'],
                    'event_type': 'tokens',
                    'timestamp': timestamp.isoformat(),
                    'properties': {
                        'type': 'input',
                        'model_name': model,
                        'count_tokens': input_tokens
                    }
                })
                
                # Add output event with same transaction ID
                events.append({
                    'transaction_id': transaction_id,
                    'customer_id': customer['customer_id'],
                    'event_type': 'tokens',
                    'timestamp': timestamp.isoformat(),
                    'properties': {
                        'type': 'output',
                        'model_name': model,
                        'count_tokens': output_tokens
                    }
                })
                
                # Occasionally add GPU usage
                if np.random.random() < gpu_usage_probability:
                    gpu_type = f"gpu_type_{np.random.randint(1, 4)}"
                    gpu_seconds = int(np.random.uniform(360, 7200))  # Between 6 minutes and 2 hours in seconds
                    
                    events.append({
                        'transaction_id': str(uuid.uuid4()),
                        'customer_id': customer['customer_id'],
                        'event_type': 'gpu',
                        'timestamp': timestamp.isoformat(),
                        'properties': {
                            'type': gpu_type,
                            'count_seconds': gpu_seconds
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

def validate_events(events):
    """
    Validate that events match the billable metrics configuration:
    1. Tokens events have all required properties
    2. GPU events have all required properties
    """
    for event in events:
        if event['event_type'] == 'tokens':
            assert 'type' in event['properties'], "Token event missing 'type' property"
            assert event['properties']['type'] in ['input', 'output'], "Token event 'type' must be 'input' or 'output'"
            assert 'model_name' in event['properties'], "Token event missing 'model_name' property"
            assert 'count_tokens' in event['properties'], "Token event missing 'count_tokens' property"
            assert isinstance(event['properties']['count_tokens'], int), "count_tokens must be an integer"
        elif event['event_type'] == 'gpu':
            assert 'type' in event['properties'], "GPU event missing 'type' property"
            assert event['properties']['type'].startswith('gpu_type_'), "GPU event 'type' must start with 'gpu_type_'"
            assert 'count_seconds' in event['properties'], "GPU event missing 'count_seconds' property"
            assert isinstance(event['properties']['count_seconds'], int), "count_seconds must be an integer"

def main():
    # Load data
    customers_df = get_customers()
    models_df = get_rate_card_models()
    
    # Generate events
    print("Generating usage events...")
    events = generate_usage_events(customers_df, models_df)
    
    # Validate events match billable metrics configuration
    print("Validating events...")
    validate_events(events)
    
    # Save events to file for reference
    with open('generated_usage_events.json', 'w') as f:
        json.dump(events, f, indent=2)
    print(f"Generated {len(events)} events and saved to generated_usage_events.json")
    
    # Send events to Metronome
    api_key = "e940e56fd5d98819bd3870adee8f163fa0e3c6429e9bb19290e65d9888b492df"
    print("\nSending events to Metronome...")
    send_events_to_metronome(events, api_key)

if __name__ == "__main__":
    main()