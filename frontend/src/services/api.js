import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Merchant Fee Calculator API endpoints
export const merchantFeeAPI = {
  // Calculate profitability based on current rates
  calculateCurrentRates: async (data) => {
    try {
      const response = await api.post('/merchant-fee/calculate', data);
      return response.data;
    } catch (error) {
      console.error('Error calculating current rates:', error);
      throw error;
    }
  },

  // Upload and validate transaction data
  uploadTransactionData: async (formData) => {
    try {
      const response = await api.post('/merchant-fee/upload', formData, {
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

  // Get MCC information
  getMCCList: async () => {
    try {
      const response = await api.get('/merchant-fee/mcc-list');
      return response.data;
    } catch (error) {
      console.error('Error fetching MCC list:', error);
      throw error;
    }
  },
};

// Desired Margin Calculator API endpoints
export const desiredMarginAPI = {
  // Calculate desired margin rates
  calculateDesiredMargin: async (data) => {
    try {
      const response = await api.post('/desired-margin/calculate', data);
      return response.data;
    } catch (error) {
      console.error('Error calculating desired margin:', error);
      throw error;
    }
  },

  // Upload merchant data file
  uploadMerchantData: async (formData) => {
    try {
      const response = await api.post('/desired-margin/upload', formData, {
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

export default api;
