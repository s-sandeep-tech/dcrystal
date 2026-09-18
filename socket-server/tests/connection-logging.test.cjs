const { test } = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('logs connection, upgrade and disconnect without leaking credentials', async () => {
  const logs = [];
  const io = new EventEmitter();
  io.use = () => {};
  const subscriber = {
    on() {}, async connect() {}, async subscribe() {}
  };
  const express = () => ({ use() {} });
  express.json = () => {};
  const dependencies = {
    express,
    http: { createServer: () => ({ listen: (_port, ready) => ready() }) },
    'socket.io': { Server: function () { return io; } },
    redis: { createClient: () => subscriber },
    jsonwebtoken: {}
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../index.js'), 'utf8'), {
    require: name => dependencies[name],
    process: { env: { JWT_SECRET_KEY: 'test-only-signing-key-with-at-least-32-characters' } },
    console: { log: value => logs.push(value), error: value => logs.push(value) }
  });
  await new Promise(resolve => setImmediate(resolve));

  for (const [index, reason] of ['ping timeout', 'transport close', 'client namespace disconnect'].entries()) {
    const socket = new EventEmitter();
    socket.id = `test-${index}`;
    socket.user = { sub: '85' };
    socket.handshake = { headers: { authorization: 'SECRET_TOKEN' }, address: 'PRIVATE_IP' };
    socket.conn = new EventEmitter();
    socket.conn.transport = { name: 'polling' };
    io.emit('connection', socket);
    socket.conn.transport = { name: 'websocket' };
    socket.conn.emit('upgrade', socket.conn.transport);
    socket.emit('disconnect', reason);
  }
  const events = logs.filter(line => line.startsWith('{')).map(line => JSON.parse(line));
  assert.equal(events.length, 9);
  for (let i = 0; i < events.length; i += 3) {
    assert.equal(events[i].event, 'socket_connected');
    assert.equal(events[i].transport, 'polling');
    assert.equal(events[i].active_connections, 1);
    assert.equal(events[i + 1].event, 'socket_transport_upgraded');
    assert.equal(events[i + 1].transport, 'websocket');
    assert.equal(events[i + 2].event, 'socket_disconnected');
    assert.equal(events[i + 2].active_connections, 0);
    assert.equal(events[i + 2].initial_transport, 'polling');
    assert.equal(typeof events[i + 2].reason, 'string');
    assert(events[i + 2].duration_ms >= 0);
    assert(!Number.isNaN(Date.parse(events[i + 2].timestamp)));
  }
  assert.equal(events[2].reason, 'ping timeout');
  assert(!logs.join('\n').includes('SECRET_TOKEN'));
  assert(!logs.join('\n').includes('PRIVATE_IP'));
});
