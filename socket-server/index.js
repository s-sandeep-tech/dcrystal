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

app.use(express.json());

const JWT_SECRET = process.env.JWT_SECRET_KEY;
if (!JWT_SECRET || JWT_SECRET.trim().length < 32 || JWT_SECRET === 'super-secret-key-change-me') {
  throw new Error('JWT_SECRET_KEY must be configured with a random secret of at least 32 characters');
}

// Authentication middleware for standard socket connections
io.use((socket, next) => {
  const token = socket.handshake.auth.token || socket.handshake.headers['authorization'];
  if (!token) return next(new Error('Authentication error: Token missing'));

  const jwtToken = token.startsWith('Bearer ') ? token.slice(7) : token;
  jwt.verify(jwtToken, JWT_SECRET, (err, decoded) => {
    if (err) return next(new Error('Authentication error: Invalid token'));
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

  const connectedUsers = new Map();

  await subscriber.subscribe('dashboard_updates', (message) => {
    const data = JSON.parse(message);
    io.emit(`update:${data.view_id}`, data.payload);
    io.emit('dashboard_global', data);
  });

  await subscriber.subscribe('global_notifications', (message) => {
    try {
      const data = JSON.parse(message);
      if (data.socket_id) {
        io.to(data.socket_id).emit('new_notification', data);
      } else {
        io.emit('global_notification', data); 
      }
    } catch (e) {
      console.error('Error parsing global notification:', e);
    }
  });

  await subscriber.subscribe('sync_updates', (message) => {
    try {
      const data = JSON.parse(message);
      io.emit('sync_update', data);
    } catch (e) {
      console.error('Error parsing sync update:', e);
    }
  });

  await subscriber.subscribe('akt_performance_updates', (message) => {
    console.log('Received AKT performance update signal');
    try {
      const data = JSON.parse(message);
      io.emit('aktPerformanceRefresh', data);
    } catch (e) {
      console.error('Error parsing AKT update signal:', e);
    }
  });

  io.on('connection', (socket) => {
    const ipAddress = socket.handshake.headers['x-forwarded-for'] || socket.handshake.address;
    const userId = socket.user ? (socket.user.sub || socket.user.user_id || socket.user.username || 'System') : 'Guest';
    const connectedAt = Date.now();
    const initialTransport = socket.conn.transport.name;
    // Allowlisted fields only: never log handshake headers, auth tokens or raw errors.
    const logConnection = (event, details = {}) => {
      console.log(JSON.stringify({
        timestamp: new Date().toISOString(),
        event,
        user_id: userId,
        socket_id: socket.id,
        transport: socket.conn.transport.name,
        initial_transport: initialTransport,
        duration_ms: Date.now() - connectedAt,
        active_connections: connectedUsers.size,
        ...details
      }));
    };

    connectedUsers.set(socket.id, {
      sid: socket.id,
      user_id: socket.user ? (socket.user.user_id || socket.user.sub || 'N/A') : 'Guest',
      username: socket.user ? (socket.user.username || socket.user.name || 'Unknown') : 'Guest',
      ip_address: ipAddress,
      connected_at: new Date().toISOString()
    });
    logConnection('socket_connected');

    socket.conn.on('upgrade', (transport) => {
      logConnection('socket_transport_upgraded', { transport: transport.name });
    });

    socket.on('subscribe_view', (viewId) => {
      socket.join(`view:${viewId}`);
    });

    socket.on('get_active_users', (...args) => {
      const callback = args[args.length - 1];
      if (typeof callback === 'function') {
        callback({ users: Array.from(connectedUsers.values()) });
      }
    });

    socket.on('disconnect', (reason) => {
      connectedUsers.delete(socket.id);
      logConnection('socket_disconnected', { reason });
    });
  });

  const PORT = process.env.SOCKET_PORT || 3000;
  server.listen(PORT, () => {
    console.log(`Socket.IO server (Express) running on port ${PORT}`);
  });
}

start();
