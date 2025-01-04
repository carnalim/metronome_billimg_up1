#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from pathlib import Path
import sys
import uuid
import stripe
import requests
from datetime import datetime, timezone, timedelta
import json
import logging
import os
import numpy as np
import time
from website.models import db, LogEntry, Customer, Product, Contract

sys.path.append(str(Path(__file__).parent.parent))
from metronome_billing.core.metronome_api import MetronomeAPI

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev')

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///metronome.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def init_db():
    """Initialize the database and handle migrations"""
    with app.app_context():
        # Check if we need to recreate tables
        try:
            # Try to query the new columns
            Customer.query.order_by(Customer.last_synced).first()
            Product.query.order_by(Product.last_synced).first()
            Contract.query.order_by(Contract.last_synced).first()
        except Exception as e:
            logging.info("Detected schema change, recreating database tables")
            # Drop all tables
            db.drop_all()
            # Create all tables with new schema
            db.create_all()
            logging.info("Database tables recreated successfully")

# Initialize database
init_db()

# Create database tables
with app.app_context():
    db.create_all()

# Configure logging
class DatabaseHandler(logging.Handler):
    def emit(self, record):
        try:
            from flask import current_app
            if current_app:
                log_entry = LogEntry(
                    level=record.levelname,
                    message=self.format(record)
                )
                db.session.add(log_entry)
                db.session.commit()
        except Exception as e:
            # Print to console if database logging fails
            print(f"[{record.levelname}] {self.format(record)}")

# Remove existing handlers
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Configure root logger
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
db_handler = DatabaseHandler()
db_handler.setFormatter(formatter)

# Also add a stream handler for console output
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

root_logger.addHandler(db_handler)
root_logger.addHandler(console_handler)
root_logger.setLevel(logging.INFO)

# Load API keys from environment or use defaults
metronome_api_key = os.getenv('METRONOME_API_KEY', "48b0453c99607fb5dfb4dc717ab2d9a2b6cc0dabec7885228871bc8c42748ccf")
stripe.api_key = os.getenv('STRIPE_API_KEY', "sk_test_51QaIZkIXaJVb8AWbz26erRPAJeaBQ90Nef7RFZzz3zDEtLxO0rROaLkvXsb7eyL9v4X2eL6L8l2HWMX459Q2KNbk003E64rxiX")

# Industry list
INDUSTRIES = [
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

def create_contract(api, customer_id, rate_card_id):
    # Format the date as YYYY-MM-DDT00:00:00.000Z
    current_date = datetime.now(timezone.utc)
    formatted_date = current_date.strftime("%Y-%m-%dT00:00:00.000Z")
    
    payload = {
        "customer_id": customer_id,
        "rate_card_id": rate_card_id,
        "starting_at": formatted_date
    }
    url = f"{api.BASE_URL}/contracts"
    response = api.session.post(url, json=payload)
    if response.status_code not in [200, 201]:
        raise Exception(f"Failed to create contract. Status code: {response.status_code}. Response: {response.text}")
    return response.json()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create', methods=['GET', 'POST'])
def create_customer():
    response_data = {}
    try:
        if request.method == 'POST':
            # Get form data
            name = request.form.get('name')
            rate_card_id = request.form.get('rate_card_id')
            salesforce_id = request.form.get('salesforce_id')
            
            response_data['form_data'] = {
                'name': name,
                'rate_card_id': rate_card_id,
                'salesforce_id': salesforce_id
            }
            
            # Create customer in Stripe first
            try:
                stripe_customer = stripe.Customer.create(
                    name=name,
                    metadata={
                        'salesforce_id': salesforce_id
                    }
                )
                response_data['stripe'] = {
                    'success': True,
                    'customer_id': stripe_customer.id,
                    'response': stripe_customer
                }
                logging.info(f"Created Stripe customer: {stripe_customer.id}")
            except Exception as e:
                response_data['stripe'] = {
                    'success': False,
                    'error': str(e)
                }
                flash(f"Failed to create Stripe customer: {str(e)}", "danger")
                return render_template('create.html', rate_cards=[], response_data=response_data)
            
            # Prepare request data for Metronome
            json_data = {
                "name": name,
                "payment_provider": "stripe",
                "payment_provider_id": stripe_customer.id
            }
            
            # Add optional fields if provided
            if salesforce_id:
                json_data["salesforce_id"] = salesforce_id
            if rate_card_id:
                json_data["rate_card_id"] = rate_card_id
            
            response_data['metronome_request'] = json_data
            
            # Create customer in Metronome
            url = "https://api.metronome.com/v1/customers"
            headers = {
                "Authorization": f"Bearer {metronome_api_key}",
                "Content-Type": "application/json"
            }
            
            logging.info(f"Creating Metronome customer with data: {json_data}")
            response = requests.post(url, headers=headers, json=json_data)
            logging.info(f"Metronome response status: {response.status_code}")
            logging.info(f"Metronome response: {response.text}")
            
            response_data['metronome'] = {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'response': response.json() if response.status_code == 200 else response.text
            }
            
            if response.status_code == 200:
                response_data = response.json()
                metronome_customer = response_data.get('data', {})
                
                # Save customer to local database
                customer = Customer(
                    metronome_id=metronome_customer.get('id'),
                    name=name,
                    salesforce_id=salesforce_id,
                    rate_card_id=rate_card_id,
                    stripe_id=stripe_customer.id,
                    created_at=datetime.now(timezone.utc),
                    last_synced=datetime.now(timezone.utc)
                )
                db.session.add(customer)
                db.session.commit()
                
                response_data['database'] = {
                    'success': True,
                    'customer_id': customer.id
                }
                
                # Link customer to Stripe
                link_payload = {
                    "data": [{
                        "customer_id": metronome_customer.get('id'),
                        "billing_provider": "stripe",
                        "configuration": {
                            "stripe_customer_id": stripe_customer.id,
                            "stripe_collection_method": "charge_automatically"
                        },
                        "delivery_method": "direct_to_billing_provider"
                    }]
                }
                link_url = "https://api.metronome.com/v1/setCustomerBillingProviderConfigurations"
                link_response = requests.post(
                    link_url,
                    headers={"Authorization": f"Bearer {metronome_api_key}"},
                    json=link_payload
                )
                if link_response.status_code != 200:
                    error_msg = f"Failed to link customer to Stripe: {link_response.text}"
                    logging.error(error_msg)
                    flash(error_msg, "danger")
                    return render_template('create.html', rate_cards=rate_cards, response_data=response_data)

                # Create contract if rate card was selected
                if rate_card_id:
                    current_date = datetime.now(timezone.utc)
                    formatted_date = current_date.strftime("%Y-%m-%dT00:00:00.000Z")
                    # Get rate card details to get product_id
                    rate_card_url = "https://api.metronome.com/v1/rate-cards/list"
                    rate_card_response = requests.post(
                        rate_card_url,
                        headers={"Authorization": f"Bearer {metronome_api_key}"},
                        json={}
                    )
                    if rate_card_response.status_code == 200:
                        rate_cards_data = rate_card_response.json()
                        rate_card = next(
                            (card for card in rate_cards_data.get('data', []) if card.get('id') == rate_card_id),
                            None
                        )
                        if rate_card and rate_card.get('product_id'):
                            contract_payload = {
                                "customer_id": metronome_customer.get('id'),
                                "rate_card_id": rate_card_id,
                                "product_id": rate_card['product_id'],
                                "starting_at": formatted_date,
                                "status": "active"
                            }
                            logging.info(f"Creating contract with payload: {json.dumps(contract_payload, indent=2)}")
                        else:
                            error_msg = "Rate card does not have a product ID"
                            logging.error(error_msg)
                            flash(error_msg, "danger")
                            return render_template('create.html', rate_cards=rate_cards, response_data=response_data)
                    else:
                        error_msg = f"Failed to fetch rate card: {rate_card_response.text}"
                        logging.error(error_msg)
                        flash(error_msg, "danger")
                        return render_template('create.html', rate_cards=rate_cards, response_data=response_data)
                    contract_url = "https://api.metronome.com/v1/contracts"
                    contract_response = requests.post(
                        contract_url,
                        headers={"Authorization": f"Bearer {metronome_api_key}"},
                        json=contract_payload
                    )
                    logging.info(f"Contract response: {json.dumps(contract_response.json() if contract_response.status_code in [200, 201] else {}, indent=2)}")
                    if contract_response.status_code not in [200, 201]:
                        error_msg = f"Failed to create contract: {contract_response.text}"
                        logging.error(error_msg)
                        flash(error_msg, "danger")
                        return render_template('create.html', rate_cards=rate_cards, response_data=response_data)

                flash("Customer created successfully", "success")
            else:
                # If Metronome creation fails, delete the Stripe customer
                try:
                    stripe.Customer.delete(stripe_customer.id)
                    response_data['stripe_cleanup'] = {
                        'success': True,
                        'message': 'Stripe customer deleted due to Metronome failure'
                    }
                except Exception as e:
                    response_data['stripe_cleanup'] = {
                        'success': False,
                        'error': str(e)
                    }
                
                error_msg = f"Failed to create customer in Metronome: {response.text}"
                logging.error(error_msg)
                flash(error_msg, "danger")
        
        # Get rate cards for the form
        api = MetronomeAPI(api_key=metronome_api_key)
        print("Fetching rate cards...")
        response_data = api._make_request("POST", "/contract-pricing/rate-cards/list", json={})
        print(f"Rate cards response data: {json.dumps(response_data, indent=2)}")
        logging.info(f"Rate cards response data: {json.dumps(response_data, indent=2)}")
        
        # Extract rate cards from response
        if isinstance(response_data, dict):
            if 'data' in response_data and isinstance(response_data['data'], list):
                rate_cards = response_data['data']
            else:
                rate_cards = [response_data]
        else:
            rate_cards = response_data if isinstance(response_data, list) else []
        
        print(f"Found {len(rate_cards)} rate cards")
        print(f"Rate cards: {json.dumps(rate_cards, indent=2)}")
        logging.info(f"Found {len(rate_cards)} rate cards")
        logging.info(f"Rate cards: {json.dumps(rate_cards, indent=2)}")
        
        if not rate_cards:
            flash("No rate cards found. Please create a rate card first.", "warning")
        
        return render_template('create.html', rate_cards=rate_cards, response_data=response_data)
        
    except Exception as e:
        error_msg = f"Error creating customer: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback:")
        flash(error_msg, "danger")
        response_data['error'] = str(e)
        return render_template('create.html', rate_cards=[], response_data=response_data)

def refresh_products():
    """Refresh products from Metronome API and store in database"""
    try:
        api = MetronomeAPI(api_key=metronome_api_key)
        logging.info("Fetching products from Metronome API")
        response_data = api._make_request("POST", "/contract-pricing/products/list", json={
            "archive_filter": "NOT_ARCHIVED"
        })

        if isinstance(response_data, dict) and 'data' in response_data:
            products_list = response_data['data']
            updated_count = 0
            created_count = 0

            for product in products_list:
                product_id = product.get('id')
                if not product_id:
                    continue

                # Get detailed product information
                product_response = api._make_request("POST", "/contract-pricing/products/get", json={
                    "id": product_id
                })

                if isinstance(product_response, dict) and 'data' in product_response:
                    product_data = product_response.get('data', {})
                    initial = product_data.get('initial', {})
                    
                    # Parse created_at if present
                    created_at = None
                    if 'created_at' in product_data:
                        try:
                            created_at = datetime.fromisoformat(product_data['created_at'].replace('Z', '+00:00'))
                        except (ValueError, AttributeError):
                            pass

                    # Find or create product
                    db_product = Product.query.filter_by(product_id=product_id).first()
                    if db_product:
                        db_product.name = initial.get('name', 'Unnamed Product')
                        db_product.description = initial.get('description', '')
                        db_product.archived = product_data.get('archived_at') is not None
                        db_product.created_at = created_at
                        db_product.last_synced = datetime.now(timezone.utc)
                        db_product.credit_types = product_data.get('credit_types', [])
                        updated_count += 1
                    else:
                        db_product = Product(
                            product_id=product_id,
                            name=initial.get('name', 'Unnamed Product'),
                            description=initial.get('description', ''),
                            archived=product_data.get('archived_at') is not None,
                            created_at=created_at,
                            last_synced=datetime.now(timezone.utc),
                            credit_types=product_data.get('credit_types', [])
                        )
                        db.session.add(db_product)
                        created_count += 1

            db.session.commit()
            message = f"Successfully refreshed products. Updated {updated_count} and created {created_count} products."
            logging.info(message)
            return True, message
        else:
            error_msg = "Unexpected response format from Metronome API"
            logging.error(error_msg)
            return False, error_msg

    except Exception as e:
        error_msg = f"Error refreshing products: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback:")
        return False, error_msg

@app.route('/products')
def products():
    try:
        # Get products from database
        products = Product.query.all()
        
        # Convert database objects to dictionaries for template
        products_list = []
        for product in products:
            product_dict = {
                'id': product.product_id,
                'name': product.name,
                'description': product.description,
                'archived': product.archived,
                'created_at': product.created_at.strftime('%Y-%m-%d %H:%M:%S') if product.created_at else None,
                'credit_types': product.credit_types
            }
            products_list.append(product_dict)
        
        return render_template('products.html', products=products_list)
            
    except Exception as e:
        error_msg = f"Error loading products: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback:")
        flash(error_msg, 'danger')
        return render_template('products.html', products=[])

@app.route('/rate-cards')
def rate_cards():
    try:
        # Make API request
        api = MetronomeAPI(api_key=metronome_api_key)
        logging.info("Fetching rate cards")
        response_data = api._make_request("POST", "/contract-pricing/rate-cards/list", json={})
        logging.info(f"Rate cards response data: {json.dumps(response_data, indent=2)}")
        
        # Extract rate cards from response
        if isinstance(response_data, dict):
            if 'data' in response_data and isinstance(response_data['data'], list):
                rate_cards = response_data['data']
            else:
                rate_cards = [response_data]
        else:
            rate_cards = response_data if isinstance(response_data, list) else []
        
        logging.info(f"Found {len(rate_cards)} rate cards")
        return render_template('rate_cards.html', rate_cards=rate_cards)
            
    except Exception as e:
        error_msg = f"Error loading rate cards: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback:")
        flash(error_msg, 'danger')
        return render_template('rate_cards.html', rate_cards=[])

@app.route('/customers')
def customers():
    try:
        # Get search and pagination parameters
        search_query = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Fetch all customers from Metronome using pagination
        all_customers = []
        next_page = None
        base_url = "https://api.metronome.com/v1/customers"
        headers = {
            "Authorization": f"Bearer {metronome_api_key}",
            "Accept": "application/json"
        }

        while True:
            # Make API request with pagination token if available
            params = {}
            if next_page:
                params["page_token"] = next_page
                logging.info(f"Fetching next page with token: {next_page}")
            
            response = requests.get(base_url, headers=headers, params=params)
            logging.info(f"Customers response status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        # Handle customer list response
                        if 'data' in data and isinstance(data['data'], list):
                            current_page_customers = len(data['data'])
                            all_customers.extend(data['data'])
                            logging.info(f"Fetched {current_page_customers} customers (total: {len(all_customers)})")
                        
                        # Get next page token
                        next_page = data.get('next_page_token')
                        if next_page:
                            logging.info(f"Found next page token")
                        else:
                            logging.info("No more pages to fetch")
                            break
                    else:
                        logging.error("Unexpected response format")
                        break
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse JSON response: {e}")
                    break
            else:
                error_msg = f"Failed to fetch customers: {response.text}"
                logging.error(error_msg)
                flash(error_msg, "danger")
                break

            # Add a small delay between requests to avoid rate limiting
            time.sleep(0.5)
        
        # Update local database with all customers
        if all_customers:
            
            # Update local database with all customers
            for customer_data in all_customers:
                customer_id = customer_data.get('id')
                if not customer_id:
                    continue
                
                # Parse created_at if present
                created_at = None
                if 'created_at' in customer_data:
                    try:
                        created_at = datetime.fromisoformat(customer_data['created_at'].replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        pass
                
                customer = Customer.query.filter_by(metronome_id=customer_id).first()
                if customer:
                    # Update existing customer
                    customer.name = customer_data.get('name', 'Unnamed Customer')
                    customer.salesforce_id = customer_data.get('salesforce_id')
                    customer.rate_card_id = customer_data.get('rate_card_id')
                    customer.created_at = created_at
                    customer.last_synced = datetime.now(timezone.utc)
                else:
                    # Create new customer
                    customer = Customer(
                        metronome_id=customer_id,
                        name=customer_data.get('name', 'Unnamed Customer'),
                        salesforce_id=customer_data.get('salesforce_id'),
                        rate_card_id=customer_data.get('rate_card_id'),
                        created_at=created_at,
                        last_synced=datetime.now(timezone.utc)
                    )
                    db.session.add(customer)
            
            db.session.commit()
            logging.info(f"Updated {len(all_customers)} customers in database")
            
            # Get updated customers from database with search filter and pagination
            query = Customer.query
            if search_query:
                search = f"%{search_query}%"
                query = query.filter(
                    db.or_(
                        Customer.name.ilike(search),
                        Customer.metronome_id.ilike(search),
                        Customer.salesforce_id.ilike(search)
                    )
                )
            
            # Get sort parameters
            sort_by = request.args.get('sort_by', 'created_at')
            sort_order = request.args.get('sort_order', 'desc')
            
            # Map sort field to model attribute
            sort_field_map = {
                'metronome_id': Customer.metronome_id,
                'name': Customer.name,
                'status': Customer.status,
                'rate_card_id': Customer.rate_card_id,
                'salesforce_id': Customer.salesforce_id,
                'created_at': Customer.created_at
            }
            
            # Get sort field from map, default to created_at if invalid
            sort_field = sort_field_map.get(sort_by, Customer.created_at)
            
            # Apply sort order
            if sort_order == 'desc':
                query = query.order_by(sort_field.desc())
            else:
                query = query.order_by(sort_field.asc())
            
            # Paginate results
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            customers = pagination.items
            
            return render_template('customers.html', 
                                customers=customers, 
                                pagination=pagination,
                                search_query=search_query,
                                sort_by=sort_by,
                                sort_order=sort_order)
        else:
            error_msg = f"Failed to fetch customers: {response.text}"
            logging.error(error_msg)
            flash(error_msg, "danger")
            return render_template('customers.html', 
                                customers=[], 
                                pagination=None,
                                search_query=search_query)
            
    except Exception as e:
        error_msg = f"Error loading customers: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback:")
        flash(error_msg, "danger")
        return render_template('customers.html', 
                            customers=[], 
                            pagination=None,
                            search_query=search_query)

def refresh_contracts():
    """Refresh contracts from Metronome API and store in database"""
    try:
        # Import and run the import_contracts script
        from scripts.import_contracts import import_contracts
        success, message = import_contracts()
        if success:
            logging.info(message)
        else:
            logging.error(message)
        return success, message
    except Exception as e:
        error_msg = f"Error refreshing contracts: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback:")
        return False, error_msg

@app.route('/contracts')
def contracts():
    try:
        # Get contracts from database
        contracts = Contract.query.all()
        
        # Convert database objects to dictionaries for template
        contracts_list = []
        for contract in contracts:
            contracts_list.append({
                'id': contract.id,
                'customer_id': contract.customer.metronome_id if contract.customer else None,
                'customer_name': contract.customer.name if contract.customer else 'Unknown Customer',
                'name': contract.name,
                'product_name': contract.product_name,
                'rate_card_name': contract.rate_card_name,
                'status': contract.status,
                'starting_at': contract.starting_at.strftime('%Y-%m-%d %H:%M:%S') if contract.starting_at else None,
                'ending_before': contract.ending_before.strftime('%Y-%m-%d %H:%M:%S') if contract.ending_before else None
            })
        
        return render_template('contracts.html', contracts=contracts_list)
        
    except Exception as e:
        error_msg = f"Error loading contracts: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback:")
        flash(error_msg, 'danger')
        return render_template('contracts.html', contracts=[])

@app.route('/usage', methods=['GET', 'POST'])
def usage():
    return render_template('usage.html')

@app.route('/generate_usage', methods=['POST'])
def generate_usage():
    try:
        customer_id = request.form['customer_id']
        days = int(request.form.get('days', 7))
        events_per_day = int(request.form.get('events_per_day', 20))
        event_types = request.form.getlist('event_types')
        
        if not event_types:
            flash('Please select at least one event type', 'danger')
            return redirect(url_for('usage'))
        
        # Initialize API
        api = MetronomeAPI(api_key=metronome_api_key)
        
        # Verify customer exists
        url = f"{api.BASE_URL}/customers/{customer_id}"
        headers = {
            "Authorization": f"Bearer {metronome_api_key}",
            "Accept": "application/json"
        }
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            flash(f'Customer not found: {customer_id}', 'danger')
            return redirect(url_for('usage'))
        
        # Generate events
        events = []
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        models = [
            'gpt-3.5-turbo',
            'gpt-4',
            'claude-2',
            'claude-instant'
        ]
        
        current_date = start_date
        while current_date < datetime.now(timezone.utc):
            # More events during business hours (8am-6pm UTC)
            hour = current_date.hour
            is_business_hours = 8 <= hour <= 18
            day_multiplier = 1.5 if is_business_hours else 0.5
            
            # Generate events for this hour
            hourly_events = int(events_per_day * day_multiplier / 24)
            
            for _ in range(hourly_events):
                timestamp = current_date + timedelta(minutes=np.random.randint(60))
                
                if 'token_usage' in event_types:
                    # Choose model
                    model = np.random.choice(models)
                    
                    # Generate input and output tokens
                    input_tokens = np.random.randint(100, 2000)
                    output_tokens = np.random.randint(50, input_tokens)
                    
                    # Add input event
                    events.append({
                        'transaction_id': f"{timestamp.isoformat()}_{customer_id}_{model}_input",
                        'customer_id': customer_id,
                        'event_type': 'token_usage',
                        'timestamp': timestamp.isoformat(),
                        'properties': {
                            'type': 'input',
                            'model_name': model,
                            'token_count': input_tokens
                        }
                    })
                    
                    # Add output event
                    events.append({
                        'transaction_id': f"{timestamp.isoformat()}_{customer_id}_{model}_output",
                        'customer_id': customer_id,
                        'event_type': 'token_usage',
                        'timestamp': timestamp.isoformat(),
                        'properties': {
                            'type': 'output',
                            'model_name': model,
                            'token_count': output_tokens
                        }
                    })
                
                if 'gpu_usage' in event_types and np.random.random() < 0.2:  # 20% chance of GPU usage
                    gpu_type = f"gpu_type_{np.random.randint(1, 4)}"
                    gpu_hours = round(np.random.uniform(0.1, 2.0), 3)  # Between 6 minutes and 2 hours
                    
                    events.append({
                        'transaction_id': f"{timestamp.isoformat()}_{customer_id}_{gpu_type}",
                        'customer_id': customer_id,
                        'event_type': 'gpu_usage',
                        'timestamp': timestamp.isoformat(),
                        'properties': {
                            'type': gpu_type,
                            'hours': gpu_hours
                        }
                    })
            
            current_date += timedelta(hours=1)
        
        # Send events to Metronome
        batch_size = 100
        url = f"{api.BASE_URL}/ingest"
        headers = {
            "Authorization": f"Bearer {metronome_api_key}",
            "Content-Type": "application/json"
        }
        
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            response = requests.post(url, headers=headers, json=batch)
            if response.status_code != 200:
                flash(f'Error sending events batch {i//batch_size + 1}: {response.text}', 'danger')
                return redirect(url_for('usage'))
        
        flash(f'Successfully generated and sent {len(events)} usage events', 'success')
        return render_template('usage.html', events=events[:100])  # Show first 100 events
        
    except Exception as e:
        error_msg = f'Error generating usage: {str(e)}'
        logging.error(error_msg)
        logging.exception("Full traceback:")
        flash(error_msg, 'danger')
        return redirect(url_for('usage'))

@app.route('/logs')
def view_logs():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        search_query = request.args.get('search', '').strip()
        level = request.args.get('level', '').strip().upper()

        # Start with base query
        query = LogEntry.query

        # Apply search filter if provided
        if search_query:
            search = f"%{search_query}%"
            query = query.filter(LogEntry.message.ilike(search))

        # Apply level filter if provided
        if level in ['INFO', 'WARNING', 'ERROR']:
            query = query.filter(LogEntry.level == level)

        # Order by timestamp descending
        query = query.order_by(LogEntry.timestamp.desc())

        # Paginate results
        logs = query.paginate(page=page, per_page=per_page)

        return render_template('logs.html', 
                            logs=logs,
                            search_query=search_query,
                            level=level)
    except Exception as e:
        error_msg = f"Error viewing logs: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback:")
        flash(error_msg, 'danger')
        return render_template('logs.html', logs=None)

@app.route('/preferences')
def preferences():
    return render_template('preferences.html',
                         metronome_api_key=metronome_api_key,
                         stripe_api_key=stripe.api_key)

@app.route('/preferences', methods=['POST'])
def save_preferences():
    global metronome_api_key, stripe_api_key
    
    new_metronome_key = request.form.get('metronome_api_key')
    new_stripe_key = request.form.get('stripe_api_key')
    
    if new_metronome_key:
        metronome_api_key = new_metronome_key
        os.environ['METRONOME_API_KEY'] = new_metronome_key
    
    if new_stripe_key:
        stripe.api_key = new_stripe_key
        os.environ['STRIPE_API_KEY'] = new_stripe_key
    
    flash('Preferences saved successfully!', 'success')
    return redirect(url_for('preferences'))

@app.route('/admin')
def admin():
    # Get counts from database
    customer_count = Customer.query.count()
    product_count = Product.query.count()
    contract_count = Contract.query.count()
    return render_template('admin.html',
                         customer_count=customer_count,
                         product_count=product_count,
                         contract_count=contract_count)

@app.route('/admin/refresh-contracts', methods=['POST'])
def refresh_contracts_route():
    success, message = refresh_contracts()
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    return redirect(url_for('admin'))

@app.route('/admin/refresh-products', methods=['POST'])
def refresh_products_route():
    success, message = refresh_products()
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    return redirect(url_for('admin'))

@app.route('/admin/refresh-database', methods=['POST'])
def refresh_database():
    try:
        # First refresh products
        success, message = refresh_products()
        if not success:
            flash(message, "danger")
            return redirect(url_for('admin'))
        
        # Then fetch all customers from Metronome
        all_customers = []
        next_page = None
        base_url = "https://api.metronome.com/v1/customers"
        headers = {
            "Authorization": f"Bearer {metronome_api_key}",
            "Accept": "application/json"
        }

        while True:
            # Make API request with pagination token if available
            params = {}
            if next_page:
                params["next_page"] = next_page  # Using correct parameter name from API docs
                logging.info(f"Fetching next page with token: {next_page}")
            
            response = requests.get(base_url, headers=headers, params=params)
            logging.info(f"Request URL: {response.url}")  # Log the full URL to verify parameters
            logging.info(f"Customers response status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if not isinstance(data, dict):
                        logging.error("Unexpected response format - not a dictionary")
                        break
                        
                    if 'data' not in data or not isinstance(data['data'], list):
                        logging.error("Unexpected response format - missing data array")
                        break
                        
                    # Add customers from current page
                    current_page_customers = len(data['data'])
                    all_customers.extend(data['data'])
                    logging.info(f"Fetched {current_page_customers} customers (total: {len(all_customers)})")
                    
                    # Log the current data structure for debugging
                    logging.info(f"Response data structure: {json.dumps(data, indent=2)}")
                    
                    # Get next page token
                    next_page = data.get('next_page')  # API returns 'next_page', not 'next_page_token'
                    if next_page:
                        logging.info(f"Found next page token: {next_page}, continuing to next page")
                        # Add a small delay between requests to avoid rate limiting
                        time.sleep(0.5)
                        continue  # Continue to next iteration to fetch next page
                    else:
                        logging.info("No more pages to fetch")
                        break
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse JSON response: {e}")
                    break
            else:
                error_msg = f"Failed to fetch customers: {response.text}"
                logging.error(error_msg)
                flash(error_msg, "danger")
                return redirect(url_for('admin'))

        # Update local database with all customers
        updated_count = 0
        created_count = 0
        if all_customers:
            logging.info(f"Starting database update with {len(all_customers)} customers")
            
            # First, get all existing customers for bulk comparison
            existing_customers = {c.metronome_id: c for c in Customer.query.all()}
            logging.info(f"Found {len(existing_customers)} existing customers in database")
            
            for customer_data in all_customers:
                customer_id = customer_data.get('id')
                if not customer_id:
                    logging.warning(f"Skipping customer with no ID: {customer_data}")
                    continue
                
                # Parse created_at if present
                created_at = None
                if 'created_at' in customer_data:
                    try:
                        created_at = datetime.fromisoformat(customer_data['created_at'].replace('Z', '+00:00'))
                    except (ValueError, AttributeError) as e:
                        logging.warning(f"Error parsing created_at for customer {customer_id}: {e}")
                
                customer = existing_customers.get(customer_id)
                if customer:
                    # Update existing customer
                    customer.name = customer_data.get('name', 'Unnamed Customer')
                    customer.salesforce_id = customer_data.get('salesforce_id')
                    customer.rate_card_id = customer_data.get('rate_card_id')
                    customer.created_at = created_at
                    customer.last_synced = datetime.now(timezone.utc)
                    updated_count += 1
                else:
                    # Create new customer
                    customer = Customer(
                        metronome_id=customer_id,
                        name=customer_data.get('name', 'Unnamed Customer'),
                        salesforce_id=customer_data.get('salesforce_id'),
                        rate_card_id=customer_data.get('rate_card_id'),
                        created_at=created_at,
                        last_synced=datetime.now(timezone.utc)
                    )
                    db.session.add(customer)
                    created_count += 1
                
                # Commit every 100 customers to avoid memory issues
                if (updated_count + created_count) % 100 == 0:
                    db.session.commit()
                    logging.info(f"Committed batch of 100 customers (Updated: {updated_count}, Created: {created_count})")
            
            # Final commit for remaining customers
            db.session.commit()
            customer_message = f"Successfully refreshed customers. Updated {updated_count} and created {created_count} customers."
            logging.info(customer_message)
            flash(customer_message, "success")
        else:
            flash("No customers found to update.", "warning")
        
        # Finally refresh contracts
        success, contract_message = refresh_contracts()
        if success:
            flash(contract_message, "success")
        else:
            flash(contract_message, "danger")
        
        return redirect(url_for('admin'))
            
    except Exception as e:
        error_msg = f"Error refreshing database: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback:")
        flash(error_msg, "danger")
        return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8082, debug=True)
