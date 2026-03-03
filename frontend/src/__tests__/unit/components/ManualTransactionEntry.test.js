import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ManualTransactionEntry from '../../../components/ManualTransactionEntry';

describe('ManualTransactionEntry', () => {
  it('shows estimated monthly volume from valid inputs', () => {
    render(<ManualTransactionEntry onValidDataConfirmed={jest.fn()} />);

    fireEvent.change(screen.getByLabelText(/average transaction value/i), { target: { value: '100' } });
    fireEvent.change(screen.getByLabelText(/monthly transactions/i), { target: { value: '5' } });

    expect(screen.getByText('Estimated Monthly Volume')).toBeInTheDocument();
    expect(screen.getByText('$500.00')).toBeInTheDocument();
  });

  it('generates data and proceeds on click', () => {
    const onValidDataConfirmed = jest.fn();
    render(<ManualTransactionEntry onValidDataConfirmed={onValidDataConfirmed} />);

    fireEvent.change(screen.getByLabelText(/average transaction value/i), { target: { value: '50' } });
    fireEvent.change(screen.getByLabelText(/monthly transactions/i), { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: /generate & proceed/i }));

    expect(onValidDataConfirmed).toHaveBeenCalledTimes(1);
    expect(onValidDataConfirmed.mock.calls[0][0]).toHaveLength(3);
  });

  it('auto-confirms valid inputs when enabled', async () => {
    const onValidDataConfirmed = jest.fn();
    render(
      <ManualTransactionEntry
        onValidDataConfirmed={onValidDataConfirmed}
        showProceedButton={false}
        autoConfirm
      />,
    );

    fireEvent.change(screen.getByLabelText(/average transaction value/i), { target: { value: '25' } });
    fireEvent.change(screen.getByLabelText(/monthly transactions/i), { target: { value: '2' } });

    await waitFor(() => expect(onValidDataConfirmed).toHaveBeenCalledTimes(1));
  });
});
