#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import csv
import requests
from rich.console import Console
from rich.progress import Progress
from metronome_billing.core.metronome_api import MetronomeAPI

def read_customers_from_csv(file_path: str):
    customers = []
    with open(file_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            customers.append(row)
    return customers

def link_customer_to_stripe(api: MetronomeAPI, customer_id: str, stripe_customer_id: str):
    # Prepare the request payload based on the example
    payload = {
        "provider_type": "stripe",
        "provider_customer_id": stripe_customer_id
    }
    
    # Make the API request to set the billing provider configuration
    response = api._make_request(
        "PUT",
        f"/customers/{customer_id}/billing_provider",
        json=payload
    )
    return response

def main():
    console = Console()
    csv_file = '/workspace/metronome-billing/new_customer_data.csv'
    
    try:
        api = MetronomeAPI()
        
        with Progress() as progress:
            # Read customers from CSV
            task1 = progress.add_task("[cyan]Reading customer data...", total=1)
            customers = read_customers_from_csv(csv_file)
            progress.update(task1, completed=1)
            
            # Link customers
            task2 = progress.add_task("[green]Linking customers...", total=len(customers))
            
            linked_customers = []
            for customer in customers:
                try:
                    response = link_customer_to_stripe(
                        api,
                        customer['customer_id'],
                        customer['stripe_customer_id']
                    )
                    linked_customers.append(response)
                    console.print(
                        f"✓ Linked customer: {customer['name']} "
                        f"(Metronome: {customer['customer_id']}, "
                        f"Stripe: {customer['stripe_customer_id']})",
                        style="green"
                    )
                except Exception as e:
                    console.print(f"✗ Failed to link customer {customer['name']}: {str(e)}", style="red")
                progress.update(task2, advance=1)

        console.print(f"\n✓ Successfully linked {len(linked_customers)} customers", style="bold green")
        
    except Exception as e:
        console.print(f"Error: {str(e)}", style="bold red")
        sys.exit(1)

if __name__ == "__main__":
    main()