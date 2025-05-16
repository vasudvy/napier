// Simple web interface for Napier
const express = require('express');
const cors = require('cors');
const axios = require('axios');
const http = require('http');
const socketIo = require('socket.io');
const { spawn } = require('child_process');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = socketIo(server);

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Napier service connection details
const NAPIER_HOST = process.env.NAPIER_HOST || 'napier';
const NAPIER_PORT = process.env.NAPIER_PORT || 5000;

// Route to serve the main page
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// API endpoint to proxy requests to Napier
app.post('/api/napier', async (req, res) => {
  try {
    const { query } = req.body;
    if (!query) {
      return res.status(400).json({ error: 'Query is required' });
    }

    // Here you would normally call your Napier service via HTTP
    // For now, we'll execute the CLI command within this container
    const napierProcess = spawn('docker', [
      'exec', 
      'napier-napier-1', 
      'python', 
      'cli.py', 
      '--query', 
      query
    ]);

    let output = '';
    let errorOutput = '';

    napierProcess.stdout.on('data', (data) => {
      output += data.toString();
    });

    napierProcess.stderr.on('data', (data) => {
      errorOutput += data.toString();
    });

    napierProcess.on('close', (code) => {
      if (code === 0) {
        res.json({ success: true, result: output });
      } else {
        res.status(500).json({ 
          success: false, 
          error: errorOutput || 'Unknown error executing Napier command' 
        });
      }
    });
  } catch (error) {
    console.error('Error calling Napier:', error);
    res.status(500).json({ error: error.message });
  }
});

// Socket.IO connection for real-time interaction
io.on('connection', (socket) => {
  console.log('New client connected');
  
  socket.on('napier:query', async (data) => {
    try {
      const { query } = data;
      if (!query) {
        socket.emit('napier:error', { error: 'Query is required' });
        return;
      }

      const napierProcess = spawn('docker', [
        'exec', 
        'napier-napier-1', 
        'python', 
        'cli.py', 
        '--query', 
        query
      ]);

      // Send immediate acknowledgment
      socket.emit('napier:ack', { 
        message: 'Processing query: ' + query,
        timestamp: new Date()
      });

      napierProcess.stdout.on('data', (data) => {
        // Send incremental outputs
        socket.emit('napier:progress', { 
          output: data.toString(),
          timestamp: new Date()
        });
      });

      let errorOutput = '';
      napierProcess.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });

      napierProcess.on('close', (code) => {
        if (code === 0) {
          socket.emit('napier:response', { 
            success: true,
            timestamp: new Date()
          });
        } else {
          socket.emit('napier:error', { 
            error: errorOutput || 'Unknown error executing Napier command',
            timestamp: new Date()
          });
        }
      });
    } catch (error) {
      console.error('Error processing socket query:', error);
      socket.emit('napier:error', { error: error.message });
    }
  });

  socket.on('disconnect', () => {
    console.log('Client disconnected');
  });
});

// Start the server
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Napier Web Interface running on port ${PORT}`);
});