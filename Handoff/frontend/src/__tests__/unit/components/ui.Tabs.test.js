import { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../../components/ui/Tabs';

const TabsHarness = () => {
  const [value, setValue] = useState('first');

  return (
    <Tabs value={value} onValueChange={setValue}>
      <TabsList>
        <TabsTrigger value="first">First</TabsTrigger>
        <TabsTrigger value="second">Second</TabsTrigger>
      </TabsList>
      <TabsContent value="first">First content</TabsContent>
      <TabsContent value="second">Second content</TabsContent>
    </Tabs>
  );
};

describe('Tabs', () => {
  it('switches visible content when trigger is clicked', () => {
    render(<TabsHarness />);

    expect(screen.getByText('First content')).toBeInTheDocument();
    expect(screen.queryByText('Second content')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Second' }));

    expect(screen.getByText('Second content')).toBeInTheDocument();
    expect(screen.queryByText('First content')).not.toBeInTheDocument();
  });
});
