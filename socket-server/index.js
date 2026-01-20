const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const redis = require('redis');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  path: "/realtimedata/",
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';

const subscriber = redis.createClient({ url: REDIS_URL });

subscriber.on('error', (err) => console.log('Redis Client Error', err));

async function start() {
  await subscriber.connect();
  console.log('Connected to Redis');

  await subscriber.subscribe('dashboard_updates', (message) => {
    console.log('Received update:', message);
    const data = JSON.parse(message);
    // Emit to specific room based on view_id or broadcast
    io.emit(`update:${data.view_id}`, data.payload);
    io.emit('dashboard_global', data); // For overview pages
  });

  io.on('connection', (socket) => {
    console.log('a user connected:', socket.id);

    socket.on('subscribe_view', (viewId) => {
      socket.join(`view:${viewId}`);
      console.log(`Socket ${socket.id} joined view:${viewId}`);
    });

    socket.on('disconnect', () => {
      console.log('user disconnected');
    });
  });

  const PORT = process.env.SOCKET_PORT || 3000;
  server.listen(PORT, () => {
    console.log(`Socket.IO server running on port ${PORT}`);
  });
}

start();
