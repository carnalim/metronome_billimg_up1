#!/usr/bin/env python3
import sys
from pathlib import Path
import csv
from datetime import datetime
sys.path.append(str(Path(__file__).parent.parent))

from metronome_billing.core.metronome_api import MetronomeAPI
from rich.console import Console
from rich.progress import Progress

def format_datetime(dt_str: str) -> str:
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except:
        return dt_str

def export_customers_to_csv(customers: list, output_file: str):
    fieldnames = [
        'customer_id',
        'name',
        'external_id',
        'salesforce_account_id',
        'ingest_aliases',
        'custom_fields'
    ]

    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for customer in customers:
            customer_config = customer.get('customer_config', {})
            writer.writerow({
                'customer_id': customer.get('id', ''),
                'name': customer.get('name', ''),
                'external_id': customer.get('external_id', ''),
                'salesforce_account_id': customer_config.get('salesforce_account_id', ''),
                'ingest_aliases': ', '.join(customer.get('ingest_aliases', [])),
                'custom_fields': str(customer.get('custom_fields', {}))
            })

def main():
    console = Console()
    output_file = 'current_customers.csv'
    
    try:
        api = MetronomeAPI()
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Fetching customers...", total=None)
            customers = api.get_all_customers()
            progress.update(task, total=1, completed=1)
            
            if not customers:
                console.print("No customers found.", style="yellow")
                return

            task2 = progress.add_task("[green]Exporting to CSV...", total=1)
            export_customers_to_csv(customers, output_file)
            progress.update(task2, completed=1)

        console.print(f"\n✓ Successfully exported {len(customers)} customers to {output_file}", style="bold green")
        
    except Exception as e:
        console.print(f"Error: {str(e)}", style="bold red")
        sys.exit(1)

if __name__ == "__main__":
    main()