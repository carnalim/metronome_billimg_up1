import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import requests
import json

def get_customers():
    """Load customer data from CSV"""
    # Only get the first 10 customers to make it manageable
    return pd.read_csv('../recent_customers.csv').head(10)

def get_rate_card_models():
    """Load rate card data from CSV"""
    return pd.read_csv('../current_rate_card_rates.csv')

def generate_usage_events(customers_df, models_df, days=7):
    """
    Generate simulated usage events for each customer
    
    The simulation will:
    1. Generate more usage during business hours
    2. Have some variation between customers
    3. Include both input and output tokens for each model
    4. Include occasional GPU usage
    """
    
    events = []
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get unique models (excluding GPU types)
    models = models_df[models_df['model_name'].notna()]['model_name'].unique()
    
    # Get GPU types
    gpu_types = models_df[models_df['type'].str.startswith('gpu_type_', na=False)]['type'].unique()
    
    for _, customer in customers_df.iterrows():
        # Assign random usage patterns to this customer
        daily_events = np.random.randint(10, 30)  # Events per day - reduced for testing
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
                
                # Add input event
                timestamp = current_date + timedelta(minutes=np.random.randint(60))
                events.append({
                    'transaction_id': f"{timestamp.isoformat()}_{customer['customer_id']}_{model}_input",
                    'customer_id': customer['customer_id'],
                    'event_type': 'token_usage',
                    'timestamp': timestamp.isoformat(),
                    'properties': {
                        'type': 'input',
                        'model_name': model,
                        'token_count': input_tokens
                    }
                })
                
                # Add output event
                events.append({
                    'transaction_id': f"{timestamp.isoformat()}_{customer['customer_id']}_{model}_output",
                    'customer_id': customer['customer_id'],
                    'event_type': 'token_usage',
                    'timestamp': timestamp.isoformat(),
                    'properties': {
                        'type': 'output',
                        'model_name': model,
                        'token_count': output_tokens
                    }
                })
                
                # Occasionally add GPU usage
                if np.random.random() < gpu_usage_probability:
                    gpu_type = f"gpu_type_{np.random.randint(1, 4)}"
                    gpu_hours = np.random.uniform(0.1, 2.0)  # Between 6 minutes and 2 hours
                    
                    events.append({
                        'transaction_id': f"{timestamp.isoformat()}_{customer['customer_id']}_{gpu_type}",
                        'customer_id': customer['customer_id'],
                        'event_type': 'gpu_usage',
                        'timestamp': timestamp.isoformat(),
                        'properties': {
                            'type': gpu_type,
                            'hours': gpu_hours
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
    # Load data
    customers_df = get_customers()
    models_df = get_rate_card_models()
    
    # Generate events
    print("Generating usage events...")
    events = generate_usage_events(customers_df, models_df)
    
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