const express = require("express");
const Document = require("../models/Document");

const router = express.Router();

router.get("/documents", async (req, res) => {
  const docs = await Document.find().sort({ uploadedAt: -1 });
  res.json(docs.map((d) => ({
    docId: d.docId, filename: d.filename, chunks: d.chunks, uploadedAt: d.uploadedAt,
  })));
});

module.exports = router;
