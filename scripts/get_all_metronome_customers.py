#!/usr/bin/env python3
import sys
from pathlib import Path
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
sys.path.append(str(Path(__file__).parent.parent))
from metronome_billing.core.metronome_api import MetronomeAPI

def get_all_customers(api):
    """Get all customers from Metronome with pagination"""
    all_customers = []
    cursor = None
    page = 1
    
    console = Console()
    console.print("[cyan]Fetching customers from Metronome...")
    
    while True:
        try:
            # Make request with cursor if available
            params = {"limit": 100}  # API limit is 100 per page
            if cursor:
                params["cursor"] = cursor
            
            response = api._make_request("GET", "/customers", params=params)
            console.print(f"Response: {response}", style="yellow")
            
            # Check if we got any customers
            customers = response.get('data', [])
            if not customers:
                break
                
            all_customers.extend(customers)
            console.print(f"✓ Retrieved page {page} with {len(customers)} customers (Total: {len(all_customers)})", style="green")
            
            # Get cursor for next page
            cursor = response.get('next_page')
            if not cursor:
                break
                
            page += 1
            
        except Exception as e:
            console.print(f"Error fetching page {page}: {str(e)}", style="red")
            if hasattr(e, 'response'):
                console.print(f"Response: {e.response.text}", style="red")
            break
    
    return all_customers

def save_customers_to_json(customers, output_file):
    """Save customers to a JSON file with pretty formatting"""
    with open(output_file, 'w') as f:
        json.dump(customers, f, indent=2)

def display_customer_summary(customers):
    """Display a summary of the customers in a table"""
    console = Console()
    
    # Create main statistics table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Total Customers", justify="center")
    table.add_column("With External IDs", justify="center")
    table.add_column("With Custom Fields", justify="center")
    table.add_column("With Ingest Aliases", justify="center")
    
    # Calculate statistics
    total = len(customers)
    with_external_ids = sum(1 for c in customers if c.get('external_id'))
    with_custom_fields = sum(1 for c in customers if c.get('custom_fields'))
    with_ingest_aliases = sum(1 for c in customers if c.get('ingest_aliases'))
    
    # Add row to table
    table.add_row(
        str(total),
        f"{with_external_ids} ({with_external_ids/total*100:.1f}%)",
        f"{with_custom_fields} ({with_custom_fields/total*100:.1f}%)",
        f"{with_ingest_aliases} ({with_ingest_aliases/total*100:.1f}%)"
    )
    
    # Create name pattern table
    name_table = Table(show_header=True, header_style="bold cyan")
    name_table.add_column("Name Pattern", justify="left")
    name_table.add_column("Count", justify="right")
    
    # Analyze name patterns
    name_patterns = {}
    for c in customers:
        name = c.get('name', '')
        if name.startswith('Sample Company Inc.'):
            pattern = 'Sample Company Inc.'
        elif name.startswith('Test Customer'):
            pattern = 'Test Customer'
        else:
            pattern = 'Other'
        name_patterns[pattern] = name_patterns.get(pattern, 0) + 1
    
    # Add rows to name pattern table
    for pattern, count in sorted(name_patterns.items(), key=lambda x: x[1], reverse=True):
        name_table.add_row(pattern, f"{count} ({count/total*100:.1f}%)")
    
    console.print("\n[bold]Customer Summary:[/bold]")
    console.print(table)
    console.print("\n[bold]Name Patterns:[/bold]")
    console.print(name_table)

def main():
    # Initialize API
    api_key = "48b0453c99607fb5dfb4dc717ab2d9a2b6cc0dabec7885228871bc8c42748ccf"
    api = MetronomeAPI(api_key=api_key)
    
    # Get all customers
    customers = get_all_customers(api)
    
    if not customers:
        print("No customers found")
        return
    
    # Save to JSON file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f'../metronome_customers_{timestamp}.json'
    save_customers_to_json(customers, output_file)
    print(f"\nSaved {len(customers)} customers to {output_file}")
    
    # Display summary
    display_customer_summary(customers)
    
    # Save to CSV
    csv_file = '../all_customers.csv'
    import pandas as pd
    df = pd.DataFrame([{
        'customer_id': c.get('id'),
        'name': c.get('name'),
        'external_id': c.get('external_id'),
        'salesforce_account_id': '',
        'ingest_aliases': c.get('ingest_aliases', []),
        'custom_fields': c.get('custom_fields', {}),
        'stripe_customer_id': '',
        'contract_id': ''
    } for c in customers])
    df.to_csv(csv_file, index=False)
    print(f"\nSaved customer data to {csv_file} for use with other scripts")

if __name__ == "__main__":
    main()