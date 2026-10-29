import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Permisiune doar pentru citire la primul test
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def test_connection():
    creds = None
    # token.json se creează automat la prima rulare cu succes
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("EROARE: Fișierul credentials.json nu a fost găsit în directorul curent!")
                return
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0, open_browser=False)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Conectare la serviciul Gmail
    service = build('gmail', 'v1', credentials=creds)

    # Interogare pentru ultimele 3 mailuri din inbox
    results = service.users().messages().list(userId='me', maxResults=3).execute()
    messages = results.get('messages', [])

    if not messages:
        print("Conexiunea a funcționat, dar inbox-ul pare gol!")
    else:
        print("Conexiune reușită! Ultimele mesaje găsite:")
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
            headers = {h['name']: h['value'] for h in msg_data.get('payload', {}).get('headers', [])}
            print(f"- De la: {headers.get('From', 'Necunoscut')} | Subiect: {headers.get('Subject', 'Fără subiect')}")

if __name__ == '__main__':
    test_connection()