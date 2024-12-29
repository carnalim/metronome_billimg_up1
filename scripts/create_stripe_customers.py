#!/usr/bin/env python3
import sys
from pathlib import Path
import csv
import stripe
from rich.console import Console
from rich.progress import Progress

# Initialize Stripe with the sandbox API key
stripe.api_key = "sk_test_51QaIZkIXaJVb8AWbz26erRPAJeaBQ90Nef7RFZzz3zDEtLxO0rROaLkvXsb7eyL9v4X2eL6L8l2HWMX459Q2KNbk003E64rxiX"

def read_customers_from_csv(file_path: str):
    customers = []
    with open(file_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            customers.append(row)
    return customers

def create_stripe_customer(customer_data):
    try:
        # Create customer in Stripe
        stripe_customer = stripe.Customer.create(
            name=customer_data['name'],
            metadata={
                'metronome_customer_id': customer_data['customer_id'],
                'metronome_external_id': customer_data['external_id']
            }
        )
        return stripe_customer
    except stripe.error.StripeError as e:
        raise Exception(f"Stripe API error: {str(e)}")

def main():
    console = Console()
    csv_file = '/workspace/metronome-billing/new_customer_data.csv'
    
    try:
        with Progress() as progress:
            # Read customers from CSV
            task1 = progress.add_task("[cyan]Reading customer data...", total=1)
            customers = read_customers_from_csv(csv_file)
            progress.update(task1, completed=1)
            
            # Create customers in Stripe
            task2 = progress.add_task("[green]Creating customers in Stripe...", total=len(customers))
            
            created_customers = []
            for customer in customers:
                try:
                    stripe_customer = create_stripe_customer(customer)
                    created_customers.append(stripe_customer)
                    console.print(f"✓ Created Stripe customer: {customer['name']} (ID: {stripe_customer.id})", style="green")
                except Exception as e:
                    console.print(f"✗ Failed to create customer {customer['name']}: {str(e)}", style="red")
                progress.update(task2, advance=1)

        console.print(f"\n✓ Successfully created {len(created_customers)} customers in Stripe", style="bold green")
        
        # Update CSV with Stripe IDs
        with open(csv_file, 'r') as file:
            rows = list(csv.reader(file))
        
        # Add Stripe ID column if it doesn't exist
        if 'stripe_customer_id' not in rows[0]:
            rows[0].append('stripe_customer_id')
            for i, row in enumerate(rows[1:], 1):
                if i <= len(created_customers):
                    row.append(created_customers[i-1].id)
                else:
                    row.append('')
        
        with open(csv_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(rows)
        
        console.print(f"✓ Updated CSV file with Stripe customer IDs", style="bold green")
        
    except Exception as e:
        console.print(f"Error: {str(e)}", style="bold red")
        sys.exit(1)

if __name__ == "__main__":
    main()