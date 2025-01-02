from flask import Flask, render_template
import pandas as pd
import os

app = Flask(__name__)

def get_customer_stats():
    # Get the parent directory path
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Read the CSV files
    all_customers_path = os.path.join(parent_dir, 'all_customers.csv')
    current_customers_path = os.path.join(parent_dir, 'current_customers.csv')
    
    all_customers = pd.read_csv(all_customers_path)
    current_customers = pd.read_csv(current_customers_path)
    
    return {
        'total_customers': len(all_customers),
        'active_customers': len(current_customers)
    }

@app.route('/')
def index():
    stats = get_customer_stats()
    return render_template('index.html', 
                         total_customers=stats['total_customers'],
                         active_customers=stats['active_customers'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)