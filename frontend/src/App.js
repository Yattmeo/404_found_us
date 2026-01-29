import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:5000/')
      .then(response => response.json())
      .then(data => {
        setMessage(data.message);
        setLoading(false);
      })
      .catch(error => {
        console.error('Error:', error);
        setMessage('Error connecting to backend');
        setLoading(false);
      });
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>ML Web Application</h1>
        {loading ? <p>Loading...</p> : <p>{message}</p>}
      </header>
    </div>
  );
}

export default App;
