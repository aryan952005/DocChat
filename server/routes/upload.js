const crypto = require("crypto");
const path = require("path");
const express = require("express");
const multer = require("multer");
const Document = require("../models/Document");
const { ingestFile } = require("../services/aiClient");

const router = express.Router();
const ALLOWED = [".pdf", ".md", ".txt"];

// Memory storage: the file stays in RAM as req.file.buffer and is never written to disk (D10)
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    if (ALLOWED.includes(ext)) return cb(null, true);
    const err = new Error("Only .pdf, .md and .txt files are allowed");
    err.status = 400;
    cb(err);
  },
});

router.post("/upload", upload.single("file"), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: "No file uploaded" });

  const docId = crypto.randomUUID(); // one id links the MongoDB record and the Qdrant chunks (D11)
  const result = await ingestFile(req.file.buffer, req.file.originalname, docId);

  // Save the record only after FastAPI succeeded, so failed uploads never appear (D9)
  await Document.create({ docId, filename: req.file.originalname, chunks: result.chunks });
  res.json({ docId, filename: req.file.originalname, chunks: result.chunks });
});

module.exports = router;
