const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const redis = require('redis');
const jwt = require('jsonwebtoken');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  path: "/realtimedata/",
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

const JWT_SECRET = process.env.JWT_SECRET_KEY || 'super-secret-key-change-me';

// Authentication middleware
io.use((socket, next) => {
  const token = socket.handshake.auth.token || socket.handshake.headers['authorization'];

  if (!token) {
    return next(new Error('Authentication error: Token missing'));
  }

  // Handle "Bearer <token>" format if necessary
  const jwtToken = token.startsWith('Bearer ') ? token.slice(7) : token;

  jwt.verify(jwtToken, JWT_SECRET, (err, decoded) => {
    if (err) {
      return next(new Error('Authentication error: Invalid token'));
    }
    socket.user = decoded;
    next();
  });
});

const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';

const subscriber = redis.createClient({ url: REDIS_URL });

subscriber.on('error', (err) => console.log('Redis Client Error', err));

async function start() {
  await subscriber.connect();
  console.log('Connected to Redis');

  // Track active users
  const connectedUsers = new Map();

  await subscriber.subscribe('dashboard_updates', (message) => {
    console.log('Received update:', message);
    const data = JSON.parse(message);
    // Emit to specific room based on view_id or broadcast
    io.emit(`update:${data.view_id}`, data.payload);
    io.emit('dashboard_global', data); // For overview pages
  });

  await subscriber.subscribe('global_notifications', (message) => {
    console.log('Received global notification:', message);
    try {
      const data = JSON.parse(message);
      io.emit('global_notification', data);
    } catch (e) {
      console.error('Error parsing global notification:', e);
    }
  });

  io.on('connection', (socket) => {
    // Determine the IP address (handling proxies if applicable)
    const ipAddress = socket.handshake.headers['x-forwarded-for'] || socket.handshake.address;

    // Default to 'Unknown User' if socket.user is not fully populated
    // Assuming socket.user has logic from jwt.verify
    const userId = socket.user ? (socket.user.sub || socket.user.user_id || socket.user.username || 'System') : 'Guest';

    console.log(`User connected: ${userId} (${socket.id}) from ${ipAddress}`);

    // Store user data
    connectedUsers.set(socket.id, {
      sid: socket.id,
      user_id: socket.user ? (socket.user.user_id || socket.user.sub || 'N/A') : 'Guest',
      username: socket.user ? (socket.user.username || socket.user.name || 'Unknown') : 'Guest',
      ip_address: ipAddress,
      connected_at: new Date().toISOString()
    });

    socket.on('subscribe_view', (viewId) => {
      socket.join(`view:${viewId}`);
      console.log(`Socket ${socket.id} joined view:${viewId}`);
    });

    // Provide endpoint to fetch all active connections
    socket.on('get_active_users', (...args) => {
      // Find the callback function (last argument)
      const callback = args[args.length - 1];
      console.log(`Socket ${socket.id} requested active users list. Count: ${connectedUsers.size}`);

      if (typeof callback === 'function') {
        const usersArray = Array.from(connectedUsers.values());
        console.log('Sending users array:', JSON.stringify(usersArray));
        // Return object with users key as expected by frontend
        callback({ users: usersArray });
      } else {
        console.error('get_active_users called without a callback function');
      }
    });

    socket.on('disconnect', () => {
      console.log(`User disconnected: ${userId} (${socket.id})`);
      connectedUsers.delete(socket.id);
    });
  });

  const PORT = process.env.SOCKET_PORT || 3000;
  server.listen(PORT, () => {
    console.log(`Socket.IO server running on port ${PORT}`);
  });
}

start();
