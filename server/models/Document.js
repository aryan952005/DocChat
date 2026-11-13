const mongoose = require("mongoose");

// One record per uploaded file (the file itself is not stored anywhere)
const documentSchema = new mongoose.Schema({
  docId: { type: String, required: true, unique: true }, // same id as the Qdrant chunks
  filename: { type: String, required: true },
  chunks: { type: Number, required: true },
  uploadedAt: { type: Date, default: Date.now },
});

module.exports = mongoose.model("Document", documentSchema);
