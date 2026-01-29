import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Error interceptor for consistent error handling
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response) {
      console.error('API Error:', error.response.data);
    } else if (error.request) {
      console.error('No response received:', error.request);
    } else {
      console.error('Error:', error.message);
    }
    throw error;
  }
);

// Merchant Fee Calculator API endpoints
export const merchantFeeAPI = {
  // Calculate fees based on current rates
  calculateCurrentRates: async (transactions, mcc, currentRate, fixedFee = 0.30) => {
    try {
      const response = await api.post('/calculations/merchant-fee', {
        transactions,
        mcc,
        current_rate: currentRate,
        fixed_fee: fixedFee,
      });
      return response.data;
    } catch (error) {
      console.error('Error calculating current rates:', error);
      throw error;
    }
  },

  // Upload and validate transaction data (CSV/Excel)
  uploadTransactionData: async (file, merchantId = null) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (merchantId) {
        formData.append('merchant_id', merchantId);
      }

      const response = await api.post('/transactions/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      console.error('Error uploading transaction data:', error);
      throw error;
    }
  },

  // Get MCC list
  getMCCList: async () => {
    try {
      const response = await api.get('/mcc-codes');
      return response.data;
    } catch (error) {
      console.error('Error fetching MCC list:', error);
      throw error;
    }
  },

  // Search MCCs
  searchMCCs: async (query) => {
    try {
      const response = await api.get('/mcc-codes/search', {
        params: { q: query },
      });
      return response.data;
    } catch (error) {
      console.error('Error searching MCCs:', error);
      throw error;
    }
  },

  // Get transactions
  getTransactions: async (page = 1, perPage = 20, merchantId = null) => {
    try {
      const params = { page, per_page: perPage };
      if (merchantId) {
        params.merchant_id = merchantId;
      }
      const response = await api.get('/transactions', { params });
      return response.data;
    } catch (error) {
      console.error('Error fetching transactions:', error);
      throw error;
    }
  },
};

// Desired Margin Calculator API endpoints
export const desiredMarginAPI = {
  // Calculate desired margin rates
  calculateDesiredMargin: async (transactions, mcc, desiredMargin = 0.015) => {
    try {
      const response = await api.post('/calculations/desired-margin', {
        transactions,
        mcc,
        desired_margin: desiredMargin,
      });
      return response.data;
    } catch (error) {
      console.error('Error calculating desired margin:', error);
      throw error;
    }
  },

  // Upload merchant data (CSV/Excel)
  uploadMerchantData: async (file) => {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await api.post('/transactions/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      console.error('Error uploading merchant data:', error);
      throw error;
    }
  },
};

// Merchant API endpoints
export const merchantAPI = {
  // Get merchants list
  getMerchants: async (page = 1, perPage = 20) => {
    try {
      const response = await api.get('/merchants', {
        params: { page, per_page: perPage },
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching merchants:', error);
      throw error;
    }
  },

  // Get single merchant
  getMerchant: async (merchantId) => {
    try {
      const response = await api.get(`/merchants/${merchantId}`);
      return response.data;
    } catch (error) {
      console.error('Error fetching merchant:', error);
      throw error;
    }
  },

  // Create or update merchant
  saveMerchant: async (merchantData) => {
    try {
      const response = await api.post('/merchants', merchantData);
      return response.data;
    } catch (error) {
      console.error('Error saving merchant:', error);
      throw error;
    }
  },
};

export default api;
