const mongoose = require("mongoose");

// Messages shown on screen. The agent's own memory lives separately in the checkpoints.
const messageSchema = new mongoose.Schema({
  sessionId: { type: mongoose.Schema.Types.ObjectId, ref: "Session", required: true },
  role: { type: String, enum: ["user", "assistant"], required: true },
  content: { type: String, required: true },
  sources: [{ filename: String, page: Number, _id: false }],
  route: String,
  retries: Number,
  createdAt: { type: Date, default: Date.now },
});

messageSchema.index({ sessionId: 1, createdAt: 1 }); // fast "messages of one chat, in order"

module.exports = mongoose.model("Message", messageSchema);
