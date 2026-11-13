const mongoose = require("mongoose");

// One record per chat. Its _id is also the LangGraph thread_id (the agent's memory key)
const sessionSchema = new mongoose.Schema({
  title: { type: String, default: "New chat" },
  createdAt: { type: Date, default: Date.now },
});

module.exports = mongoose.model("Session", sessionSchema);
