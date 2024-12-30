#!/usr/bin/env python3
import sys
from pathlib import Path
import csv
from datetime import datetime, timezone
sys.path.append(str(Path(__file__).parent.parent))
from metronome_billing.core.metronome_api import MetronomeAPI

def get_all_customers(api):
    """Get all customers from Metronome"""
    customers = []
    cursor = None
    
    while True:
        response = api._make_request("GET", "/customers", params={"limit": 100, "cursor": cursor})
        if not response.get('data'):
            break
            
        customers.extend(response['data'])
        
        # Check if there are more pages
        cursor = response.get('pagination', {}).get('next_cursor')
        if not cursor:
            break
    
    return customers

def save_customers_to_csv(customers, output_file):
    """Save customers to CSV file"""
    if not customers:
        print("No customers found")
        return
        
    # Define the fieldnames based on the first customer's data
    fieldnames = ['customer_id', 'name', 'external_id', 'salesforce_account_id', 
                 'ingest_aliases', 'custom_fields', 'stripe_customer_id', 'contract_id']
    
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for customer in customers:
            row = {
                'customer_id': customer.get('id'),
                'name': customer.get('name'),
                'external_id': customer.get('external_id'),
                'salesforce_account_id': '',  # Not provided in API response
                'ingest_aliases': customer.get('ingest_aliases', []),
                'custom_fields': customer.get('custom_fields', {}),
                'stripe_customer_id': '',  # Will be populated if available
                'contract_id': ''  # Will be populated if available
            }
            writer.writerow(row)
    
    print(f"Saved {len(customers)} customers to {output_file}")

def main():
    # Initialize API
    api_key = "48b0453c99607fb5dfb4dc717ab2d9a2b6cc0dabec7885228871bc8c42748ccf"
    api = MetronomeAPI(api_key=api_key)
    
    # Get all customers
    print("Fetching customers from Metronome...")
    customers = get_all_customers(api)
    print(f"Found {len(customers)} customers")
    
    # Save to CSV
    output_file = '../recent_customers.csv'
    save_customers_to_csv(customers, output_file)

if __name__ == "__main__":
    main()