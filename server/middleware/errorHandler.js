const multer = require("multer");

// Every error from every route ends up here, so the error format is the same everywhere
function errorHandler(err, req, res, next) {
  // Multer: file too large
  if (err instanceof multer.MulterError) {
    const message = err.code === "LIMIT_FILE_SIZE" ? "File is larger than 10 MB" : err.message;
    return res.status(400).json({ error: message });
  }

  // Our own errors with a status (e.g. wrong file type, unknown session)
  if (err.status) {
    return res.status(err.status).json({ error: err.message });
  }

  // Errors from the AI service (Axios)
  if (err.isAxiosError) {
    if (!err.response) {
      // Connection refused or timeout: FastAPI is down or too slow
      console.error("AI service unreachable:", err.code);
      return res.status(503).json({ error: "AI service is unavailable" });
    }
    if (err.response.status === 400) {
      return res.status(400).json({ error: err.response.data?.detail || "Bad request" });
    }
    console.error("AI service error:", err.response.status);
    return res.status(500).json({ error: "AI service error" });
  }

  console.error(err);
  res.status(500).json({ error: "Something went wrong" });
}

module.exports = errorHandler;
