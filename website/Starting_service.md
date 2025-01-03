# Starting Metronome Billing Services Manually

## Prerequisites
Ensure you have Python installed and all required dependencies by running:
```bash
pip install -r requirements.txt
```

## Starting the Web Server

1. Set the Python path to include the current directory:
```powershell
# Windows PowerShell
$env:PYTHONPATH = ".;$env:PYTHONPATH"

# Windows CMD
set PYTHONPATH=%PYTHONPATH%;.

# Linux/Mac
export PYTHONPATH="${PYTHONPATH:+${PYTHONPATH}:}./"
```

2. Start the Flask web server:
```bash
python website/app.py
```
The web interface will be available at http://127.0.0.1:8082

## Database
The SQLite database is automatically initialized when starting the web server. It will be created at `website/instance/metronome.db` if it doesn't exist.

## Available Scripts
The following scripts are available in the `scripts/` directory for various operations:

### Customer Management
- `python scripts/create_customers.py` - Create new customers
- `python scripts/list_customers.py` - List all customers
- `python scripts/get_metronome_customers.py` - Get customers from Metronome
- `python scripts/export_customers.py` - Export customer data

### Usage and Billing
- `python scripts/generate_usage.py` - Generate usage data
- `python scripts/generate_usage_with_metrics.py` - Generate usage data with specific metrics
- `python scripts/get_billable_metrics.py` - Get billable metrics
- `python scripts/get_rate_card.py` - Get rate card information

### Contract Management
- `python scripts/create_contracts.py` - Create new contracts
- `python scripts/add_contracts.py` - Add contracts to existing customers

### Stripe Integration
- `python scripts/create_stripe_customers.py` - Create customers in Stripe
- `python scripts/link_metronome_stripe.py` - Link Metronome and Stripe accounts

## Shell Scripts (Linux/Mac only)
The following shell scripts are available:
- `scripts/start.sh` - Start all services
- `scripts/stop.sh` - Stop all services
- `scripts/restart.sh` - Restart all services

## Logs
- Web server logs are stored in `website/server.log`
- The web interface provides a logs view at http://127.0.0.1:8082/logs

## Troubleshooting
1. If you see "Module not found" errors, ensure your PYTHONPATH is set correctly as shown above
2. If the port 8082 is already in use, you may need to stop any existing instances of the web server
3. Check the server logs at `website/server.log` for detailed error messages
