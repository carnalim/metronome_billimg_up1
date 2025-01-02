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
from models import db, LogEntry, Customer

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
            # Ensure we're in an application context
            if not app.app_context():
                with app.app_context():
                    self._emit(record)
            else:
                self._emit(record)
        except Exception as e:
            print(f"Error in DatabaseHandler: {e}")
    
    def _emit(self, record):
        try:
            log_entry = LogEntry(
                level=record.levelname,
                message=self.format(record)
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            print(f"Error saving log to database: {e}")
            db.session.rollback()

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
    url = f"{api.BASE_URL}/contracts/create"
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
            stripe.api_key = stripe_api_key
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
                metronome_customer = response.json()
                
                # Save customer to local database
                customer = Customer(
                    metronome_id=metronome_customer['id'],
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
        url = "https://api.metronome.com/v1/contract-pricing/rate-cards/list"
        headers = {
            "Authorization": f"Bearer {metronome_api_key}",
            "Content-Type": "application/json"
        }
        
        logging.info("Fetching rate cards")
        response = requests.post(url, headers=headers, json={})
        logging.info(f"Rate cards response status: {response.status_code}")
        logging.info(f"Rate cards response: {response.text}")
        
        if response.status_code == 200:
            response_data = response.json()
            if isinstance(response_data, dict):
                rate_cards = response_data.get('data', [])
            else:
                rate_cards = response_data if isinstance(response_data, list) else []
            
            logging.info(f"Found {len(rate_cards)} rate cards")
            
            if not rate_cards:
                flash("No rate cards found. Please create a rate card first.", "warning")
        else:
            rate_cards = []
            error_msg = f"Failed to fetch rate cards: {response.text}"
            logging.error(error_msg)
            flash(error_msg, "warning")
        
        return render_template('create.html', rate_cards=rate_cards, response_data=response_data)
        
    except Exception as e:
        error_msg = f"Error creating customer: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback:")
        flash(error_msg, "danger")
        response_data['error'] = str(e)
        return render_template('create.html', rate_cards=[], response_data=response_data)

@app.route('/rate-cards')
def rate_cards():
    try:
        # Make API request
        url = "https://api.metronome.com/v1/contract-pricing/rate-cards/list"
        headers = {
            "Authorization": f"Bearer {metronome_api_key}",
            "Content-Type": "application/json"
        }
        
        logging.info("Fetching rate cards")
        response = requests.post(url, headers=headers, json={})
        logging.info(f"Rate cards response status: {response.status_code}")
        logging.info(f"Rate cards response: {response.text}")
        
        if response.status_code == 200:
            response_data = response.json()
            if isinstance(response_data, dict):
                rate_cards = response_data.get('data', [])
            else:
                rate_cards = response_data if isinstance(response_data, list) else []
            
            logging.info(f"Found {len(rate_cards)} rate cards")
            return render_template('rate_cards.html', rate_cards=rate_cards)
        else:
            error_msg = f"Failed to fetch rate cards: {response.text}"
            logging.error(error_msg)
            flash(error_msg, 'danger')
            return render_template('rate_cards.html', rate_cards=[])
            
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
        per_page = 25
        
        # Make API request to list customers
        response = requests.get(
            "https://api.metronome.com/v1/customers",
            headers={
                "Authorization": f"Bearer {metronome_api_key}",
            },
        )
        
        logging.info(f"Customers response status: {response.status_code}")
        logging.info(f"Customers response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            customers_list = data.get('data', []) if isinstance(data, dict) else data
            
            # Update local database with customers
            for customer_data in customers_list:
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
            logging.info(f"Updated {len(customers_list)} customers in database")
            
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
            
            # Order by name
            query = query.order_by(Customer.name)
            
            # Paginate results
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            customers = pagination.items
            
            return render_template('customers.html', 
                                customers=customers, 
                                pagination=pagination,
                                search_query=search_query)
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

@app.route('/customers/<customer_id>/credits', methods=['GET', 'POST'])
def add_credits(customer_id):
    try:
        # Get customer details
        customer = Customer.query.filter_by(metronome_id=customer_id).first_or_404()
        
        if request.method == 'POST':
            # Get form data
            name = request.form.get('name')
            priority = int(request.form.get('priority', 100))
            product_id = request.form.get('product_id')
            credit_type_id = request.form.get('credit_type_id')
            amount = float(request.form.get('amount'))
            starting_at = request.form.get('starting_at')
            ending_before = request.form.get('ending_before')
            
            # Convert datetime-local to UTC ISO format
            starting_at = datetime.fromisoformat(starting_at).astimezone(timezone.utc).isoformat()
            ending_before = datetime.fromisoformat(ending_before).astimezone(timezone.utc).isoformat()
            
            # Prepare request data
            json_data = {
                "customer_id": customer_id,
                "name": name,
                "priority": priority,
                "product_id": product_id,
                "access_schedule": {
                    "credit_type_id": credit_type_id,
                    "schedule_items": [
                        {
                            "amount": amount,
                            "starting_at": starting_at,
                            "ending_before": ending_before,
                        }
                    ],
                },
            }
            
            # Make API request
            url = "https://api.metronome.com/v1/contracts/customerCredits/create"
            headers = {
                "Authorization": f"Bearer {metronome_api_key}",
            }
            
            logging.info(f"Adding credits for customer {customer_id}")
            logging.info(f"Request data: {json_data}")
            
            response = requests.post(url, headers=headers, json=json_data)
            logging.info(f"Response status: {response.status_code}")
            logging.info(f"Response body: {response.text}")
            
            if response.status_code == 200:
                flash("Credits added successfully", "success")
                return redirect(url_for('customers'))
            else:
                flash(f"Failed to add credits: {response.text}", "danger")
        
        # Get customer's active contract to get the product ID
        contracts_url = f"https://api.metronome.com/v1/customers/{customer_id}/contracts"
        contracts_response = requests.get(
            contracts_url,
            headers={"Authorization": f"Bearer {metronome_api_key}"}
        )
        
        active_contract = None
        if contracts_response.status_code == 200:
            contracts = contracts_response.json()
            if not isinstance(contracts, list):
                contracts = [contracts]
            active_contract = next(
                (c for c in contracts if isinstance(c, dict) and c.get('status') == 'active'),
                None
            )
            logging.info(f"Active contract: {active_contract}")
        
        # Get products for the form
        if active_contract and active_contract.get('product_id'):
            # If customer has an active contract, get that product
            product_id = active_contract.get('product_id')
            product_url = f"https://api.metronome.com/v1/products/{product_id}"
            product_response = requests.get(
                product_url,
                headers={"Authorization": f"Bearer {metronome_api_key}"}
            )
            if product_response.status_code == 200:
                products = [product_response.json()]
            else:
                products = []
                logging.error(f"Failed to fetch product: {product_response.text}")
        else:
            # Otherwise get all products
            products_response = requests.get(
                "https://api.metronome.com/v1/products",
                headers={"Authorization": f"Bearer {metronome_api_key}"}
            )
            if products_response.status_code == 200:
                products = products_response.json()
                if not isinstance(products, list):
                    products = [products]
            else:
                products = []
                logging.error(f"Failed to fetch products: {products_response.text}")
        
        # Get credit types from the active contract's rate card
        credit_types = []
        if active_contract and active_contract.get('rate_card_id'):
            rate_card_id = active_contract.get('rate_card_id')
            rate_card_url = f"https://api.metronome.com/v1/contract-pricing/rate-cards/{rate_card_id}"
            rate_card_response = requests.get(
                rate_card_url,
                headers={"Authorization": f"Bearer {metronome_api_key}"}
            )
            if rate_card_response.status_code == 200:
                rate_card = rate_card_response.json()
                # Extract credit types from rate card pricing
                pricing = rate_card.get('pricing', {})
                for item in pricing.get('items', []):
                    if item.get('credit_type_id'):
                        credit_types.append({
                            'id': item['credit_type_id'],
                            'name': item.get('name', 'Unknown Credit Type')
                        })
        
        if not credit_types:
            flash("No credit types found in the rate card. Please ensure the customer has an active contract with a rate card.", "warning")
        
        return render_template('add_credits.html', 
                             customer=customer,
                             products=products,
                             credit_types=credit_types,
                             active_contract=active_contract)
                             
    except Exception as e:
        error_msg = f"Error adding credits: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback:")
        flash(error_msg, "danger")
        return redirect(url_for('customers'))

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
        logs = LogEntry.query.order_by(LogEntry.timestamp.desc()).paginate(page=page, per_page=per_page)
        return render_template('logs.html', logs=logs)
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8082, debug=True)