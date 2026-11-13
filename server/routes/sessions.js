const express = require("express");
const mongoose = require("mongoose");
const Session = require("../models/Session");
const Message = require("../models/Message");

const router = express.Router();

router.post("/sessions", async (req, res) => {
  const title = req.body?.title?.trim() || "New chat";
  const session = await Session.create({ title });
  res.json({ sessionId: session._id }); // this id becomes the agent's thread_id
});

router.get("/sessions", async (req, res) => {
  const sessions = await Session.find().sort({ createdAt: -1 }); // newest first
  res.json(sessions.map((s) => ({ sessionId: s._id, title: s.title, createdAt: s.createdAt })));
});

router.get("/sessions/:id/messages", async (req, res) => {
  const { id } = req.params;
  if (!mongoose.isValidObjectId(id) || !(await Session.exists({ _id: id }))) {
    return res.status(404).json({ error: "Session not found" });
  }
  const messages = await Message.find({ sessionId: id }).sort({ createdAt: 1 }); // oldest first
  res.json(messages.map((m) => ({
    role: m.role, content: m.content, sources: m.sources,
    route: m.route, retries: m.retries, createdAt: m.createdAt,
  })));
});

module.exports = router;
