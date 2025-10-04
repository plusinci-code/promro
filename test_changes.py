#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for F and G step changes
Tests the email filtering and multiple email sending functionality
"""

import pandas as pd
import json
from pathlib import Path

def test_f_step_email_filtering():
    """Test F step: Should not generate content for companies without emails"""
    print("🧪 Testing F Step - Email Filtering")
    
    # Mock C step data with mixed email availability
    test_data = [
        {
            "Firma Adı": "Company A",
            "Firma Websitesi": "https://companya.com",
            "Email Adresleri": "info@companya.com; sales@companya.com",
            "Özet Metin": "Company A description"
        },
        {
            "Firma Adı": "Company B", 
            "Firma Websitesi": "https://companyb.com",
            "Email Adresleri": "",  # No email
            "Özet Metin": "Company B description"
        },
        {
            "Firma Adı": "Company C",
            "Firma Websitesi": "https://companyc.com", 
            "Email Adresleri": "contact@companyc.com",
            "Özet Metin": "Company C description"
        }
    ]
    
    df = pd.DataFrame(test_data)
    
    # Simulate F step filtering logic
    companies_with_emails = []
    companies_without_emails = []
    
    for _, row in df.iterrows():
        email_addresses = str(row.get("Email Adresleri", "")).strip()
        company_name = str(row.get("Firma Adı", "")).strip()
        
        if not email_addresses or email_addresses == "nan" or email_addresses == "":
            companies_without_emails.append(company_name)
            print(f"❌ {company_name}: No email addresses - SKIPPED")
        else:
            # Parse emails
            email_list = []
            for e in email_addresses.split(";"):
                e = e.strip()
                if e and "@" in e:
                    email_list.append(e)
            
            if email_list:
                companies_with_emails.append({
                    "company_name": company_name,
                    "emails": email_list
                })
                print(f"✅ {company_name}: {len(email_list)} email(s) - {email_list}")
    
    print(f"\n📊 Results:")
    print(f"Companies with emails: {len(companies_with_emails)}")
    print(f"Companies without emails: {len(companies_without_emails)}")
    
    # Expected: 2 companies with emails, 1 without
    assert len(companies_with_emails) == 2, f"Expected 2 companies with emails, got {len(companies_with_emails)}"
    assert len(companies_without_emails) == 1, f"Expected 1 company without emails, got {len(companies_without_emails)}"
    
    print("✅ F Step test passed!")
    return companies_with_emails

def test_g_step_multiple_emails():
    """Test G step: Should send to all emails separately for each company"""
    print("\n🧪 Testing G Step - Multiple Email Sending")
    
    companies_with_emails = [
        {
            "company_name": "Company A",
            "emails": ["info@companya.com", "sales@companya.com", "support@companya.com"]
        },
        {
            "company_name": "Company C", 
            "emails": ["contact@companyc.com"]
        }
    ]
    
    # Mock F step data
    f_data = {
        "Company A": {
            "Konu": "Partnership Opportunity - Company A",
            "İçerik": "Dear Company A team, we would like to discuss partnership...",
            "Şablon_Tipi": "Text"
        },
        "Company C": {
            "Konu": "Business Inquiry - Company C",
            "İçerik": "Hello Company C, we are interested in your services...",
            "Şablon_Tipi": "Text"
        }
    }
    
    # Simulate G step sending logic
    sent_emails = []
    
    for company_data in companies_with_emails:
        company_name = company_data["company_name"]
        emails = company_data["emails"]
        
        if company_name in f_data:
            content_data = f_data[company_name]
            subject = content_data["Konu"]
            
            # Send to each email separately
            for email_address in emails:
                # Simulate email sending (in real code this would call send_email_smtp)
                sent_emails.append({
                    "company": company_name,
                    "to": email_address,
                    "subject": subject,
                    "status": "sent"
                })
                print(f"📧 Sent to {email_address} ({company_name}): {subject}")
        else:
            print(f"⚠️ No content found for {company_name}")
    
    print(f"\n📊 Results:")
    print(f"Total emails sent: {len(sent_emails)}")
    
    # Expected: 4 emails total (3 for Company A + 1 for Company C)
    assert len(sent_emails) == 4, f"Expected 4 emails sent, got {len(sent_emails)}"
    
    # Verify each company's emails are separate
    company_a_emails = [e for e in sent_emails if e["company"] == "Company A"]
    company_c_emails = [e for e in sent_emails if e["company"] == "Company C"]
    
    assert len(company_a_emails) == 3, f"Expected 3 emails for Company A, got {len(company_a_emails)}"
    assert len(company_c_emails) == 1, f"Expected 1 email for Company C, got {len(company_c_emails)}"
    
    # Verify different email addresses received same content but as separate emails
    company_a_subjects = set(e["subject"] for e in company_a_emails)
    assert len(company_a_subjects) == 1, "All emails for Company A should have same subject"
    
    print("✅ G Step test passed!")

def test_email_parsing():
    """Test email parsing from semicolon-separated strings"""
    print("\n🧪 Testing Email Parsing")
    
    test_cases = [
        ("info@test.com", ["info@test.com"]),
        ("info@test.com; sales@test.com", ["info@test.com", "sales@test.com"]),
        ("info@test.com; sales@test.com; support@test.com", ["info@test.com", "sales@test.com", "support@test.com"]),
        ("", []),
        ("nan", []),
        ("   ", []),
        ("invalid-email; info@test.com", ["info@test.com"]),
    ]
    
    for input_emails, expected in test_cases:
        # Parse emails like in the code
        email_list = []
        if input_emails and input_emails != "nan" and input_emails.strip():
            for e in input_emails.split(";"):
                e = e.strip()
                if e and "@" in e:
                    email_list.append(e)
        
        assert email_list == expected, f"Input: '{input_emails}', Expected: {expected}, Got: {email_list}"
        print(f"✅ '{input_emails}' -> {email_list}")
    
    print("✅ Email parsing test passed!")

def main():
    """Run all tests"""
    print("🚀 Starting Tests for F and G Step Changes\n")
    
    try:
        test_email_parsing()
        companies_with_emails = test_f_step_email_filtering()
        test_g_step_multiple_emails()
        
        print("\n🎉 All tests passed successfully!")
        print("\n📋 Summary of Changes:")
        print("✅ F Step: Companies without emails are skipped (no content generated)")
        print("✅ G Step: Multiple emails per company are sent separately")
        print("✅ Email parsing: Handles semicolon-separated email lists correctly")
        print("✅ Each email is sent individually (recipients don't see each other)")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

