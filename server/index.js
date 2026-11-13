require("dotenv").config();
const express = require("express");
const cors = require("cors");
const mongoose = require("mongoose");
const errorHandler = require("./middleware/errorHandler");

const app = express();
// Only the React app may call this API (set CLIENT_URL to the deployed frontend URL later)
app.use(cors({ origin: process.env.CLIENT_URL || ["http://localhost:5174", "http://127.0.0.1:5174"] }));
app.use(express.json());  // parse JSON bodies into req.body

// Express 5 passes errors thrown in async handlers to errorHandler automatically
app.use("/api", require("./routes/upload"));
app.use("/api", require("./routes/chat"));
app.use("/api", require("./routes/sessions"));
app.use("/api", require("./routes/documents"));

app.use(errorHandler); // must be last

const PORT = process.env.PORT || 5001;

mongoose
  .connect(process.env.MONGO_URI, { dbName: process.env.MONGO_DB })
  .then(() => {
    app.listen(PORT, () => console.log(`Express gateway on http://localhost:${PORT}`));
  })
  .catch((err) => {
    console.error("MongoDB connection failed:", err.message);
    process.exit(1);
  });
