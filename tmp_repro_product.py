from backend.app import app

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user'] = 'test@example.com'
    resp = client.get('/product/1')
    print('status', resp.status_code)
    print(resp.data.decode('utf-8', 'replace')[:2000])
