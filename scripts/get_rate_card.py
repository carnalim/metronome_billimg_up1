import requests
import pandas as pd
import json

def get_rate_card_rates(api_key, rate_card_id):
    """
    Fetch rates for a rate card and return them as a pandas DataFrame
    """
    url = "https://api.metronome.com/v1/contract-pricing/rate-cards/getRates"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Get current timestamp to fetch current rates
    from datetime import datetime, timezone
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    
    payload = {
        "rate_card_id": rate_card_id,
        "at": current_time
    }
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    
    data = response.json()
    
    # Convert the rates data to a DataFrame
    rates = []
    for rate in data.get("data", []):
        rate_info = {
            "product_id": rate.get("product", {}).get("id"),
            "product_name": rate.get("product", {}).get("name"),
            "rate_type": rate.get("rate_type"),
            "entitled": rate.get("entitled", False)
        }
        
        # Add pricing details based on rate type
        if rate.get("rate_type") == "FLAT":
            rate_info["price"] = rate.get("price")
        elif rate.get("rate_type") == "TIERED":
            for idx, tier in enumerate(rate.get("tiers", [])):
                rate_info[f"tier_{idx+1}_start"] = tier.get("start_quantity")
                rate_info[f"tier_{idx+1}_price"] = tier.get("unit_price")
        
        # Add pricing group values if present
        if rate.get("pricing_group_values"):
            rate_info.update(rate.get("pricing_group_values"))
            
        rates.append(rate_info)
    
    return pd.DataFrame(rates)

if __name__ == "__main__":
    # API key and rate card ID
    API_KEY = "e940e56fd5d98819bd3870adee8f163fa0e3c6429e9bb19290e65d9888b492df"
    RATE_CARD_ID = "ee186f96-3e72-4f7c-a326-a88a28e4b7da"
    
    try:
        # Get rates and save to CSV
        df = get_rate_card_rates(API_KEY, RATE_CARD_ID)
        output_file = "/workspace/metronome-billing/current_rate_card_rates.csv"
        df.to_csv(output_file, index=False)
        print(f"Rate card rates saved to {output_file}")
        print("\nFirst few rows:")
        print(df.head())
        
    except Exception as e:
        print(f"Error: {str(e)}")
        if hasattr(e, 'response'):
            print(f"Response status code: {e.response.status_code}")
            print(f"Response text: {e.response.text}")