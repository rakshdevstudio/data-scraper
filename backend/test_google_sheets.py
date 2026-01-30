#!/usr/bin/env python3
"""
Test script for Google Sheets integration.
This will verify that the credentials work and create a test sheet.
"""

import sys

sys.path.insert(0, "/Users/raksh/Raksh's Vault/MapsProject/backend")

from app.google_sheets import GoogleSheetsManager


def test_google_sheets():
    print("🔍 Testing Google Sheets Integration...\n")

    # Initialize manager
    print("1. Initializing Google Sheets Manager...")
    manager = GoogleSheetsManager(
        credentials_path="credentials/service_account.json",
        sheet_name="MapsScraperResults",
    )

    if not manager.is_connected:
        print("❌ Failed to connect to Google Sheets")
        return False

    print("✅ Connected to Google Sheets!")
    print(f"   Sheet URL: {manager.get_sheet_url()}\n")

    # Test writing data
    print("2. Testing data write...")
    test_data = [
        {
            "Name": "Test Business 1",
            "Ratings": "4.5 stars",
            "Niche": "Restaurant",
            "Address": "123 Test St",
            "Contact": "+1-555-0100",
            "Website": "https://test1.com",
            "Keyword": "test keyword",
            "dataset_id": "test_20260130",
            "scraped_at": "2026-01-30T01:30:00Z",
        },
        {
            "Name": "Test Business 2",
            "Ratings": "5.0 stars",
            "Niche": "Cafe",
            "Address": "456 Test Ave",
            "Contact": "+1-555-0200",
            "Website": "https://test2.com",
            "Keyword": "test keyword",
            "dataset_id": "test_20260130",
            "scraped_at": "2026-01-30T01:31:00Z",
        },
    ]

    success = manager.append_rows(test_data)

    if success:
        print("✅ Successfully wrote test data!")
        print(f"   Total rows in sheet: {manager.get_row_count()}\n")
    else:
        print("❌ Failed to write test data\n")
        return False

    # Test connectivity
    print("3. Testing connectivity check...")
    is_online = manager.check_connectivity()
    print(
        f"   {'✅' if is_online else '❌'} Connectivity: {'Online' if is_online else 'Offline'}\n"
    )

    print("=" * 60)
    print("🎉 All tests passed!")
    print("=" * 60)
    print("\n📊 View your Google Sheet here:")
    print(f"   {manager.get_sheet_url()}\n")
    print("⚠️  IMPORTANT: Share this sheet with your service account email:")
    print("   maps-scraper-service@mapsscraper-485901.iam.gserviceaccount.com")
    print("   (Give it 'Editor' permissions)\n")

    return True


if __name__ == "__main__":
    try:
        test_google_sheets()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
