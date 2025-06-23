#!/usr/bin/env python3
import requests
import json
import datetime
import uuid
from typing import Dict, Any, List, Optional
import os
import sys
import time

# Get the backend URL from the frontend .env file
with open('/app/frontend/.env', 'r') as f:
    for line in f:
        if line.startswith('REACT_APP_BACKEND_URL='):
            BACKEND_URL = line.strip().split('=')[1].strip('"\'')
            break

# Ensure we have a valid backend URL
if not BACKEND_URL:
    print("Error: Could not find REACT_APP_BACKEND_URL in frontend/.env")
    sys.exit(1)

# Add /api to the backend URL
API_URL = f"{BACKEND_URL}/api"

print(f"Using API URL: {API_URL}")

# Test results tracking
test_results = {
    "client_api": {
        "create": False,
        "list": False,
        "get": False,
        "update": False,
        "delete": False
    },
    "invoice_api": {
        "create": False,
        "list": False,
        "get": False,
        "update": False,
        "delete": False
    },
    "dashboard_api": {
        "stats": False
    }
}

# Helper function to format dates for JSON
def json_serial(obj):
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# Test Client API
def test_client_api():
    print("\n=== Testing Client API ===")
    
    # Create a client
    print("\n--- Testing Client Creation ---")
    client_data = {
        "nom": "Entreprise Dupont",
        "email": "contact@dupont.fr",
        "telephone": "+33123456789",
        "adresse": "123 Rue de Paris",
        "ville": "Paris",
        "code_postal": "75001",
        "pays": "France"
    }
    
    try:
        response = requests.post(f"{API_URL}/clients", json=client_data)
        response.raise_for_status()
        client = response.json()
        print(f"Created client: {client['nom']} with ID: {client['id']}")
        test_results["client_api"]["create"] = True
        
        # Test listing clients
        print("\n--- Testing Client Listing ---")
        response = requests.get(f"{API_URL}/clients")
        response.raise_for_status()
        clients = response.json()
        print(f"Found {len(clients)} clients")
        test_results["client_api"]["list"] = True
        
        # Test getting a specific client
        print(f"\n--- Testing Get Client by ID ---")
        client_id = client["id"]
        response = requests.get(f"{API_URL}/clients/{client_id}")
        response.raise_for_status()
        retrieved_client = response.json()
        print(f"Retrieved client: {retrieved_client['nom']}")
        test_results["client_api"]["get"] = True
        
        # Test updating a client
        print(f"\n--- Testing Client Update ---")
        update_data = {
            "nom": "Entreprise Dupont & Fils",
            "email": "nouveau@dupont.fr"
        }
        response = requests.put(f"{API_URL}/clients/{client_id}", json=update_data)
        response.raise_for_status()
        updated_client = response.json()
        print(f"Updated client name to: {updated_client['nom']}")
        test_results["client_api"]["update"] = True
        
        # Create an invoice for this client to test deletion constraint
        print("\n--- Creating invoice to test client deletion constraint ---")
        invoice_data = {
            "client_id": client_id,
            "date_echeance": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
            "items": [
                {
                    "description": "Service de consultation",
                    "quantite": 2,
                    "prix_unitaire": 100.0,
                    "total": 200.0
                }
            ],
            "taux_tva": 20.0,
            "notes": "Test invoice for client deletion constraint"
        }
        
        invoice_response = requests.post(f"{API_URL}/invoices", json=invoice_data)
        invoice_response.raise_for_status()
        invoice = invoice_response.json()
        print(f"Created test invoice with ID: {invoice['id']}")
        
        # Test client deletion with existing invoices (should fail)
        print("\n--- Testing Client Deletion Constraint ---")
        delete_response = requests.delete(f"{API_URL}/clients/{client_id}")
        if delete_response.status_code == 400:
            print("Correctly prevented deletion of client with invoices")
            
            # Delete the invoice first
            print("\n--- Deleting test invoice ---")
            invoice_delete_response = requests.delete(f"{API_URL}/invoices/{invoice['id']}")
            invoice_delete_response.raise_for_status()
            print(f"Deleted test invoice")
            
            # Now try deleting the client again
            print("\n--- Testing Client Deletion ---")
            delete_response = requests.delete(f"{API_URL}/clients/{client_id}")
            delete_response.raise_for_status()
            print(f"Successfully deleted client")
            test_results["client_api"]["delete"] = True
        else:
            print(f"ERROR: Expected 400 status code for client with invoices, got {delete_response.status_code}")
            print(delete_response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"Error testing client API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return False
    
    return all(test_results["client_api"].values())

# Test Invoice API
def test_invoice_api():
    print("\n=== Testing Invoice API ===")
    
    # First create a client for the invoices
    print("\n--- Creating test client for invoices ---")
    client_data = {
        "nom": "Société Martin",
        "email": "contact@martin.fr",
        "telephone": "+33987654321",
        "adresse": "456 Avenue de Lyon",
        "ville": "Lyon",
        "code_postal": "69001",
        "pays": "France"
    }
    
    try:
        client_response = requests.post(f"{API_URL}/clients", json=client_data)
        client_response.raise_for_status()
        client = client_response.json()
        client_id = client["id"]
        print(f"Created test client with ID: {client_id}")
        
        # Create an invoice
        print("\n--- Testing Invoice Creation ---")
        invoice_data = {
            "client_id": client_id,
            "date_echeance": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
            "items": [
                {
                    "description": "Développement web",
                    "quantite": 10,
                    "prix_unitaire": 75.0,
                    "total": 750.0
                },
                {
                    "description": "Hébergement annuel",
                    "quantite": 1,
                    "prix_unitaire": 120.0,
                    "total": 120.0
                }
            ],
            "taux_tva": 20.0,
            "notes": "Paiement à 30 jours"
        }
        
        response = requests.post(f"{API_URL}/invoices", json=invoice_data)
        response.raise_for_status()
        invoice = response.json()
        print(f"Created invoice: {invoice['numero']} with ID: {invoice['id']}")
        print(f"Invoice total: {invoice['total']} €")
        
        # Verify automatic calculations
        expected_sous_total = 10 * 75.0 + 1 * 120.0  # 870.0
        expected_tva = expected_sous_total * 0.2  # 174.0
        expected_total = expected_sous_total + expected_tva  # 1044.0
        
        calculation_correct = (
            abs(invoice['sous_total'] - expected_sous_total) < 0.01 and
            abs(invoice['montant_tva'] - expected_tva) < 0.01 and
            abs(invoice['total'] - expected_total) < 0.01
        )
        
        if calculation_correct:
            print("Invoice calculations are correct")
            test_results["invoice_api"]["create"] = True
        else:
            print(f"ERROR: Invoice calculations are incorrect")
            print(f"Expected: sous_total={expected_sous_total}, tva={expected_tva}, total={expected_total}")
            print(f"Got: sous_total={invoice['sous_total']}, tva={invoice['montant_tva']}, total={invoice['total']}")
        
        # Test listing invoices
        print("\n--- Testing Invoice Listing ---")
        response = requests.get(f"{API_URL}/invoices")
        response.raise_for_status()
        invoices = response.json()
        print(f"Found {len(invoices)} invoices")
        test_results["invoice_api"]["list"] = True
        
        # Test getting a specific invoice
        print(f"\n--- Testing Get Invoice by ID ---")
        invoice_id = invoice["id"]
        response = requests.get(f"{API_URL}/invoices/{invoice_id}")
        response.raise_for_status()
        retrieved_invoice = response.json()
        print(f"Retrieved invoice: {retrieved_invoice['numero']}")
        test_results["invoice_api"]["get"] = True
        
        # Test updating an invoice
        print(f"\n--- Testing Invoice Update ---")
        update_data = {
            "statut": "envoyée",
            "items": [
                {
                    "description": "Développement web",
                    "quantite": 12,  # Changed from 10 to 12
                    "prix_unitaire": 75.0,
                    "total": 900.0
                },
                {
                    "description": "Hébergement annuel",
                    "quantite": 1,
                    "prix_unitaire": 120.0,
                    "total": 120.0
                }
            ]
        }
        response = requests.put(f"{API_URL}/invoices/{invoice_id}", json=update_data)
        response.raise_for_status()
        updated_invoice = response.json()
        print(f"Updated invoice status to: {updated_invoice['statut']}")
        print(f"Updated invoice total: {updated_invoice['total']} €")
        
        # Verify recalculation
        expected_sous_total = 12 * 75.0 + 1 * 120.0  # 1020.0
        expected_tva = expected_sous_total * 0.2  # 204.0
        expected_total = expected_sous_total + expected_tva  # 1224.0
        
        recalculation_correct = (
            abs(updated_invoice['sous_total'] - expected_sous_total) < 0.01 and
            abs(updated_invoice['montant_tva'] - expected_tva) < 0.01 and
            abs(updated_invoice['total'] - expected_total) < 0.01
        )
        
        if recalculation_correct:
            print("Invoice recalculations are correct")
            test_results["invoice_api"]["update"] = True
        else:
            print(f"ERROR: Invoice recalculations are incorrect")
            print(f"Expected: sous_total={expected_sous_total}, tva={expected_tva}, total={expected_total}")
            print(f"Got: sous_total={updated_invoice['sous_total']}, tva={updated_invoice['montant_tva']}, total={updated_invoice['total']}")
        
        # Test invoice deletion
        print(f"\n--- Testing Invoice Deletion ---")
        response = requests.delete(f"{API_URL}/invoices/{invoice_id}")
        response.raise_for_status()
        print(f"Successfully deleted invoice")
        test_results["invoice_api"]["delete"] = True
        
        # Clean up - delete the test client
        print("\n--- Cleaning up: Deleting test client ---")
        requests.delete(f"{API_URL}/clients/{client_id}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error testing invoice API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return False
    
    return all(test_results["invoice_api"].values())

# Test Dashboard API
def test_dashboard_api():
    print("\n=== Testing Dashboard API ===")
    
    try:
        # Create test data for dashboard
        print("\n--- Creating test data for dashboard ---")
        
        # Create a client
        client_data = {
            "nom": "Entreprise Bernard",
            "email": "contact@bernard.fr"
        }
        client_response = requests.post(f"{API_URL}/clients", json=client_data)
        client_response.raise_for_status()
        client = client_response.json()
        client_id = client["id"]
        
        # Create invoices with different statuses
        statuses = ["brouillon", "envoyée", "payée", "en_retard"]
        for i, status in enumerate(statuses):
            invoice_data = {
                "client_id": client_id,
                "date_echeance": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
                "items": [
                    {
                        "description": f"Service {i+1}",
                        "quantite": 1,
                        "prix_unitaire": 100.0 * (i+1),
                        "total": 100.0 * (i+1)
                    }
                ],
                "taux_tva": 20.0
            }
            
            # Create invoice
            invoice_response = requests.post(f"{API_URL}/invoices", json=invoice_data)
            invoice_response.raise_for_status()
            invoice = invoice_response.json()
            
            # Update status if not draft
            if status != "brouillon":
                update_data = {"statut": status}
                requests.put(f"{API_URL}/invoices/{invoice['id']}", json=update_data)
        
        # Test dashboard stats
        print("\n--- Testing Dashboard Stats ---")
        response = requests.get(f"{API_URL}/dashboard/stats")
        response.raise_for_status()
        stats = response.json()
        
        print(f"Dashboard stats:")
        print(f"Total clients: {stats['total_clients']}")
        print(f"Total invoices: {stats['total_invoices']}")
        print(f"Total revenue: {stats['total_revenue']} €")
        print(f"Status breakdown: {json.dumps(stats['status_breakdown'], indent=2)}")
        
        # Verify stats
        if stats['total_clients'] >= 1 and stats['total_invoices'] >= 4:
            print("Dashboard stats look correct")
            test_results["dashboard_api"]["stats"] = True
        else:
            print("ERROR: Dashboard stats don't match expected values")
        
        # Clean up - delete the invoices and client
        print("\n--- Cleaning up dashboard test data ---")
        
        # Get all invoices for this client
        invoices_response = requests.get(f"{API_URL}/invoices")
        invoices = invoices_response.json()
        
        for invoice in invoices:
            if invoice['client_id'] == client_id:
                requests.delete(f"{API_URL}/invoices/{invoice['id']}")
        
        # Delete the client
        requests.delete(f"{API_URL}/clients/{client_id}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error testing dashboard API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return False
    
    return all(test_results["dashboard_api"].values())

# Run all tests
def run_all_tests():
    print("\n=== Starting Backend API Tests ===")
    print(f"Testing against API URL: {API_URL}")
    
    # Run tests
    client_success = test_client_api()
    invoice_success = test_invoice_api()
    dashboard_success = test_dashboard_api()
    
    # Print summary
    print("\n=== Test Results Summary ===")
    
    print("\nClient API:")
    for test, result in test_results["client_api"].items():
        print(f"  {test.capitalize()}: {'✅ PASS' if result else '❌ FAIL'}")
    
    print("\nInvoice API:")
    for test, result in test_results["invoice_api"].items():
        print(f"  {test.capitalize()}: {'✅ PASS' if result else '❌ FAIL'}")
    
    print("\nDashboard API:")
    for test, result in test_results["dashboard_api"].items():
        print(f"  {test.capitalize()}: {'✅ PASS' if result else '❌ FAIL'}")
    
    all_success = client_success and invoice_success and dashboard_success
    print(f"\nOverall Test Result: {'✅ PASS' if all_success else '❌ FAIL'}")
    
    return all_success

if __name__ == "__main__":
    run_all_tests()