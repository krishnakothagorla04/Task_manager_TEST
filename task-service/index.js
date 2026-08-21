// ============================================================
// TASK SERVICE — Microservice for task management
// Part of the Task Manager enterprise DevOps system (CA2)
// ============================================================

const express = require('express');
const mongoose = require('mongoose');
const morgan = require('morgan');
const cors = require('cors');
const axios = require('axios');

const app = express();
app.disable('x-powered-by'); // Security: prevent Express version disclosure
const PORT = process.env.PORT || 3001;
const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017/taskmanager';
const USER_SERVICE_URL = process.env.USER_SERVICE_URL || 'http://localhost:3000';

// Middleware
app.use(express.json());
app.use(cors({
  origin: process.env.CORS_ORIGIN || '*', // Configured via environment variable in production
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type']
}));
app.use(morgan('combined'));

// ---- MongoDB Connection ----
mongoose.connect(MONGO_URI)
  .then(() => console.log('[task-service] Connected to MongoDB'))
  .catch((err) => {
    console.error('[task-service] MongoDB connection error:', err.message);
    process.exit(1);
  });

// ---- Task Schema & Model ----
const taskSchema = new mongoose.Schema({
  userId:      { type: mongoose.Schema.Types.ObjectId, required: true },
  title:       { type: String, required: true },
  description: { type: String, default: '' },
  status:      { type: String, enum: ['pending', 'in-progress', 'completed'], default: 'pending' },
  createdAt:   { type: Date, default: Date.now }
});

const Task = mongoose.model('Task', taskSchema);

// ============================================================
// ROUTES
// ============================================================

// Health check — used by Kubernetes readiness/liveness probes
app.get('/health', (_req, res) => {
  res.status(200).json({ status: 'healthy', service: 'task-service' });
});

// Create a new task (with inter-service user validation)
app.post('/tasks', async (req, res) => {
  try {
    const { userId, title, description } = req.body;
    if (!userId || !title) {
      return res.status(400).json({ error: 'userId and title are required' });
    }

    // ── INTER-SERVICE COMMUNICATION ──
    // Validate that the user exists by calling user-service
    try {
      await axios.get(`${USER_SERVICE_URL}/users/${userId}`, { timeout: 5000 });
    } catch (err) {
      if (err.response && err.response.status === 404) {
        return res.status(404).json({ error: 'User not found in user-service. Create user first.' });
      }
      console.error('[task-service] user-service communication failure:', err.message);
      return res.status(503).json({ error: 'Unable to reach user-service for validation' });
    }

    const task = new Task({ userId, title, description });
    await task.save();
    console.log(`[task-service] Created task: ${task._id} for user: ${userId}`);
    res.status(201).json(task);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get all tasks (optionally filter by userId)
app.get('/tasks', async (req, res) => {
  try {
    const filter = req.query.userId ? { userId: req.query.userId } : {};
    const tasks = await Task.find(filter).sort({ createdAt: -1 });
    res.json(tasks);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Update task status
app.put('/tasks/:id/status', async (req, res) => {
  try {
    const { status } = req.body;
    if (!status) {
      return res.status(400).json({ error: 'status is required' });
    }
    const task = await Task.findByIdAndUpdate(
      req.params.id,
      { status },
      { new: true, runValidators: true }
    );
    if (!task) return res.status(404).json({ error: 'Task not found' });
    console.log(`[task-service] Updated task ${task._id} → ${status}`);
    res.json(task);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Delete a task
app.delete('/tasks/:id', async (req, res) => {
  try {
    const task = await Task.findByIdAndDelete(req.params.id);
    if (!task) return res.status(404).json({ error: 'Task not found' });
    console.log(`[task-service] Deleted task: ${req.params.id}`);
    res.json({ message: 'Task deleted successfully' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ============================================================
// START SERVER
// ============================================================
app.listen(PORT, () => {
  console.log(`[task-service] Running on port ${PORT}`);
});
