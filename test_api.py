from main import app
from database import SessionLocal
import models
import auth
import urllib.request
import json

db = SessionLocal()
test_user = db.query(models.User).filter(models.User.email == "test_api@test.com").first()
if not test_user:
    test_user = models.User(
        nome="Test API",
        email="test_api@test.com",
        senha_hash=auth.get_password_hash("123456")
    )
    db.add(test_user)
    db.commit()

req = urllib.request.Request(
    'http://127.0.0.1:8000/login', 
    data=b'username=test_api@test.com&password=123456',
    headers={'Content-Type': 'application/x-www-form-urlencoded'}
)
with urllib.request.urlopen(req) as f:
    token = json.loads(f.read().decode('utf-8'))['access_token']

req2 = urllib.request.Request(
    'http://127.0.0.1:8000/transactions',
    data=json.dumps({
        "valor": 1300.87,
        "tipo": "receita",
        "descricao": "Saldo que já possuia."
    }).encode('utf-8'),
    headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
)
try:
    with urllib.request.urlopen(req2) as f2:
        print("Status:", f2.status)
        print("Response:", f2.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("Status:", e.code)
    print("Response:", e.read().decode('utf-8'))
