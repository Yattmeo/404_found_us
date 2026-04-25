describe('index entrypoint', () => {
  beforeEach(() => {
    jest.resetModules();
    document.body.innerHTML = '<div id="root"></div>';
  });

  it('creates a root and renders App in StrictMode', () => {
    const renderMock = jest.fn();
    const createRootMock = jest.fn(() => ({ render: renderMock }));

    jest.doMock('react-dom/client', () => ({
      createRoot: createRootMock,
    }));

    jest.doMock('../../App', () => () => <div>App Mock</div>);

    jest.isolateModules(() => {
      require('../../index');
    });

    expect(createRootMock).toHaveBeenCalledWith(document.getElementById('root'));
    expect(renderMock).toHaveBeenCalledTimes(1);
  });
});
