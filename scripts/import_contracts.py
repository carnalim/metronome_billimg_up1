#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from website import db
from website.models import Customer, Contract
from metronome_billing.core.metronome_api import MetronomeAPI
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def import_contracts():
    """Import all contracts from Metronome API for each customer"""
    try:
        # Initialize API
        api = MetronomeAPI()
        
        # Get all customers from database
        customers = Customer.query.all()
        logger.info(f"Found {len(customers)} customers in database")
        
        updated_count = 0
        created_count = 0
        
        for customer in customers:
            if not customer.metronome_id:
                continue
                
            try:
                logger.info(f"Fetching contracts for customer {customer.metronome_id}")
                response = api._make_request("POST", "/contracts/list", json={
                    "customer_id": customer.metronome_id
                })
                
                if isinstance(response, dict) and 'data' in response:
                    contracts_data = response['data']
                    if not isinstance(contracts_data, list):
                        contracts_data = [contracts_data]
                    
                    for contract_data in contracts_data:
                        try:
                            contract_id = contract_data.get('id')
                            if not contract_id:
                                continue

                            # Get initial contract data
                            initial = contract_data.get('initial', {})
                            
                            # Parse dates
                            starting_at = None
                            ending_before = None
                            try:
                                if initial.get('starting_at'):
                                    starting_at = datetime.fromisoformat(initial['starting_at'].replace('Z', '+00:00'))
                                if initial.get('ending_before'):
                                    ending_before = datetime.fromisoformat(initial['ending_before'].replace('Z', '+00:00'))
                            except ValueError as e:
                                logger.error(f"Error parsing dates for contract {contract_id}: {str(e)}")

                            # Get rate card details
                            rate_card_id = initial.get('rate_card_id')
                            rate_card_name = 'Unknown Rate Card'
                            if rate_card_id:
                                rate_card_response = api._make_request("POST", "/contract-pricing/rate-cards/get", json={
                                    "id": rate_card_id
                                })
                                if isinstance(rate_card_response, dict) and 'data' in rate_card_response:
                                    rate_card_data = rate_card_response['data']
                                    rate_card_initial = rate_card_data.get('initial', {})
                                    rate_card_name = rate_card_initial.get('name', 'Unknown Rate Card')

                            # Get product details
                            product_id = initial.get('product_id')
                            product_name = 'Unknown Product'
                            if product_id:
                                product_response = api._make_request("POST", "/contract-pricing/products/get", json={
                                    "id": product_id
                                })
                                if isinstance(product_response, dict) and 'data' in product_response:
                                    product_data = product_response['data']
                                    product_initial = product_data.get('initial', {})
                                    product_name = product_initial.get('name', 'Unknown Product')

                            # Find or create contract
                            contract = Contract.query.filter_by(id=contract_id).first()
                            if contract:
                                contract.name = initial.get('name') if initial else contract_data.get('name', 'Unnamed Contract')
                                contract.product_name = product_name
                                contract.rate_card_name = rate_card_name
                                contract.status = contract_data.get('status', 'active')
                                contract.starting_at = starting_at
                                contract.ending_before = ending_before
                                contract.last_synced = datetime.now(timezone.utc)
                                updated_count += 1
                                logger.info(f"Updated contract {contract_id}")
                            else:
                                contract = Contract(
                                    id=contract_id,
                                    customer_id=customer.metronome_id,
                                    name=initial.get('name') if initial else contract_data.get('name', 'Unnamed Contract'),
                                    product_name=product_name,
                                    rate_card_name=rate_card_name,
                                    status=contract_data.get('status', 'active'),
                                    starting_at=starting_at,
                                    ending_before=ending_before,
                                    created_at=datetime.now(timezone.utc),
                                    last_synced=datetime.now(timezone.utc)
                                )
                                db.session.add(contract)
                                created_count += 1
                                logger.info(f"Created contract {contract_id}")

                            # Commit every 100 contracts to avoid memory issues
                            if (updated_count + created_count) % 100 == 0:
                                db.session.commit()
                                logger.info(f"Committed batch of 100 contracts (Updated: {updated_count}, Created: {created_count})")

                        except Exception as e:
                            logger.error(f"Error processing contract {contract_data.get('id')}: {str(e)}")
                            continue
                else:
                    logger.warning(f"No contracts data found for customer {customer.metronome_id}")
            except Exception as e:
                logger.error(f"Error fetching contracts for customer {customer.metronome_id}: {str(e)}")
                continue

        # Final commit for remaining contracts
        db.session.commit()
        logger.info(f"Successfully imported contracts. Updated {updated_count} and created {created_count} contracts.")
        return True, f"Successfully imported contracts. Updated {updated_count} and created {created_count} contracts."

    except Exception as e:
        error_msg = f"Error importing contracts: {str(e)}"
        logger.error(error_msg)
        logger.exception("Full traceback:")
        return False, error_msg

if __name__ == '__main__':
    success, message = import_contracts()
    if not success:
        sys.exit(1)