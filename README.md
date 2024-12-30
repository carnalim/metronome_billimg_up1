# Metronome Billing

A Python-based billing system for managing metered usage and invoicing.

## Features

- Automated customer setup in Metronome and Stripe
- Customer linking between platforms
- Contract creation with rate cards
- Usage tracking
- Billing calculations
- Invoice generation
- Payment processing

## Getting Started

### Prerequisites

- Python 3.8+
- pip

### Installation

1. Clone the repository:
```bash
git clone https://github.com/carnalim/metronome_billing_up1.git
cd metronome_billing_up1
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Customer Setup

The `scripts/full_customer_setup.py` script automates the process of setting up a new customer in both Metronome and Stripe. It performs the following steps:

1. Creates a new customer in Metronome
2. Creates a corresponding customer in Stripe
3. Links the Metronome and Stripe customers
4. Creates a contract with a specified rate card

To run the script:

```bash
cd scripts
python3 full_customer_setup.py
```

#### Configuration

The script requires the following environment variables or configuration:

- `METRONOME_API_KEY`: Your Metronome API key
- `STRIPE_API_KEY`: Your Stripe API key
- Rate Card ID: Currently set to "ee186f96-3e72-4f7c-a326-a88a28e4b7da"

#### Example Output

```
✓ Using default rate card: ee186f96-3e72-4f7c-a326-a88a28e4b7da
Creating customer in Metronome...
✓ Created Metronome customer: Sample Company Inc.
Creating customer in Stripe...
✓ Created Stripe customer: Sample Company Inc. (ID: cus_xxx)
Linking customers...
✓ Linked customer: Sample Company Inc. (Metronome ID: xxx, Stripe ID: cus_xxx)
Creating contract...
✓ Created contract for customer: Sample Company Inc.
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.