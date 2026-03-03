from io import BytesIO


def test_root_and_health(client):
    root = client.get('/')
    assert root.status_code == 200
    assert root.json()['status'] == 'success'

    health = client.get('/health')
    assert health.status_code == 200
    assert health.json()['status'] == 'healthy'


def test_create_get_list_merchant(client):
    payload = {
        'merchant_id': 'M100',
        'merchant_name': 'Test Merchant',
        'mcc': '5812',
        'industry': 'Food',
        'annual_volume': 120000,
        'average_ticket': 25,
        'current_rate': 0.018,
        'fixed_fee': 0.30,
    }

    created = client.post('/api/v1/merchants', json=payload)
    assert created.status_code == 201
    assert created.json()['merchant_id'] == 'M100'

    fetched = client.get('/api/v1/merchants/M100')
    assert fetched.status_code == 200
    assert fetched.json()['merchant_name'] == 'Test Merchant'

    listed = client.get('/api/v1/merchants?limit=10&offset=0')
    assert listed.status_code == 200
    assert any(item['merchant_id'] == 'M100' for item in listed.json())


def test_upload_transactions_and_list(client):
    csv_content = (
        'transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type\n'
        'TX-1,2026-01-01,M100,100.50,Sale,Visa\n'
        'TX-2,2026-01-02,M100,50.25,Refund,Mastercard\n'
    ).encode('utf-8')

    files = {'file': ('transactions.csv', BytesIO(csv_content), 'text/csv')}
    data = {'merchant_id': 'M100'}

    upload = client.post('/api/v1/transactions/upload', files=files, data=data)
    assert upload.status_code == 200
    body = upload.json()
    assert body['status'] == 'success'
    assert body['stored_records'] == 2

    listed = client.get('/api/v1/transactions?merchant_id=M100&limit=10&offset=0')
    assert listed.status_code == 200
    assert len(listed.json()) >= 2


def test_calculations_success_and_validation(client):
    transactions = [
        {
            'transaction_id': 'TX-C1',
            'transaction_date': '2026-01-01',
            'merchant_id': 'M200',
            'amount': 100,
            'transaction_type': 'Sale',
            'card_type': 'Visa',
        },
        {
            'transaction_id': 'TX-C2',
            'transaction_date': '2026-01-02',
            'merchant_id': 'M200',
            'amount': 50,
            'transaction_type': 'Sale',
            'card_type': 'Mastercard',
        },
    ]

    no_mcc = client.post('/api/v1/calculations/merchant-fee', json={'transactions': transactions})
    assert no_mcc.status_code == 400

    merchant_fee = client.post(
        '/api/v1/calculations/merchant-fee',
        json={
            'transactions': transactions,
            'mcc': '5812',
            'current_rate': 0.02,
            'fixed_fee': 0.30,
        },
    )
    assert merchant_fee.status_code == 200
    mf_data = merchant_fee.json()['data']
    assert mf_data['transaction_count'] == 2
    assert mf_data['total_volume'] == 150.0

    desired_margin = client.post(
        '/api/v1/calculations/desired-margin',
        json={
            'transactions': transactions,
            'mcc': '5812',
            'desired_margin': 0.015,
        },
    )
    assert desired_margin.status_code == 200
    dm_data = desired_margin.json()['data']
    assert dm_data['transaction_count'] == 2
    assert dm_data['total_volume'] == 150.0


def test_mcc_endpoints(client):
    all_mcc = client.get('/api/v1/mcc-codes')
    assert all_mcc.status_code == 200
    assert all_mcc.json()['status'] == 'success'
    assert len(all_mcc.json()['data']) > 0

    bad_search = client.get('/api/v1/mcc-codes/search?q=5')
    assert bad_search.status_code == 400

    search = client.get('/api/v1/mcc-codes/search?q=58')
    assert search.status_code == 200
    assert search.json()['status'] == 'success'

    known = client.get('/api/v1/mcc-codes/5812')
    assert known.status_code == 200
    assert known.json()['data']['code'] == '5812'

    missing = client.get('/api/v1/mcc-codes/9998')
    assert missing.status_code == 404
