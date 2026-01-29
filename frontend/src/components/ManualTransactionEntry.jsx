import React, { useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from './ui/Button';
import { Input } from './ui/Input';

const ManualTransactionEntry = ({ onValidDataConfirmed }) => {
  const [transactions, setTransactions] = useState([
    {
      transaction_id: '',
      transaction_date: '',
      merchant_id: '',
      amount: '',
      transaction_type: '',
      card_type: ''
    }
  ]);

  const addTransaction = () => {
    setTransactions([
      ...transactions,
      {
        transaction_id: '',
        transaction_date: '',
        merchant_id: '',
        amount: '',
        transaction_type: '',
        card_type: ''
      }
    ]);
  };

  const removeTransaction = (index) => {
    setTransactions(transactions.filter((_, i) => i !== index));
  };

  const updateTransaction = (index, field, value) => {
    const updated = [...transactions];
    updated[index][field] = value;
    setTransactions(updated);
  };

  const handleSubmit = () => {
    // Filter out empty transactions
    const validTransactions = transactions.filter(t =>
      t.transaction_id && t.transaction_date && t.merchant_id && t.amount
    );

    if (validTransactions.length === 0) {
      alert('Please add at least one complete transaction');
      return;
    }

    onValidDataConfirmed(validTransactions);
  };

  return (
    <div className="space-y-4">
      <div className="max-h-96 overflow-y-auto space-y-4 p-1">
        {transactions.map((transaction, index) => (
          <div key={index} className="border border-gray-200 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-medium text-gray-700">Transaction {index + 1}</h4>
              {transactions.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeTransaction(index)}
                  className="text-red-600 hover:text-red-700"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Transaction ID</label>
                <Input
                  type="text"
                  value={transaction.transaction_id}
                  onChange={(e) => updateTransaction(index, 'transaction_id', e.target.value)}
                  placeholder="TXN001"
                  className="h-9"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Date (DD/MM/YYYY)</label>
                <Input
                  type="text"
                  value={transaction.transaction_date}
                  onChange={(e) => updateTransaction(index, 'transaction_date', e.target.value)}
                  placeholder="17/01/2026"
                  className="h-9"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Merchant ID</label>
                <Input
                  type="text"
                  value={transaction.merchant_id}
                  onChange={(e) => updateTransaction(index, 'merchant_id', e.target.value)}
                  placeholder="M12345"
                  className="h-9"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Amount</label>
                <Input
                  type="number"
                  step="0.01"
                  value={transaction.amount}
                  onChange={(e) => updateTransaction(index, 'amount', e.target.value)}
                  placeholder="500.00"
                  className="h-9"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Transaction Type</label>
                <select
                  value={transaction.transaction_type}
                  onChange={(e) => updateTransaction(index, 'transaction_type', e.target.value)}
                  className="w-full h-9 px-3 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent text-sm"
                >
                  <option value="">Select type</option>
                  <option value="Sale">Sale</option>
                  <option value="Refund">Refund</option>
                  <option value="Void">Void</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Card Type</label>
                <select
                  value={transaction.card_type}
                  onChange={(e) => updateTransaction(index, 'card_type', e.target.value)}
                  className="w-full h-9 px-3 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent text-sm"
                >
                  <option value="">Select card</option>
                  <option value="Visa">Visa</option>
                  <option value="Mastercard">Mastercard</option>
                  <option value="Amex">American Express</option>
                  <option value="Discover">Discover</option>
                </select>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={addTransaction}
          className="flex-1 flex items-center justify-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Transaction
        </Button>

        <Button
          type="button"
          onClick={handleSubmit}
          className="flex-1"
        >
          Confirm Transactions
        </Button>
      </div>
    </div>
  );
};

export default ManualTransactionEntry;
