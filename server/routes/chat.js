const express = require("express");
const mongoose = require("mongoose");
const Session = require("../models/Session");
const Message = require("../models/Message");
const { askAgent } = require("../services/aiClient");

const router = express.Router();

// Short chat title from the first question, like ChatGPT: "What is the rate limit?" -> "What is the rate limit"
function makeTitle(question) {
  let t = question.replace(/\s+/g, " ").trim().replace(/[?.!]+$/, "");
  if (t.length > 40) t = t.slice(0, 40).replace(/\s+\S*$/, "") + "…";
  return t.charAt(0).toUpperCase() + t.slice(1);
}

router.post("/chat", async (req, res) => {
  const sessionId = req.body?.sessionId;
  const question = req.body?.question?.trim();
  if (!sessionId || !question) {
    return res.status(400).json({ error: "sessionId and question are required" });
  }
  const session = mongoose.isValidObjectId(sessionId) ? await Session.findById(sessionId) : null;
  if (!session) {
    return res.status(404).json({ error: "Session not found" });
  }

  await Message.create({ sessionId, role: "user", content: question });
  if (session.title === "New chat") {
    session.title = makeTitle(question);
    await session.save();
  }

  // sessionId is passed as thread_id, so the agent loads this chat's memory
  const result = await askAgent(String(sessionId), question);

  await Message.create({
    sessionId, role: "assistant", content: result.answer,
    sources: result.sources, route: result.route, retries: result.retries,
  });
  res.json({ ...result, title: session.title }); // { answer, sources, route, retries, title }
});

module.exports = router;
