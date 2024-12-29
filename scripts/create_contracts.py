#!/usr/bin/env python3
import sys
from pathlib import Path
import csv
from datetime import datetime, timezone
sys.path.append(str(Path(__file__).parent.parent))

from metronome_billing.core.metronome_api import MetronomeAPI
from rich.console import Console
from rich.progress import Progress

def read_customers_from_csv(file_path: str):
    customers = []
    with open(file_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            customers.append(row)
    return customers

def create_contract(api: MetronomeAPI, customer_id: str, rate_card_id: str):
    # Format the date in the required format, setting minutes and seconds to 0
    now = datetime.now(timezone.utc)
    now = now.replace(minute=0, second=0, microsecond=0)
    formatted_date = now.strftime("%Y-%m-%dT%H:00:00Z")
    
    # Prepare the contract payload
    payload = {
        "customer_id": customer_id,
        "rate_card_id": rate_card_id,
        "starting_at": formatted_date,
        "name": "Standard Contract"
    }
    
    # Make the API request to create the contract
    response = api._make_request(
        "POST",
        "/contracts/create",
        json=payload
    )
    return response

def main():
    console = Console()
    csv_file = '/workspace/metronome-billing/new_customer_data.csv'
    rate_card_id = "ee186f96-3e72-4f7c-a326-a88a28e4b7da"
    
    try:
        api = MetronomeAPI()
        
        with Progress() as progress:
            # Read customers from CSV
            task1 = progress.add_task("[cyan]Reading customer data...", total=1)
            customers = read_customers_from_csv(csv_file)
            progress.update(task1, completed=1)
            
            # Create contracts
            task2 = progress.add_task("[green]Creating contracts...", total=len(customers))
            
            created_contracts = []
            for customer in customers:
                try:
                    response = create_contract(
                        api,
                        customer['customer_id'],
                        rate_card_id
                    )
                    created_contracts.append(response)
                    console.print(
                        f"✓ Created contract for customer: {customer['name']} "
                        f"(Contract ID: {response['data']['id']})",
                        style="green"
                    )
                except Exception as e:
                    console.print(f"✗ Failed to create contract for customer {customer['name']}: {str(e)}", style="red")
                progress.update(task2, advance=1)

        console.print(f"\n✓ Successfully created {len(created_contracts)} contracts", style="bold green")
        
        # Update CSV with contract IDs
        with open(csv_file, 'r') as file:
            rows = list(csv.reader(file))
        
        # Add contract ID column if it doesn't exist
        if 'contract_id' not in rows[0]:
            rows[0].append('contract_id')
            for i, row in enumerate(rows[1:], 1):
                if i <= len(created_contracts):
                    row.append(created_contracts[i-1]['data']['id'])
                else:
                    row.append('')
        
        with open(csv_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(rows)
        
        console.print(f"✓ Updated CSV file with contract IDs", style="bold green")
        
    except Exception as e:
        console.print(f"Error: {str(e)}", style="bold red")
        sys.exit(1)

if __name__ == "__main__":
    main()