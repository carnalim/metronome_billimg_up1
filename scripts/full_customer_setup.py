#!/usr/bin/env python3
import sys
from pathlib import Path
import uuid
import csv
import stripe
from datetime import datetime, timezone
from rich.console import Console
from rich.progress import Progress
sys.path.append(str(Path(__file__).parent.parent))
from metronome_billing.core.metronome_api import MetronomeAPI

metronome_api_key = "48b0453c99607fb5dfb4dc717ab2d9a2b6cc0dabec7885228871bc8c42748ccf"
stripe.api_key = "sk_test_51QaIZkIXaJVb8AWbz26erRPAJeaBQ90Nef7RFZzz3zDEtLxO0rROaLkvXsb7eyL9v4X2eL6L8l2HWMX459Q2KNbk003E64rxiX"

class IndustryProvider:
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
    
    @classmethod
    def industry(cls):
        return cls.random_element(cls.industries)


def generate_realistic_customer():
    company_types = ['Inc.', 'LLC', 'Corp.', 'Technologies', 'Solutions', 'Software']
    company_base = "Sample Company"
    company_type = "Inc."
    unique_suffix = str(uuid.uuid4())
    company_name = f"{company_base} {company_type} - {unique_suffix}"
    external_id = str(uuid.uuid4())
    return {
        "name": company_name,
        "external_id": external_id,
        "customer_config": {
            "salesforce_account_id": str(uuid.uuid4())  # Simulated Salesforce ID
        }
    }


def create_metronome_customer(api):
    customer = generate_realistic_customer()
    response = api._make_request("POST", "/customers", json=customer)
    return response


def create_stripe_customer(customer_data, metronome_id):
    stripe_customer = stripe.Customer.create(
        name=customer_data['name'],
        metadata={
            'metronome_customer_id': metronome_id,
            'metronome_external_id': customer_data['external_id']
        }
    )
    return stripe_customer


def link_customer_to_stripe(api, console, customer_id, stripe_customer_id):
    payload = {
        "data": [{
            "customer_id": customer_id,
            "billing_provider": "stripe",
            "configuration": {
                "stripe_customer_id": stripe_customer_id,
                "stripe_collection_method": "charge_automatically"
            },
            "delivery_method": "direct_to_billing_provider"
        }]
    }
    console.print(f"Linking customer to Stripe...", style="cyan")
    url = f"{api.BASE_URL}/setCustomerBillingProviderConfigurations"
    response = api.session.post(url, json=payload)
    if response.status_code != 200:
        raise Exception(f"Failed to link customer. Status code: {response.status_code}")


def create_contract(api, customer_id, rate_card_id):
    payload = {
        "data": {
            "rate_card_id": rate_card_id,
            "start_date": datetime.now(timezone.utc).isoformat(),
            "auto_renew": True
        }
    }
    url = f"{api.BASE_URL}/customers/{customer_id}/contracts"
    response = api.session.post(url, json=payload)
    if response.status_code not in [200, 201]:
        raise Exception(f"Failed to create contract. Status code: {response.status_code}. Response: {response.text}")
    return response.json()


import json
import tempfile

def get_metronome_customer(api, customer_id):
    response = api._make_request("GET", f"/customers/{customer_id}")
    return response

def get_rate_cards(api):
    url = f"{api.BASE_URL}/rate-cards"
    response = api.session.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to get rate cards. Status code: {response.status_code}. Response: {response.text}")
    return response.json()


def main():
    console = Console()
    try:
        api = MetronomeAPI(api_key=metronome_api_key)
        
        # Use default rate card
        rate_card_id = "ee186f96-3e72-4f7c-a326-a88a28e4b7da"
        console.print(f"✓ Using default rate card: {rate_card_id}", style="green")
        
        console.print("[cyan]Creating customer in Metronome...")
        metronome_customer = create_metronome_customer(api)
        console.print(f"✓ Created Metronome customer: {metronome_customer['data']['name']}", style="green")
        
        console.print("[cyan]Creating customer in Stripe...")
        stripe_customer = create_stripe_customer(metronome_customer['data'], metronome_customer['data']['id'])
        console.print(f"✓ Created Stripe customer: {stripe_customer.name} (ID: {stripe_customer.id})", style="green")

        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json') as temp_file:
                json.dump({
                    'metronome_customer_id': metronome_customer['data']['id'],
                    'stripe_customer_id': stripe_customer.id
                }, temp_file)
                console.print(f"Temporary file created: {temp_file.name}", style="cyan")
        
        console.print("[cyan]Linking customers...")
        try:
            link_customer_to_stripe(api, console, metronome_customer['data']['id'], stripe_customer.id)
            console.print(f"✓ Linked customer: {metronome_customer['data']['name']} (Metronome ID: {metronome_customer['data']['id']}, Stripe ID: {stripe_customer.id})", style="green")
        except Exception as e:
            console.print(f"Error linking customer: {str(e)}", style="bold red")
            sys.exit(1)
        
        console.print("[cyan]Creating contract...")
        create_contract(api, metronome_customer['data']['id'], rate_card_id)
        console.print(f"✓ Created contract for customer: {metronome_customer['data']['name']} (Customer ID: {metronome_customer['data']['id']})", style="green")
        
    except Exception as e:
        console.print(f"Error: {str(e)}", style="bold red")
        sys.exit(1)

if __name__ == "__main__":
    main()