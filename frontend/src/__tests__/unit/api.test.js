describe('services/api', () => {
  let apiInstance;
  let moduleRef;
  let axiosMock;
  let consoleErrorSpy;

  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
    delete process.env.REACT_APP_BACKEND_URL;
    delete process.env.REACT_APP_API_URL;

    apiInstance = {
      post: jest.fn(),
      get: jest.fn(),
      interceptors: {
        response: {
          use: jest.fn(),
        },
      },
    };

    jest.doMock('axios', () => ({
      create: jest.fn(() => apiInstance),
    }));

    axiosMock = require('axios');
    moduleRef = require('../../services/api');
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it('creates axios client with default base URL and json headers', () => {
    expect(axiosMock.create).toHaveBeenCalledWith({
      baseURL: '/api/v1',
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('registers response interceptor and handles all error shapes', () => {
    const rejectHandler = apiInstance.interceptors.response.use.mock.calls[0][1];

    const responseErr = { response: { data: { detail: 'bad request' } } };
    try {
      rejectHandler(responseErr);
    } catch (error) {
      expect(error).toBe(responseErr);
    }
    expect(consoleErrorSpy).toHaveBeenCalledWith('API Error:', responseErr.response.data);

    const requestErr = { request: { readyState: 4 } };
    try {
      rejectHandler(requestErr);
    } catch (error) {
      expect(error).toBe(requestErr);
    }
    expect(consoleErrorSpy).toHaveBeenCalledWith('No response received:', requestErr.request);

    const plainErr = { message: 'boom' };
    try {
      rejectHandler(plainErr);
    } catch (error) {
      expect(error).toBe(plainErr);
    }
    expect(consoleErrorSpy).toHaveBeenCalledWith('Error:', 'boom');
  });

  it('covers merchantFeeAPI endpoints', async () => {
    const { merchantFeeAPI } = moduleRef;

    apiInstance.post.mockResolvedValueOnce({ data: { totalCost: 100 } });
    const file = new File(['x'], 'transactions.csv', { type: 'text/csv' });
    const transactionCosts = await merchantFeeAPI.calculateTransactionCosts(file, 5812);
    expect(transactionCosts).toEqual({ totalCost: 100 });
    expect(apiInstance.post).toHaveBeenCalledWith(
      '/calculations/transaction-costs?mcc=5812',
      expect.any(FormData),
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );

    apiInstance.post.mockResolvedValueOnce({ data: { suggestedRate: 1.8 } });
    const currentRates = await merchantFeeAPI.calculateCurrentRates([{ amount: 100 }], '5812', 2.1, 0.4);
    expect(currentRates).toEqual({ suggestedRate: 1.8 });
    expect(apiInstance.post).toHaveBeenCalledWith('/calculations/merchant-fee', {
      transactions: [{ amount: 100 }],
      mcc: '5812',
      current_rate: 2.1,
      fixed_fee: 0.4,
    });

    apiInstance.post.mockResolvedValueOnce({ data: { uploaded: true } });
    await merchantFeeAPI.uploadTransactionData(file, 'M100');
    expect(apiInstance.post).toHaveBeenCalledWith(
      '/transactions/upload',
      expect.any(FormData),
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );

    apiInstance.post.mockResolvedValueOnce({ data: { uploaded: true } });
    await merchantFeeAPI.uploadTransactionData(file);

    apiInstance.get.mockResolvedValueOnce({ data: ['5812'] });
    await expect(merchantFeeAPI.getMCCList()).resolves.toEqual(['5812']);
    expect(apiInstance.get).toHaveBeenCalledWith('/mcc-codes');

    apiInstance.get.mockResolvedValueOnce({ data: ['5812'] });
    await expect(merchantFeeAPI.searchMCCs('58')).resolves.toEqual(['5812']);
    expect(apiInstance.get).toHaveBeenCalledWith('/mcc-codes/search', { params: { q: '58' } });

    apiInstance.get.mockResolvedValueOnce({ data: { items: [] } });
    await merchantFeeAPI.getTransactions(2, 50, 'M100');
    expect(apiInstance.get).toHaveBeenCalledWith('/transactions', {
      params: { page: 2, per_page: 50, merchant_id: 'M100' },
    });

    apiInstance.get.mockResolvedValueOnce({ data: { items: [] } });
    await merchantFeeAPI.getTransactions();
    expect(apiInstance.get).toHaveBeenCalledWith('/transactions', {
      params: { page: 1, per_page: 20 },
    });
  });

  it('covers desiredMarginAPI endpoints for array and object payloads', async () => {
    const { desiredMarginAPI } = moduleRef;
    const file = new File(['x'], 'merchant.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    apiInstance.post.mockResolvedValueOnce({ data: { ok: true } });
    const arrayPayloadResponse = await desiredMarginAPI.calculateDesiredMargin([{ amount: 100 }], '5812', 0.02);
    expect(arrayPayloadResponse).toEqual({ ok: true });
    expect(apiInstance.post).toHaveBeenCalledWith('/calculations/desired-margin', {
      transactions: [{ amount: 100 }],
      mcc: '5812',
      desired_margin: 0.02,
    });

    apiInstance.post.mockResolvedValueOnce({ data: { ok: true } });
    const objectPayloadResponse = await desiredMarginAPI.calculateDesiredMargin({
      transactions: [{ amount: 50 }],
      mcc: '5411',
      desired_margin: 0.015,
    });
    expect(objectPayloadResponse).toEqual({ ok: true });
    expect(apiInstance.post).toHaveBeenCalledWith('/calculations/desired-margin', {
      transactions: [{ amount: 50 }],
      mcc: '5411',
      desired_margin: 0.015,
    });

    apiInstance.post.mockResolvedValueOnce({ data: { details: true } });
    const detailsResponse = await desiredMarginAPI.getDesiredMarginDetails([{ amount: 60 }], '5812', 0.02);
    expect(detailsResponse).toEqual({ details: true });
    expect(apiInstance.post).toHaveBeenCalledWith('/calculations/desired-margin-details', {
      transactions: [{ amount: 60 }],
      mcc: '5812',
      desired_margin: 0.02,
    });

    apiInstance.post.mockResolvedValueOnce({ data: { details: true, mode: 'object' } });
    await desiredMarginAPI.getDesiredMarginDetails({
      transactions: [{ amount: 10 }],
      mcc: '5411',
      desired_margin: 0.01,
      card_type: 'both',
    });
    expect(apiInstance.post).toHaveBeenCalledWith('/calculations/desired-margin-details', {
      transactions: [{ amount: 10 }],
      mcc: '5411',
      desired_margin: 0.01,
      card_type: 'both',
    });

    apiInstance.post.mockResolvedValueOnce({ data: { uploaded: true } });
    await desiredMarginAPI.uploadMerchantData(file);
    expect(apiInstance.post).toHaveBeenCalledWith(
      '/transactions/upload',
      expect.any(FormData),
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  });

  it('covers merchantAPI endpoints', async () => {
    const { merchantAPI } = moduleRef;

    apiInstance.get.mockResolvedValueOnce({ data: { data: [] } });
    await merchantAPI.getMerchants(3, 10);
    expect(apiInstance.get).toHaveBeenCalledWith('/merchants', {
      params: { page: 3, per_page: 10 },
    });

    apiInstance.get.mockResolvedValueOnce({ data: { id: 'M123' } });
    await merchantAPI.getMerchant('M123');
    expect(apiInstance.get).toHaveBeenCalledWith('/merchants/M123');

    apiInstance.post.mockResolvedValueOnce({ data: { id: 'M123', saved: true } });
    await merchantAPI.saveMerchant({ merchant_id: 'M123' });
    expect(apiInstance.post).toHaveBeenCalledWith('/merchants', { merchant_id: 'M123' });
  });

  it('rethrows endpoint errors from catch blocks', async () => {
    const { merchantFeeAPI, desiredMarginAPI, merchantAPI } = moduleRef;
    const apiError = new Error('network failure');

    apiInstance.post.mockRejectedValueOnce(apiError);
    await expect(merchantFeeAPI.calculateCurrentRates([], '5812', 1.5)).rejects.toThrow('network failure');

    apiInstance.post.mockRejectedValueOnce(apiError);
    await expect(desiredMarginAPI.calculateDesiredMargin([], '5812')).rejects.toThrow('network failure');

    apiInstance.post.mockRejectedValueOnce(apiError);
    await expect(desiredMarginAPI.getDesiredMarginDetails([], '5812')).rejects.toThrow('network failure');

    apiInstance.get.mockRejectedValueOnce(apiError);
    await expect(merchantAPI.getMerchants()).rejects.toThrow('network failure');

    apiInstance.post.mockRejectedValueOnce(apiError);
    await expect(merchantFeeAPI.calculateTransactionCosts(new File(['x'], 'f.csv'), 5812)).rejects.toThrow('network failure');

    apiInstance.get.mockRejectedValueOnce(apiError);
    await expect(merchantAPI.getMerchant('M1')).rejects.toThrow('network failure');

    apiInstance.post.mockRejectedValueOnce(apiError);
    await expect(merchantAPI.saveMerchant({ merchant_id: 'M1' })).rejects.toThrow('network failure');

    expect(consoleErrorSpy).toHaveBeenCalled();
  });
});
