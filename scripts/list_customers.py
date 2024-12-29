#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from metronome_billing.core.metronome_api import MetronomeAPI
from rich.console import Console
from rich.table import Table
from rich import print as rprint

def main():
    console = Console()
    
    try:
        api = MetronomeAPI()
        console.print("Fetching customers from Metronome...", style="bold blue")
        
        customers = api.get_all_customers()
        
        if not customers:
            console.print("No customers found.", style="yellow")
            return

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Customer ID")
        table.add_column("Name")
        table.add_column("Email")
        table.add_column("Created At")
        table.add_column("Status")

        for customer in customers:
            table.add_row(
                customer.get("id", "N/A"),
                customer.get("name", "N/A"),
                customer.get("email", "N/A"),
                customer.get("created_at", "N/A"),
                customer.get("status", "N/A")
            )

        console.print(table)
        console.print(f"\nTotal customers: {len(customers)}", style="bold green")

    except Exception as e:
        console.print(f"Error: {str(e)}", style="bold red")
        sys.exit(1)

if __name__ == "__main__":
    main()