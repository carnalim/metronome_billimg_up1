import requests
import csv

api_key = "76d6d17428784bf44e1971074ca1ac9a4079bb4d81a508cd47e0a650567f471d"
api_url = "https://api.metronome.com/v1/billable-metrics"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

response = requests.get(api_url, headers=headers)

if response.status_code == 200:
    print(response.json())
    with open('current_billable_metrics.csv', 'w', newline='') as csvfile:
        fieldnames = ['id', 'name', 'custom_fields', 'group_keys', 'event_type_filter', 'property_filters', 'aggregation_type', 'aggregation_key']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for metric in response.json()['data']:
            writer.writerow(metric)
else:
    print(f"Failed to retrieve billable metrics. Status code: {response.status_code}")