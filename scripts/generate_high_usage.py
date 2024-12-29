import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import requests
import json
import time

def get_rate_card_models():
    """Load rate card data from CSV"""
    return pd.read_csv('current_rate_card_rates.csv')

def get_token_price(model_name, token_type):
    """Get price per token based on model and type"""
    # Define base prices in dollars per 1000 tokens
    prices = {
        'gpt4-o': {'input': 0.03, 'output': 0.06},
        'claude-3.5-sonnet': {'input': 0.02, 'output': 0.04},
        'gemini-1.5-flash-8B': {'input': 0.01, 'output': 0.03}
    }
    
    # Find matching model (partial match)
    for model in prices:
        if model in model_name.lower():
            return prices[model][token_type]
    
    # Default price if no match
    return prices['claude-3.5-sonnet'][token_type]

def get_gpu_price(gpu_type):
    """Get price per hour for GPU usage"""
    # Define GPU prices in dollars per hour
    prices = {
        'gpu_type_1': 0.80,  # Basic GPU
        'gpu_type_2': 1.60,  # Advanced GPU
        'gpu_type_3': 2.40   # Premium GPU
    }
    return prices.get(gpu_type, 0.80)

def generate_intensive_usage(customer_id, models_df, days=7):
    """
    Generate intensive usage events for a specific customer
    
    The simulation will generate:
    1. Very high token usage across all models with associated costs
    2. Heavy GPU utilization with hourly rates
    3. Consistent usage patterns with peak hours
    4. Large batch processing simulations
    """
    events = []
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get unique models (excluding GPU types)
    models = models_df[models_df['model_name'].notna()]['model_name'].unique()
    
    # Get GPU types
    gpu_types = models_df[models_df['type'].str.startswith('gpu_type_', na=False)]['type'].unique()
    
    # Define usage patterns
    hourly_base_events = 500  # Base events per hour
    batch_processing_hours = [1, 9, 14, 20]  # Hours when batch processing occurs
    
    current_date = start_date
    while current_date < datetime.now(timezone.utc):
        hour = current_date.hour
        is_business_hours = 8 <= hour <= 18
        is_batch_hour = hour in batch_processing_hours
        
        # Calculate number of events for this hour
        if is_batch_hour:
            hourly_events = hourly_base_events * 5  # 5x during batch processing
        elif is_business_hours:
            hourly_events = hourly_base_events * 2  # 2x during business hours
        else:
            hourly_events = hourly_base_events
            
        # Generate events for each model
        for model in models:
            # Base tokens for this model
            base_input_tokens = 2000 if 'gpt4' in model else 1500
            
            for _ in range(hourly_events):
                # Add random variation to token counts
                input_tokens = int(base_input_tokens * np.random.uniform(0.8, 1.5))
                output_tokens = int(input_tokens * np.random.uniform(0.6, 1.2))
                
                timestamp = current_date + timedelta(minutes=np.random.randint(60))
                
                # Calculate costs
                input_price = get_token_price(model, 'input')
                output_price = get_token_price(model, 'output')
                input_cost = (input_tokens / 1000) * input_price
                output_cost = (output_tokens / 1000) * output_price
                
                # Input event
                events.append({
                    'transaction_id': f"{timestamp.isoformat()}_{customer_id}_{model}_input",
                    'customer_id': customer_id,
                    'event_type': 'token_usage',
                    'timestamp': timestamp.isoformat(),
                    'properties': {
                        'type': 'input',
                        'model_name': model,
                        'token_count': input_tokens,
                        'price_per_1k_tokens': input_price,
                        'cost_usd': input_cost
                    }
                })
                
                # Output event
                events.append({
                    'transaction_id': f"{timestamp.isoformat()}_{customer_id}_{model}_output",
                    'customer_id': customer_id,
                    'event_type': 'token_usage',
                    'timestamp': timestamp.isoformat(),
                    'properties': {
                        'type': 'output',
                        'model_name': model,
                        'token_count': output_tokens,
                        'price_per_1k_tokens': output_price,
                        'cost_usd': output_cost
                    }
                })
        
        # Generate GPU usage
        gpu_usage_events = hourly_events // 10  # 10% of events use GPU
        for _ in range(gpu_usage_events):
            gpu_type = np.random.choice(gpu_types)
            gpu_hours = np.random.uniform(0.5, 4.0)  # Between 30 minutes and 4 hours
            
            timestamp = current_date + timedelta(minutes=np.random.randint(60))
            # Calculate GPU cost
            gpu_price = get_gpu_price(gpu_type)
            gpu_cost = gpu_hours * gpu_price
            
            events.append({
                'transaction_id': f"{timestamp.isoformat()}_{customer_id}_{gpu_type}",
                'customer_id': customer_id,
                'event_type': 'gpu_usage',
                'timestamp': timestamp.isoformat(),
                'properties': {
                    'type': gpu_type,
                    'hours': gpu_hours,
                    'price_per_hour': gpu_price,
                    'cost_usd': gpu_cost
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
    delay_between_batches = 0.1  # seconds
    
    for i in range(0, len(events), batch_size):
        batch = events[i:i + batch_size]
        batch_num = i//batch_size + 1
        total_batches = len(events)//batch_size + 1
        
        for retry in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=batch, timeout=timeout)
                response.raise_for_status()
                print(f"Successfully sent batch {batch_num}/{total_batches}")
                time.sleep(delay_between_batches)
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
    # Williams and Sons Solutions customer ID
    customer_id = "913d603a-8980-43e7-8267-1f0058139848"
    
    # Load rate card models
    models_df = get_rate_card_models()
    
    # Generate intensive usage
    print("Generating intensive usage events...")
    events = generate_intensive_usage(customer_id, models_df)
    
    # Save events to file for reference
    with open('williams_usage_events.json', 'w') as f:
        json.dump(events, f, indent=2)
    print(f"Generated {len(events)} events and saved to williams_usage_events.json")
    
    # Send events to Metronome
    api_key = "e940e56fd5d98819bd3870adee8f163fa0e3c6429e9bb19290e65d9888b492df"
    print("\nSending events to Metronome...")
    send_events_to_metronome(events, api_key)

if __name__ == "__main__":
    main()