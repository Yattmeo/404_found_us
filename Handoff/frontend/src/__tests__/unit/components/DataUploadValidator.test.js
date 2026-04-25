import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DataUploadValidator from '../../../components/DataUploadValidator';
import { parseFileData } from '../../../utils/fileParser';

jest.mock('../../../utils/fileParser', () => ({
  parseFileData: jest.fn(),
}));

const validRow = {
  transaction_id: 'TX1',
  transaction_date: '2026-01-01',
  card_brand: 'Visa',
  merchant_id: 'M1',
  mcc: '5411',
  amount: '100.00',
  transaction_type: 'Sale',
  card_type: 'Credit',
};

describe('DataUploadValidator', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows error for unsupported file types', async () => {
    render(<DataUploadValidator onValidDataConfirmed={jest.fn()} onMCCExtracted={jest.fn()} />);

    const fileInput = document.querySelector('#file-upload');
    const invalidFile = new File(['x'], 'bad.txt', { type: 'text/plain' });
    fireEvent.change(fileInput, { target: { files: [invalidFile] } });

    expect(await screen.findByText(/invalid file type/i)).toBeInTheDocument();
  });

  it('shows preview and proceeds with valid parsed data', async () => {
    const onValidDataConfirmed = jest.fn();
    const onMCCExtracted = jest.fn();

    parseFileData.mockResolvedValue({
      errors: [],
      data: [validRow, validRow],
    });

    render(
      <DataUploadValidator
        onValidDataConfirmed={onValidDataConfirmed}
        onMCCExtracted={onMCCExtracted}
      />,
    );

    const fileInput = document.querySelector('#file-upload');
    const csvFile = new File(['a,b'], 'transactions_mcc_5411.csv', { type: 'text/csv' });
    fireEvent.change(fileInput, { target: { files: [csvFile] } });

    await waitFor(() => expect(screen.getByText(/preview: transactions_mcc_5411.csv/i)).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /proceed to projection/i }));

    expect(onValidDataConfirmed).toHaveBeenCalledWith([validRow, validRow]);
    expect(onMCCExtracted).toHaveBeenCalledWith('5411');
  });

  it('shows validation errors and supports dismissing banner', async () => {
    parseFileData.mockResolvedValue({
      errors: [{ row: 2, column: 'amount', error: 'Invalid amount' }],
      data: [],
    });

    render(<DataUploadValidator onValidDataConfirmed={jest.fn()} onMCCExtracted={jest.fn()} />);

    const fileInput = document.querySelector('#file-upload');
    const csvFile = new File(['a,b'], 'invalid.csv', { type: 'text/csv' });
    fireEvent.change(fileInput, { target: { files: [csvFile] } });

    expect(await screen.findByText(/validation failed: 1 issue\(s\) found/i)).toBeInTheDocument();
    expect(screen.getByText(/row 2, amount:/i)).toBeInTheDocument();

    fireEvent.click(document.querySelector('button.text-red-600'));
    expect(screen.queryByText(/validation failed: 1 issue\(s\) found/i)).not.toBeInTheDocument();
  });

  it('supports drag-and-drop upload and re-upload reset', async () => {
    parseFileData.mockResolvedValue({
      errors: [],
      data: [validRow],
    });

    render(<DataUploadValidator onValidDataConfirmed={jest.fn()} onMCCExtracted={jest.fn()} />);

    const dropZone = document.querySelector('div.border-2.border-dashed');
    const csvFile = new File(['a,b'], 'drop.csv', { type: 'text/csv' });

    fireEvent.dragEnter(dropZone, { dataTransfer: { files: [csvFile] } });
    fireEvent.drop(dropZone, { dataTransfer: { files: [csvFile] } });

    await waitFor(() => expect(screen.getByText(/preview: drop.csv/i)).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /re-upload file/i }));
    expect(screen.getByText(/click to upload/i)).toBeInTheDocument();
  });

  it('downloads template when link is clicked', () => {
    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;
    URL.createObjectURL = jest.fn(() => 'blob:test');
    URL.revokeObjectURL = jest.fn();
    const clickSpy = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    render(<DataUploadValidator onValidDataConfirmed={jest.fn()} onMCCExtracted={jest.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /download template/i }));

    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test');

    clickSpy.mockRestore();
    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
  });
});
