#!/usr/bin/env python3
import sys
from pathlib import Path
import uuid
from typing import Dict, List
sys.path.append(str(Path(__file__).parent.parent))

from metronome_billing.core.metronome_api import MetronomeAPI
from rich.console import Console
from rich.progress import Progress
from faker import Faker
from faker.providers import BaseProvider

# Add industry provider to Faker
class IndustryProvider(BaseProvider):
    industries = [
        'Software Development',
        'Cloud Computing',
        'Financial Services',
        'Healthcare Technology',
        'E-commerce',
        'Cybersecurity',
        'Data Analytics',
        'Artificial Intelligence',
        'Internet of Things',
        'Digital Marketing',
        'Telecommunications',
        'Biotechnology',
        'Manufacturing',
        'Retail Technology',
        'Education Technology'
    ]
    
    def industry(self):
        return self.random_element(self.industries)

def generate_realistic_customers(num_customers: int = 10) -> List[Dict]:
    fake = Faker()
    fake.add_provider(IndustryProvider)
    customers = []
    
    # Common company suffixes
    company_types = ['Inc.', 'LLC', 'Corp.', 'Technologies', 'Solutions', 'Software']
    
    for _ in range(num_customers):
        # Generate a realistic company name
        company_base = fake.company().replace(fake.company_suffix(), '').strip()
        company_type = fake.random_element(company_types)
        company_name = f"{company_base} {company_type}"
        
        # Generate a unique external ID
        external_id = str(uuid.uuid4())
        
        # Create customer data
        customer = {
            "name": company_name,
            "external_id": external_id,
            "customer_config": {
                "salesforce_account_id": fake.uuid4()  # Simulated Salesforce ID
            }
        }
        customers.append(customer)
    
    return customers

def main():
    console = Console()
    
    try:
        api = MetronomeAPI()
        
        with Progress() as progress:
            task1 = progress.add_task("[cyan]Generating customer data...", total=1)
            customers = generate_realistic_customers(10)
            progress.update(task1, completed=1)
            
            task2 = progress.add_task("[green]Creating customers in Metronome...", total=len(customers))
            
            created_customers = []
            for customer in customers:
                try:
                    response = api._make_request("POST", "/customers", json=customer)
                    created_customers.append(response)
                    console.print(f"✓ Created customer: {customer['name']}", style="green")
                except Exception as e:
                    console.print(f"✗ Failed to create customer {customer['name']}: {str(e)}", style="red")
                progress.update(task2, advance=1)

        console.print(f"\n✓ Successfully created {len(created_customers)} customers", style="bold green")
        
    except Exception as e:
        console.print(f"Error: {str(e)}", style="bold red")
        sys.exit(1)

if __name__ == "__main__":
    main()