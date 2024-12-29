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
    # Prepare the contract payload
    payload = {
        "rate_card_id": rate_card_id,
        "start_date": datetime.now(timezone.utc).isoformat(),
        "auto_renew": True
    }
    
    # Make the API request to create the contract
    response = api._make_request(
        "POST",
        f"/customers/{customer_id}/contracts",
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
                        f"(Customer ID: {customer['customer_id']})",
                        style="green"
                    )
                except Exception as e:
                    console.print(f"✗ Failed to create contract for customer {customer['name']}: {str(e)}", style="red")
                progress.update(task2, advance=1)

        console.print(f"\n✓ Successfully created {len(created_contracts)} contracts", style="bold green")
        
    except Exception as e:
        console.print(f"Error: {str(e)}", style="bold red")
        sys.exit(1)

if __name__ == "__main__":
    main()