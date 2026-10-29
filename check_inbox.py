from google_services import get_gmail_service, fetch_real_emails

service = get_gmail_service()
emails = fetch_real_emails(service, max_results=3)

print(f"\n--- S-au extras {len(emails)} emailuri necitite ---\n")
for idx, mail in enumerate(emails, start=1):
    print(f"[{idx}] ID: {mail['id']}")
    print(f"Expeditor: {mail['sender']}")
    print(f"Subiect:   {mail['subject']}")
    print(f"Data:      {mail['date']}")
    print("Corpul mesajului extras:")
    print("-" * 40)
    print(mail["body"])
    print("-" * 40)
    print("\n")